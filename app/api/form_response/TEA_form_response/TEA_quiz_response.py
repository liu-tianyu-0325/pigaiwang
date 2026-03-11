from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TEAQuizBaseResponse(BaseModel):
    """教师端测验基础响应。"""

    res: bool = Field(..., description="是否成功")
    code: int = Field(..., description="业务码")
    message: str = Field(..., description="提示信息")
    data: Any = Field(default=None, description="数据")


class TEAQuizItemResponse(BaseModel):
    quiz_id: int
    quiz_name: str
    class_list: list[dict]
    question_count: int
    deadline_at: datetime | None
    status: str
    submit_rate: float
    average_score: float


class TEAQuizCreateDataResponse(BaseModel):
    quiz_id: int
    quiz_name: str
    class_ids: list[int]
    question_ids: list[int]
    deadline_at: datetime | None