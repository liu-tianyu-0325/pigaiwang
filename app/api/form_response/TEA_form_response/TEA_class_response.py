"""教师端班级管理响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class TEAClassListItemResponseModel(BaseModel):
    """班级列表项响应。"""

    class_id: int | str = Field(..., description="班级ID")
    class_name: str = Field(..., description="班级名称")
    grade_name: str = Field(..., description="年级")
    student_count: int = Field(..., description="学生人数")
    finished_quiz_count: int = Field(..., description="已完成测验人数")
    remark: str | None = Field(default=None, description="备注")


class TEAClassDetailResponseModel(BaseModel):
    """班级详情响应。"""

    class_id: int | str = Field(..., description="班级ID")
    class_name: str = Field(..., description="班级名称")
    grade_name: str = Field(..., description="年级")
    student_count: int = Field(default=0, description="学生人数")
    finished_quiz_count: int = Field(default=0, description="已完成测验人数")
    remark: str | None = Field(default=None, description="备注")


class TEAClassStudentListItemResponseModel(BaseModel):
    """班级学生列表项响应。"""

    student_id: int | str = Field(..., description="学生ID")
    student_no: str = Field(..., description="学号")
    student_name: str = Field(..., description="姓名")
    participated_quiz_count: int = Field(default=0, description="已参与测验数量")
    average_accuracy_rate: float = Field(default=0, description="平均准确率")
    recent_submitted_at: datetime | None = Field(default=None, description="最近提交时间")


class TEAClassImportStudentsResponseModel(BaseModel):
    """批量导入学生响应。"""

    batch_no: str = Field(..., description="导入批次号")
    total_count: int = Field(..., description="总数量")
    success_count: int = Field(..., description="成功数量")
    fail_count: int = Field(..., description="失败数量")