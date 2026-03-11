from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TEAQuizListRequest(BaseModel):
    """教师端测验列表请求。"""

    status: str | None = Field(
        default=None,
        description="测验状态：all / ongoing / completed / expired",
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        allow_values = {"all", "ongoing", "completed", "expired"}
        if value not in allow_values:
            raise ValueError("status 仅支持 all / ongoing / completed / expired")
        return value


class TEAQuizCreateRequest(BaseModel):
    """教师端创建测验请求。"""

    quiz_name: str = Field(..., min_length=1, max_length=200, description="测验名称")
    class_ids: list[int] = Field(..., min_length=1, description="班级 ID 列表")
    question_ids: list[int] = Field(..., min_length=1, description="题目 ID 列表")
    deadline_at: datetime = Field(..., description="截止时间")

    @field_validator("quiz_name")
    @classmethod
    def validate_quiz_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("测验名称不能为空")
        return value

    @field_validator("class_ids", "question_ids")
    @classmethod
    def validate_id_list(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("列表不能为空")
        unique_values = []
        existed = set()
        for item in value:
            if item <= 0:
                raise ValueError("ID 必须为正整数")
            if item not in existed:
                existed.add(item)
                unique_values.append(item)
        return unique_values