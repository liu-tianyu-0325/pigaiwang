"""学生测验相关API路由。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from loguru import logger
from pydantic import ValidationError

from app.api.form_response import BaseResponseModel
from app.api.form_response.stu_quiz_response import (
    StuAnswerGradingViewResponseModel,
    StuQuestionDetailResponseModel,
    StuQuizDetailResponseModel,
    StuQuizListResponseModel,
    StuSubmitAnswerResponseModel,
    StuSubmitQuizResponseModel,
)
from app.api.form_validation.stu_quiz_validation import (
    StuAnswerGradingViewRequest,
    StuQuestionDetailRequest,
    StuQuizDetailRequest,
    StuQuizListRequest,
    StuSubmitAnswerRequest,
    StuSubmitQuizRequest,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.stu_quiz_service import stu_quiz_service

router = APIRouter(tags=["学生测验"])


def _ensure_student_identity(
    current_user: UserClaims,
    requested_student_id: str | None,
) -> str:
    student_id = current_user.user_id
    if requested_student_id is not None and requested_student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他学生数据",
        )
    return student_id


def _normalize_upload_files(
    images: list[UploadFile] | None,
) -> list[UploadFile]:
    if not images:
        return []

    valid_files: list[UploadFile] = []
    for image in images:
        if image is None:
            continue

        filename = (image.filename or "").strip()
        content_type = (image.content_type or "").strip()

        if filename in {"", "string"} and content_type in {"", "application/octet-stream"}:
            continue

        valid_files.append(image)

    return valid_files


@router.post(
    "/list",
    response_model=BaseResponseModel[StuQuizListResponseModel],
    summary="获取学生测验列表",
)
async def get_stu_quiz_list(
    request: StuQuizListRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """获取测验列表。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(log_type="user", student_id=student_id)
    log.info("学生请求测验列表")
    res, code, message, data = await stu_quiz_service.get_quiz_list(
        student_id,
        request.status,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/detail",
    response_model=BaseResponseModel[StuQuizDetailResponseModel],
    summary="获取学生测验详情",
)
async def get_stu_quiz_detail(
    request: StuQuizDetailRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """获取测验详情与题目状态列表。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(
        log_type="user", student_id=student_id, quiz_id=request.quiz_id
    )
    log.info("学生请求测验详情")
    res, code, message, data = await stu_quiz_service.get_quiz_detail(
        student_id,
        request.quiz_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/question/detail",
    response_model=BaseResponseModel[StuQuestionDetailResponseModel],
    summary="获取学生题目详情",
)
async def get_stu_question_detail(
    request: StuQuestionDetailRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """获取题目详情、我的答案和批改信息。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(
        log_type="user",
        student_id=student_id,
        question_id=request.question_id,
        quiz_id=request.quiz_id,
    )
    log.info("学生请求题目详情")
    res, code, message, data = await stu_quiz_service.get_question_detail(
        student_id,
        request.question_id,
        request.quiz_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/answer/submit",
    response_model=BaseResponseModel[StuSubmitAnswerResponseModel],
    summary="学生提交答案（支持多图上传）",
)
async def submit_stu_answer(
    request: Request,
    student_id: str | None = Form(default=None, description="学生用户ID（兼容保留，后端仍按当前登录学生处理）"),
    quiz_id: str | None = Form(default=None, description="测验ID"),
    question_id: str | None = Form(default=None, description="题目ID"),
    answer_md: str | None = Form(default=None, description="Markdown答案文本"),
    submitted_at: datetime | None = Form(default=None, description="提交时间，不传则使用当前时间"),
    duration_sec: int = Form(default=0, description="用时，单位秒"),
    images: list[UploadFile] | None = File(default=None, description="答案图片（可多张）"),
    current_user: UserClaims = get_current_user_dependency,
):
    """学生提交题目答案。"""
    content_type = request.headers.get("content-type", "").lower()
    payload: dict[str, Any] = {
        "student_id": student_id,
        "quiz_id": quiz_id,
        "question_id": question_id,
        "answer_md": answer_md,
        "submitted_at": submitted_at,
        "duration_sec": duration_sec,
    }

    if (
        (payload["quiz_id"] is None or payload["question_id"] is None)
        and "application/json" in content_type
    ):
        json_payload = await request.json()
        if not isinstance(json_payload, dict):
            raise RequestValidationError(
                [
                    {
                        "type": "dict_type",
                        "loc": ("body",),
                        "msg": "Input should be a valid dictionary",
                        "input": json_payload,
                    }
                ]
            )
        payload.update(json_payload)

    try:
        validated_request = StuSubmitAnswerRequest.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    student_id = _ensure_student_identity(current_user, validated_request.student_id)
    log = logger.bind(
        log_type="user",
        student_id=student_id,
        quiz_id=validated_request.quiz_id,
        question_id=validated_request.question_id,
    )
    log.info("学生提交答案")
    normalized_images = _normalize_upload_files(images)
    res, code, message, data = await stu_quiz_service.submit_answer(
        student_id=student_id,
        quiz_id=validated_request.quiz_id,
        question_id=validated_request.question_id,
        answer_md=validated_request.answer_md,
        images=normalized_images,
        submitted_at=validated_request.submitted_at,
        duration_sec=validated_request.duration_sec,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/submit",
    response_model=BaseResponseModel[StuSubmitQuizResponseModel],
    summary="学生提交测验",
)
async def submit_stu_quiz(
    request: StuSubmitQuizRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """学生提交整份测验，并自动触发 AI 批改。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(
        log_type="user",
        student_id=student_id,
        quiz_id=request.quiz_id,
    )
    log.info("学生提交测验")
    res, code, message, data = await stu_quiz_service.submit_quiz(
        student_id=student_id,
        quiz_id=request.quiz_id,
        submitted_at=request.submitted_at,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/answer/grading-view",
    response_model=BaseResponseModel[StuAnswerGradingViewResponseModel],
    summary="查看 AI 批改视图",
)
async def get_stu_answer_grading_view(
    request: StuAnswerGradingViewRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """查看指定答案的 AI 批改详情。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(
        log_type="user",
        student_id=student_id,
        answer_id=request.answer_id,
    )
    log.info("学生查看 AI 批改视图")
    res, code, message, data = await stu_quiz_service.get_answer_grading_view(
        student_id,
        request.answer_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}
