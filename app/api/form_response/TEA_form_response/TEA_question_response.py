"""教师端习题管理响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class TEAQuestionCountResponseModel(BaseModel):
    """题目总数响应。"""

    total_question_count: int = Field(..., description="题目总数")


class TEATagItemResponseModel(BaseModel):
    """标签项响应。"""

    tag_id: int | str = Field(..., description="标签ID")
    tag_name: str = Field(..., description="标签名称")


class TEAQuestionImageItemResponseModel(BaseModel):
    """题目图片项响应。"""

    image_id: int | str = Field(..., description="图片ID")
    image_url: str = Field(..., description="图片地址")
    sort_no: int = Field(..., description="排序号")


class TEAQuestionDetailResponseModel(BaseModel):
    """题目详情响应。"""

    question_id: int | str = Field(..., description="题目ID")
    content_md: str | None = Field(default=None, description="题目内容")
    reference_answer: str | None = Field(default=None, description="参考答案")
    question_type: str = Field(..., description="题目类型")
    status: str = Field(..., description="题目状态")
    tags: list[TEATagItemResponseModel] = Field(default_factory=list, description="标签列表")
    images: list[TEAQuestionImageItemResponseModel] = Field(default_factory=list, description="图片列表")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class TEAQuestionSearchItemResponseModel(BaseModel):
    """题目搜索列表项响应。"""

    question_id: int | str = Field(..., description="题目ID")
    content_md: str | None = Field(default=None, description="题目内容")
    reference_answer: str | None = Field(default=None, description="参考答案")
    question_type: str = Field(..., description="题目类型")
    status: str = Field(..., description="题目状态")
    tags: list[TEATagItemResponseModel] = Field(default_factory=list, description="标签列表")
    images: list[TEAQuestionImageItemResponseModel] = Field(default_factory=list, description="图片列表")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class TEAQuestionSearchResponseModel(BaseModel):
    """题目搜索响应。"""

    total: int = Field(..., description="总数量")
    page: int = Field(..., description="页码")
    page_size: int = Field(..., description="每页数量")
    items: list[TEAQuestionSearchItemResponseModel] = Field(
        default_factory=list, description="题目列表"
    )