"""教师端习题管理请求参数校验模型。"""

from pydantic import BaseModel, Field


class TEACreateTagRequest(BaseModel):
    """新增标签请求。"""

    tag_name: str = Field(..., min_length=1, max_length=64, description="标签名称")


class TEADeleteTagRequest(BaseModel):
    """删除标签请求。"""

    tag_id: int = Field(..., description="标签ID")


class TEADeleteQuestionRequest(BaseModel):
    """删除题目请求。"""

    question_id: int = Field(..., description="题目ID")


class TEAGetQuestionDetailRequest(BaseModel):
    """获取题目详情请求。"""

    question_id: int = Field(..., description="题目ID")


class TEAQuestionSearchRequest(BaseModel):
    """题目搜索请求。"""

    keyword: str | None = Field(default=None, description="题目内容关键字")
    tag_ids: list[int] | None = Field(default=None, description="标签ID列表")
    status: str | None = Field(default=None, description="题目状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")