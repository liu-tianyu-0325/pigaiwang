"""教师端班级管理请求参数校验模型。"""

from pydantic import BaseModel, Field


class TEAListClassRequest(BaseModel):
    """班级列表查询请求。"""

    keyword: str | None = Field(default=None, description="班级名称关键字")


class TEACreateClassRequest(BaseModel):
    """创建班级请求。"""

    class_name: str = Field(..., min_length=1, max_length=64, description="班级名称")
    grade_name: str = Field(..., min_length=1, max_length=32, description="年级")
    remark: str | None = Field(default=None, max_length=255, description="备注")


class TEAUpdateClassRequest(BaseModel):
    """编辑班级请求。"""

    class_id: int = Field(..., description="班级ID")
    class_name: str = Field(..., min_length=1, max_length=64, description="班级名称")
    grade_name: str = Field(..., min_length=1, max_length=32, description="年级")
    remark: str | None = Field(default=None, max_length=255, description="备注")


class TEAGetClassStudentsRequest(BaseModel):
    """获取班级学生列表请求。"""

    class_id: int = Field(..., description="班级ID")


class TEAImportStudentItemRequest(BaseModel):
    """单个导入学生项。"""

    student_no: str = Field(..., min_length=1, max_length=64, description="学号")
    student_name: str = Field(..., min_length=1, max_length=64, description="姓名")
    initial_password: str = Field(
        ..., min_length=1, max_length=128, description="初始密码"
    )


class TEABatchImportStudentsRequest(BaseModel):
    """批量导入学生请求。"""

    class_id: int = Field(..., description="班级ID")
    students: list[TEAImportStudentItemRequest] = Field(
        ..., min_length=1, description="学生列表"
    )