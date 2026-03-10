"""学生认证响应模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.auth.jwt_manager import TokenInfo


class StuLoginResponseModel(BaseModel):
    """学生登录成功后的响应数据。"""

    user_id: str = Field(description="学生用户ID")
    username: str = Field(description="学生用户名")
    real_name: str = Field(description="学生姓名")
    role: str = Field(description="用户角色")
    student_no: str = Field(description="学号")
    token_info: TokenInfo = Field(description="JWT 令牌信息")

    model_config = ConfigDict(from_attributes=True)


class StuRegisterResponseModel(BaseModel):
    """学生注册成功后的响应数据。"""

    user_id: str = Field(description="学生用户ID")
    username: str = Field(description="学生用户名")
    real_name: str = Field(description="学生姓名")
    student_no: str = Field(description="学号")

    model_config = ConfigDict(from_attributes=True)


class StuProfileResponseModel(BaseModel):
    """学生个人信息响应数据。"""

    student_id: str = Field(description="学生用户ID")
    real_name: str = Field(description="学生姓名")
    class_name: str | None = Field(default=None, description="班级名称")
    student_no: str = Field(description="学号")
    quiz_count: int = Field(description="已参与测验数量")
    avg_accuracy_rate: float = Field(description="平均正确率")
    answered_count: int = Field(description="已答题数")

    model_config = ConfigDict(from_attributes=True)


class StuLogoutResponseModel(BaseModel):
    """学生退出登录响应数据。"""

    student_id: str = Field(description="学生用户ID")
    logged_out: bool = Field(description="是否成功退出")

    model_config = ConfigDict(from_attributes=True)
