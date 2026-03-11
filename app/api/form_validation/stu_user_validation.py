"""学生认证请求校验模型。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.form_validation.user_validation import strip_strings


class StuLoginByStudentNoPasswordRequest(BaseModel):
    """学生学号密码登录请求。"""

    student_no: str = Field(min_length=1, max_length=64, description="学生学号")
    password: str = Field(min_length=1, max_length=128, description="登录密码")

    @field_validator("student_no", "password", mode="before")
    @classmethod
    def strip_common_whitespace(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuRegisterByStudentNoRequest(BaseModel):
    """学生学号注册请求。"""

    student_no: str = Field(min_length=1, max_length=64, description="学生学号")
    real_name: str = Field(min_length=1, max_length=64, description="学生姓名")
    password: str = Field(min_length=8, max_length=128, description="登录密码")
    username: str | None = Field(
        default=None, max_length=64, description="用户名，默认等于学号"
    )
    mobile: str | None = Field(default=None, max_length=20, description="手机号")
    email: str | None = Field(default=None, max_length=128, description="邮箱")
    gender: int | None = Field(default=None, description="性别")
    remark: str | None = Field(default=None, max_length=255, description="备注")

    @field_validator(
        "student_no",
        "real_name",
        "password",
        "username",
        "mobile",
        "email",
        "remark",
        mode="before",
    )
    @classmethod
    def strip_register_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuProfileRequest(BaseModel):
    """学生个人信息请求。"""

    student_id: str | None = Field(
        default=None,
        max_length=32,
        description="学生用户ID（兼容保留，后端仍按当前登录学生处理）",
    )

    @field_validator("student_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)


class StuLogoutRequest(BaseModel):
    """学生退出登录请求。"""

    student_id: str | None = Field(
        default=None,
        max_length=32,
        description="学生用户ID（兼容保留，后端仍按当前登录学生处理）",
    )

    @field_validator("student_id", mode="before")
    @classmethod
    def strip_common_fields(cls, value: Any) -> Any:
        return strip_strings(value)

    model_config = ConfigDict(from_attributes=True)
