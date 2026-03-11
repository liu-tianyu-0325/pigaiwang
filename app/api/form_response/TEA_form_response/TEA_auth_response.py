"""教师端认证响应模型。"""

from pydantic import BaseModel, Field


class TEATokenInfoResponseModel(BaseModel):
    """教师登录 token 信息响应。"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期秒数")


class TEALoginResponseModel(BaseModel):
    """教师登录响应。"""

    user_id: int | str = Field(..., description="用户ID")
    username: str = Field(..., description="账号")
    real_name: str = Field(..., description="姓名")
    role: str = Field(..., description="角色")
    subject_name: str | None = Field(default=None, description="学科")
    title_name: str | None = Field(default=None, description="职称")
    token_info: TEATokenInfoResponseModel = Field(..., description="登录令牌信息")