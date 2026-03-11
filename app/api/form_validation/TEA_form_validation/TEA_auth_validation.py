"""教师端认证请求参数校验模型。"""

from pydantic import BaseModel, Field


class TEAUsernameLoginRequest(BaseModel):
    """教师账号密码登录请求。"""

    username: str = Field(..., min_length=1, max_length=64, description="账号")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    device_id: str | None = Field(default=None, max_length=128, description="设备ID")