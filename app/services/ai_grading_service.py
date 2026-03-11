"""AI 批改服务。"""

from __future__ import annotations

import base64
import json
import mimetypes
from asyncio import sleep
from pathlib import Path
from typing import Any, Literal

import httpx
from openai import AsyncOpenAI
from openai import APIConnectionError, APITimeoutError
from pydantic import BaseModel, Field

from app.configs import base_configs


class AIGradingTypicalError(BaseModel):
    """AI 识别出的典型错误。"""

    pattern_name: str = Field(min_length=1, max_length=128, description="错误名称")
    pattern_desc: str | None = Field(default=None, description="错误描述")
    suggestion_text: str | None = Field(default=None, description="改进建议")


class AIGradingResult(BaseModel):
    """AI 批改结构化结果。"""

    result_status: Literal["correct", "wrong", "partial", "unanswered"] = Field(
        default="unanswered",
        description="批改结论",
    )
    ai_score: float = Field(default=0, description="AI 评分")
    final_score: float = Field(default=0, description="最终评分")
    ai_feedback: str = Field(default="", description="批改反馈")
    typical_errors: list[AIGradingTypicalError] = Field(
        default_factory=list,
        description="典型错误列表",
    )
    model_name: str = Field(default="", description="模型名称")
    raw_content: str | None = Field(default=None, description="模型原始输出")


class AIGradingService:
    """使用 OpenAI 兼容接口调用千问模型完成作业批改。"""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if not base_configs.LLM_API_KEY:
            raise RuntimeError("未配置 LLM_API_KEY，无法调用 AI 批改")
        if self._client is None:
            http_client = httpx.AsyncClient(
                timeout=base_configs.LLM_TIMEOUT_SEC,
                trust_env=base_configs.LLM_TRUST_ENV_PROXY,
            )
            self._client = AsyncOpenAI(
                api_key=base_configs.LLM_API_KEY,
                base_url=base_configs.LLM_BASE_URL,
                timeout=base_configs.LLM_TIMEOUT_SEC,
                max_retries=base_configs.LLM_MAX_RETRIES,
                http_client=http_client,
            )
        return self._client

    def _build_system_prompt(self) -> str:
        return (
            "你是一名严谨的中文老师/阅卷老师。"
            "请根据题目、参考答案和学生答案进行评分，"
            "只输出 JSON，不要输出任何额外说明。"
            "JSON 字段必须包含：result_status、ai_score、final_score、ai_feedback、typical_errors。"
            "其中 result_status 仅允许 correct、wrong、partial、unanswered。"
            "ai_score 和 final_score 必须是数字，范围在 0 到题目满分之间。"
            "只要学生已作答，就必须给出明确分数，不能省略。"
            "若判定为 correct，则 ai_score 和 final_score 必须等于满分。"
            "typical_errors 是数组，每项包含 pattern_name、pattern_desc、suggestion_text。"
            "若学生未作答，则 result_status=unanswered，分数为 0。"
        )

    def _build_user_prompt(
        self,
        *,
        question_content: str | None,
        reference_answer: str | None,
        student_answer: str | None,
        question_type: str,
        full_score: float,
    ) -> str:
        return (
            f"题型：{question_type}\n"
            f"满分：{full_score}\n\n"
            f"题目：\n{question_content or '无'}\n\n"
            f"参考答案：\n{reference_answer or '无'}\n\n"
            f"学生答案：\n{student_answer or '无'}\n\n"
            "如果同时提供了作答图片，请结合图片内容一起批改。\n\n"
            "请严格返回 JSON，例如："
            '{"result_status":"partial","ai_score":6,"final_score":6,'
            '"ai_feedback":"答案部分正确，步骤不完整",'
            '"typical_errors":[{"pattern_name":"步骤缺失",'
            '"pattern_desc":"没有写出关键推导步骤",'
            '"suggestion_text":"补充中间推导过程"}]}'
        )

    def _build_user_content(
        self,
        *,
        question_content: str | None,
        reference_answer: str | None,
        student_answer: str | None,
        question_type: str,
        full_score: float,
        image_urls: list[str],
    ) -> list[dict[str, Any]] | str:
        prompt = self._build_user_prompt(
            question_content=question_content,
            reference_answer=reference_answer,
            student_answer=student_answer,
            question_type=question_type,
            full_score=full_score,
        )
        if not image_urls:
            return prompt

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_url in image_urls:
            normalized_image_url = self._normalize_image_url(image_url)
            if not normalized_image_url:
                continue
            if not image_url:
                continue
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": normalized_image_url},
                }
            )
        return content

    def _normalize_image_url(self, image_url: str) -> str | None:
        """标准化图片输入，支持远程 URL、Data URL 和本地文件路径。"""
        if not image_url:
            return None
        normalized = image_url.strip()
        if not normalized:
            return None
        if normalized.startswith(("http://", "https://", "data:")):
            return normalized

        file_path = Path(normalized)
        if not file_path.is_absolute():
            file_path = Path(base_configs.PROJECT_DIR) / normalized
        if not file_path.exists() or not file_path.is_file():
            return normalized

        mime_type, _ = mimetypes.guess_type(file_path.name)
        mime_type = mime_type or "application/octet-stream"
        encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _extract_content_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        return ""

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if not text:
            raise ValueError("AI 返回内容为空")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def _normalize_status(self, value: str | None) -> str:
        mapping = {
            "correct": "correct",
            "wrong": "wrong",
            "partial": "partial",
            "partial_correct": "partial",
            "unanswered": "unanswered",
            "未作答": "unanswered",
            "正确": "correct",
            "错误": "wrong",
            "部分正确": "partial",
        }
        normalized = mapping.get((value or "").strip().lower(), None)
        if normalized is None:
            normalized = mapping.get((value or "").strip(), "partial")
        return normalized

    def _normalize_score(self, value: Any, full_score: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, score)
        return min(score, max(full_score, 0.0))

    def _build_score_fallback(self, result_status: str, full_score: float) -> float:
        normalized_full_score = max(float(full_score or 0), 0.0)
        if result_status == "correct":
            return normalized_full_score
        if result_status == "partial":
            if normalized_full_score <= 0:
                return 0.0
            return min(normalized_full_score, max(round(normalized_full_score * 0.6, 2), 1.0))
        return 0.0

    async def grade_answer(
        self,
        *,
        question_content: str | None,
        reference_answer: str | None,
        student_answer: str | None,
        question_type: str,
        full_score: float,
        image_urls: list[str],
    ) -> AIGradingResult:
        """调用大模型进行批改。"""
        has_answer = bool((student_answer or "").strip() or image_urls)
        client = self._get_client()
        model_name = (
            base_configs.LLM_VISION_MODEL_KEY
            if image_urls
            else base_configs.LLM_MODEL_KEY
        )
        last_error: Exception | None = None
        for attempt in range(base_configs.LLM_MAX_RETRIES + 1):
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": self._build_system_prompt()},
                        {
                            "role": "user",
                            "content": self._build_user_content(
                                question_content=question_content,
                                reference_answer=reference_answer,
                                student_answer=student_answer,
                                question_type=question_type,
                                full_score=full_score,
                                image_urls=image_urls,
                            ),
                        },
                    ],
                )
                break
            except (APIConnectionError, APITimeoutError, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt >= base_configs.LLM_MAX_RETRIES:
                    raise RuntimeError(
                        "AI 服务连接失败，请检查网络、代理或 LLM_BASE_URL 配置"
                    ) from exc
                await sleep(min(2**attempt, 3))
        else:
            raise RuntimeError("AI 服务调用失败") from last_error
        message = response.choices[0].message
        raw_content = self._extract_content_text(message.content)
        payload = self._parse_json_content(raw_content)
        result = AIGradingResult.model_validate(payload)
        result.result_status = self._normalize_status(result.result_status)
        result.ai_score = self._normalize_score(result.ai_score, full_score)
        result.final_score = self._normalize_score(result.final_score, full_score)
        fallback_score = self._build_score_fallback(result.result_status, full_score)
        if has_answer and result.ai_score <= 0 < fallback_score:
            result.ai_score = fallback_score
        if has_answer and result.final_score <= 0 < fallback_score:
            result.final_score = fallback_score
        if result.ai_score <= 0 < result.final_score:
            result.ai_score = result.final_score
        if result.final_score <= 0 and result.ai_score > 0:
            result.final_score = result.ai_score
        if result.result_status == "correct":
            result.ai_score = max(result.ai_score, float(full_score or 0))
            result.final_score = max(result.final_score, float(full_score or 0))
        if not result.ai_feedback:
            result.ai_feedback = "AI 已完成批改。"
        result.model_name = model_name
        result.raw_content = raw_content
        return result


ai_grading_service = AIGradingService()
