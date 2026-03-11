"""教师端总览响应模型。"""

from pydantic import BaseModel, Field


class TEARecentQuizItemResponseModel(BaseModel):
    """最近一周测验列表项。"""

    quiz_id: int | str = Field(..., description="测验ID")
    quiz_name: str = Field(..., description="测验名称")
    class_names: list[str] = Field(default_factory=list, description="班级名称列表")
    submit_rate: float = Field(default=0, description="提交率")
    status: str = Field(..., description="状态")


class TEATypicalErrorItemResponseModel(BaseModel):
    """典型错误列表项。"""

    pattern_id: int | str = Field(..., description="典型错误ID")
    pattern_name: str = Field(..., description="典型错误名称")
    quiz_name: str | None = Field(default=None, description="对应测验名称")
    question_id: int | str | None = Field(default=None, description="对应题目ID")
    question_content: str | None = Field(default=None, description="对应题目内容")
    hit_count: int = Field(default=0, description="命中次数")


class TEADashboardOverviewResponseModel(BaseModel):
    """教师端总览响应。"""

    weekly_quiz_count: int = Field(default=0, description="本周测验数量")
    ongoing_quiz_count: int = Field(default=0, description="进行中测验数量")
    total_quiz_count: int = Field(default=0, description="总测验数量")
    total_class_count: int = Field(default=0, description="班级总数")
    total_student_count: int = Field(default=0, description="学生总数")
    total_question_count: int = Field(default=0, description="题库总量")
    weekly_new_question_count: int = Field(default=0, description="本周新增题目数量")
    average_accuracy_rate: float = Field(default=0, description="平均正确率")
    accuracy_rate_compare_last_week: float = Field(
        default=0, description="较上周平均正确率差值"
    )
    accuracy_rate_trend: str = Field(default="flat", description="up/down/flat")
    recent_quizzes: list[TEARecentQuizItemResponseModel] = Field(
        default_factory=list, description="最近一周测验列表"
    )
    typical_errors_top5: list[TEATypicalErrorItemResponseModel] = Field(
        default_factory=list, description="典型错误Top5"
    )