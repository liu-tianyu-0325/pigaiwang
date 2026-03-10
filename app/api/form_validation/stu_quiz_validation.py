"""学生测验请求校验模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.form_validation.user_validation import strip_strings


class StuQuizListRequest(BaseModel):
    """学生测验列表请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    status: str = Field(default="全部", description="状态：全部、进行中、已完成、过期")

    @field_validator("student_id", "status", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        mapping = {
            "all": "全部",
            "全部": "全部",
            "ongoing": "进行中",
            "进行中": "进行中",
            "completed": "已完成",
            "已完成": "已完成",
            "expired": "过期",
            "过期": "过期",
        }
        normalized = mapping.get(value)
        if normalized is None:
            raise ValueError("状态仅支持：全部、进行中、已完成、过期")
        return normalized

    model_config = ConfigDict(from_attributes=True)


class StuQuizDetailRequest(BaseModel):
    """学生测验详情请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    quiz_id: str = Field(min_length=1, max_length=32, description="测验ID")

    @field_validator("student_id", "quiz_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuQuestionDetailRequest(BaseModel):
    """学生题目详情请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    question_id: str = Field(min_length=1, max_length=32, description="题目ID")
    quiz_id: str | None = Field(default=None, max_length=32, description="测验ID，可选")

    @field_validator("student_id", "question_id", "quiz_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuSubmitAnswerRequest(BaseModel):
    """学生提交答案请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    quiz_id: str = Field(min_length=1, max_length=32, description="测验ID")
    question_id: str = Field(min_length=1, max_length=32, description="题目ID")
    answer_md: str | None = Field(default=None, description="Markdown答案文本")
    image_urls: list[str] = Field(default_factory=list, description="答案图片地址列表")
    submitted_at: datetime | None = Field(
        default=None, description="提交时间，不传则使用当前时间"
    )
    duration_sec: int = Field(default=0, ge=0, description="用时，单位秒")

    @field_validator("student_id", "quiz_id", "question_id", "answer_md", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuTriggerAnswerGradingRequest(BaseModel):
    """学生手动触发 AI 批改请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    answer_id: str = Field(min_length=1, max_length=32, description="答案ID")

    @field_validator("student_id", "answer_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuAnswerGradingViewRequest(BaseModel):
    """学生查看 AI 批改视图请求。"""

    student_id: str = Field(min_length=1, max_length=32, description="学生用户ID")
    answer_id: str = Field(min_length=1, max_length=32, description="答案ID")

    @field_validator("student_id", "answer_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)
