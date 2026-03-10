"""学生测验响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StuQuizListItemResponseModel(BaseModel):
    """学生测验列表项。"""

    quiz_id: str = Field(description="测验ID")
    quiz_name: str = Field(description="测验名称")
    question_count: int = Field(description="题目数量")
    correct_count: int = Field(description="正确数量")
    status: str = Field(description="测验状态")
    due_at: datetime = Field(description="截止日期")
    score: float = Field(description="得分")
    submitted_at: datetime | None = Field(default=None, description="提交时间")

    model_config = ConfigDict(from_attributes=True)


class StuQuizListResponseModel(BaseModel):
    """学生测验列表响应数据。"""

    total: int = Field(description="测验总数")
    items: list[StuQuizListItemResponseModel] = Field(description="测验列表")

    model_config = ConfigDict(from_attributes=True)


class StuQuizQuestionItemResponseModel(BaseModel):
    """学生测验详情中的题目项。"""

    question_id: str = Field(description="题目ID")
    question: str | None = Field(default=None, description="题目内容")
    grading_status: str = Field(description="题目批改状态")
    result_status: str = Field(description="正确与否")
    is_answered: bool = Field(description="是否作答")

    model_config = ConfigDict(from_attributes=True)


class StuQuizDetailResponseModel(BaseModel):
    """学生测验详情响应。"""

    quiz_id: str = Field(description="测验ID")
    quiz_name: str = Field(description="测验名称")
    class_name: str | None = Field(default=None, description="学生班级")
    questions: list[StuQuizQuestionItemResponseModel] = Field(description="题目列表")

    model_config = ConfigDict(from_attributes=True)


class StuTypicalErrorItemResponseModel(BaseModel):
    """典型错误信息项。"""

    pattern_name: str = Field(description="典型错误名称")
    pattern_desc: str | None = Field(default=None, description="典型错误描述")
    suggestion_text: str | None = Field(default=None, description="建议文本")
    is_primary: bool = Field(description="是否主错因")

    model_config = ConfigDict(from_attributes=True)


class StuQuestionDetailResponseModel(BaseModel):
    """学生题目详情响应。"""

    answer_id: str | None = Field(default=None, description="答案ID")
    question_id: str = Field(description="题目ID")
    question: str | None = Field(default=None, description="题目内容")
    reference_answer: str | None = Field(default=None, description="参考答案")
    my_answer: str | None = Field(default=None, description="我的答案")
    duration_sec: int = Field(description="用时，单位秒")
    submitted_at: datetime | None = Field(default=None, description="提交时间")
    ai_score: float = Field(default=0, description="AI评分")
    final_score: float = Field(default=0, description="最终得分")
    ai_feedback: str | None = Field(default=None, description="AI批改结果")
    teacher_feedback: str | None = Field(default=None, description="教师反馈")
    grading_status: str = Field(description="题目批改状态")
    result_status: str = Field(description="正确与否")
    is_answered: bool = Field(description="是否作答")
    image_urls: list[str] = Field(default_factory=list, description="答案图片列表")
    typical_errors: list[StuTypicalErrorItemResponseModel] = Field(
        default_factory=list, description="典型错误信息"
    )

    model_config = ConfigDict(from_attributes=True)


class StuSubmitAnswerResponseModel(BaseModel):
    """学生提交答案响应。"""

    submission_id: str = Field(description="测验提交ID")
    answer_id: str = Field(description="答案ID")
    answered_count: int = Field(description="已答题数量")
    grading_status: str = Field(description="答案批改状态")
    submission_status: str = Field(description="测验提交状态")
    submitted_at: datetime = Field(description="答案提交时间")

    model_config = ConfigDict(from_attributes=True)


class StuTriggerAnswerGradingResponseModel(BaseModel):
    """学生手动触发 AI 批改响应。"""

    answer_id: str = Field(description="答案ID")
    grading_status: str = Field(description="答案批改状态")

    model_config = ConfigDict(from_attributes=True)


class StuAnswerGradingViewResponseModel(BaseModel):
    """学生查看 AI 批改视图响应。"""

    answer_id: str = Field(description="答案ID")
    quiz_id: str = Field(description="测验ID")
    question_id: str = Field(description="题目ID")
    question: str | None = Field(default=None, description="题目内容")
    reference_answer: str | None = Field(default=None, description="参考答案")
    my_answer: str | None = Field(default=None, description="我的答案")
    image_urls: list[str] = Field(default_factory=list, description="答案图片列表")
    submitted_at: datetime | None = Field(default=None, description="提交时间")
    grading_status: str = Field(description="批改状态")
    result_status: str = Field(description="结果状态")
    ai_score: float = Field(default=0, description="AI评分")
    final_score: float = Field(default=0, description="最终得分")
    ai_feedback: str | None = Field(default=None, description="AI反馈")
    model_name: str | None = Field(default=None, description="批改模型名")
    ai_result_status: str | None = Field(default=None, description="AI原始结论")

    model_config = ConfigDict(from_attributes=True)
