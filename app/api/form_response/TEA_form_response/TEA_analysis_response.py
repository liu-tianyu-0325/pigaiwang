from typing import Any

from pydantic import BaseModel, Field


class TEAAnalysisBaseResponse(BaseModel):
    """教师端分析基础响应。"""

    res: bool = Field(..., description="是否成功")
    code: int = Field(..., description="业务码")
    message: str = Field(..., description="提示信息")
    data: Any = Field(default=None, description="数据")