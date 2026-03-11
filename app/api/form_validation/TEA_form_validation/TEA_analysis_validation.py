from pydantic import BaseModel, Field


class TEAQuizAnalysisSummaryRequest(BaseModel):
    """测验分析总览请求。"""

    pass


class TEAQuizNameListRequest(BaseModel):
    """测验名称列表请求。"""

    pass


class TEAQuizClassStatsRequest(BaseModel):
    """某测验下班级统计请求。"""

    quiz_id: int = Field(..., gt=0, description="测验 ID")


class TEAQuizClassQuestionStatsRequest(BaseModel):
    """某测验某班级题目统计请求。"""

    quiz_id: int = Field(..., gt=0, description="测验 ID")
    class_id: int = Field(..., gt=0, description="班级 ID")


class TEAQuizStudentAnswerListRequest(BaseModel):
    """学生作答列表请求。"""

    quiz_id: int = Field(..., gt=0, description="测验 ID")
    class_id: int = Field(..., gt=0, description="班级 ID")
    question_id: int | None = Field(default=None, gt=0, description="题目 ID，可选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")


class TEAQuizStudentAnswerDetailRequest(BaseModel):
    """学生作答详情请求。"""

    submission_id: int = Field(..., gt=0, description="提交记录 ID")