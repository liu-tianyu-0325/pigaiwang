from __future__ import annotations

"""数据库模型定义文件。

保留当前模板依赖的管理员模型，并新增按业务设计的题库/测验相关表结构。
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.base import Base, register_model


class TimeMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )


class UserRole(str, Enum):
    teacher = "teacher"
    student = "student"
    admin = "admin"


class UserStatus(int, Enum):
    disabled = 0
    enabled = 1


class ClassStudentStatus(str, Enum):
    active = "active"
    left = "left"
    disabled = "disabled"


class ImportStatus(str, Enum):
    processing = "processing"
    finished = "finished"
    partial_failed = "partial_failed"
    failed = "failed"


class ImportItemResultStatus(str, Enum):
    success = "success"
    failed = "failed"
    duplicate = "duplicate"


class QuestionType(str, Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    judge = "judge"
    fill_blank = "fill_blank"
    short_answer = "short_answer"
    proof = "proof"
    calculation = "calculation"


class QuestionStatus(str, Enum):
    draft = "draft"
    active = "active"
    disabled = "disabled"


class QuizStatus(str, Enum):
    draft = "draft"
    ongoing = "ongoing"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"


class SubmissionStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    grading = "grading"
    reviewed = "reviewed"
    expired = "expired"


class GradingStatus(str, Enum):
    pending = "pending"
    grading = "grading"
    graded = "graded"


class ResultStatus(str, Enum):
    correct = "correct"
    wrong = "wrong"
    partial = "partial"
    unanswered = "unanswered"


class ReviewActionType(str, Enum):
    confirm = "confirm"
    modify_score = "modify_score"
    modify_result = "modify_result"
    comment = "comment"


@register_model
class AppUserModel(TimeMixin, Base):
    __tablename__ = "app_user"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role", native_enum=False, length=20),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=UserStatus.enabled.value, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


@register_model
class StudentProfileModel(TimeMixin, Base):
    __tablename__ = "student_profile"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, unique=True, index=True)
    student_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    gender: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


@register_model
class TeacherProfileModel(TimeMixin, Base):
    __tablename__ = "teacher_profile"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, unique=True, index=True)
    subject_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


@register_model
class ClassRoomModel(TimeMixin, Base):
    __tablename__ = "class_room"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    grade_name: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    teacher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    class_code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    student_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finished_quiz_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


@register_model
class ClassStudentModel(CreatedAtMixin, Base):
    __tablename__ = "class_student"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_student"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("class_room.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    join_status: Mapped[ClassStudentStatus] = mapped_column(SqlEnum(ClassStudentStatus, name="class_student_status", native_enum=False, length=20), default=ClassStudentStatus.active, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


@register_model
class StudentImportBatchModel(CreatedAtMixin, Base):
    __tablename__ = "student_import_batch"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("class_room.id"), nullable=False, index=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_status: Mapped[ImportStatus] = mapped_column(SqlEnum(ImportStatus, name="import_status", native_enum=False, length=20), default=ImportStatus.processing, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


@register_model
class StudentImportBatchItemModel(CreatedAtMixin, Base):
    __tablename__ = "student_import_batch_item"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student_import_batch.id"), nullable=False, index=True)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    student_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    student_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_status: Mapped[ImportItemResultStatus] = mapped_column(SqlEnum(ImportItemResultStatus, name="import_item_result_status", native_enum=False, length=20), default=ImportItemResultStatus.success, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=True)


@register_model
class QuestionModel(TimeMixin, Base):
    __tablename__ = "question"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[QuestionType] = mapped_column(SqlEnum(QuestionType, name="question_type", native_enum=False, length=32), nullable=False)
    status: Mapped[QuestionStatus] = mapped_column(SqlEnum(QuestionStatus, name="question_status", native_enum=False, length=20), default=QuestionStatus.active, nullable=False)


@register_model
class QuestionImageModel(CreatedAtMixin, Base):
    __tablename__ = "question_image"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


@register_model
class TagModel(CreatedAtMixin, Base):
    __tablename__ = "tag"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tag_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=True)


@register_model
class QuestionTagRelModel(Base):
    __tablename__ = "question_tag_rel"
    __table_args__ = (UniqueConstraint("question_id", "tag_id", name="uq_question_tag_rel"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tag.id"), nullable=False, index=True)


@register_model
class QuizModel(TimeMixin, Base):
    __tablename__ = "quiz"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_score: Mapped[float] = mapped_column(default=100, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    status: Mapped[QuizStatus] = mapped_column(SqlEnum(QuizStatus, name="quiz_status", native_enum=False, length=20), default=QuizStatus.draft, nullable=False)


@register_model
class QuizClassRelModel(CreatedAtMixin, Base):
    __tablename__ = "quiz_class_rel"
    __table_args__ = (UniqueConstraint("quiz_id", "class_id", name="uq_quiz_class_rel"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quiz.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("class_room.id"), nullable=False, index=True)
    target_student_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_student_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submit_rate: Mapped[float] = mapped_column(default=0, nullable=False)
    avg_score: Mapped[float] = mapped_column(default=0, nullable=False)
    avg_accuracy_rate: Mapped[float] = mapped_column(default=0, nullable=False)


@register_model
class QuizQuestionModel(Base):
    __tablename__ = "quiz_question"
    __table_args__ = (UniqueConstraint("quiz_id", "question_id", name="uq_quiz_question"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quiz.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question.id"), nullable=False, index=True)
    sort_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    score: Mapped[float] = mapped_column(default=0, nullable=False)


@register_model
class QuizSubmissionModel(TimeMixin, Base):
    __tablename__ = "quiz_submission"
    __table_args__ = (UniqueConstraint("quiz_id", "student_id", name="uq_quiz_submission"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quiz.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("class_room.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    status: Mapped[SubmissionStatus] = mapped_column(SqlEnum(SubmissionStatus, name="submission_status", native_enum=False, length=20), default=SubmissionStatus.not_started, nullable=False, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_score: Mapped[float] = mapped_column(default=0, nullable=False)
    accuracy_rate: Mapped[float] = mapped_column(default=0, nullable=False)
    total_duration_sec: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


@register_model
class SubmissionAnswerModel(TimeMixin, Base):
    __tablename__ = "submission_answer"
    __table_args__ = (UniqueConstraint("submission_id", "question_id", name="uq_submission_answer"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quiz_submission.id"), nullable=False, index=True)
    quiz_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quiz.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question.id"), nullable=False, index=True)
    sort_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    answer_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_answered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grading_status: Mapped[GradingStatus] = mapped_column(SqlEnum(GradingStatus, name="grading_status", native_enum=False, length=20), default=GradingStatus.pending, nullable=False, index=True)
    result_status: Mapped[ResultStatus] = mapped_column(SqlEnum(ResultStatus, name="result_status", native_enum=False, length=20), default=ResultStatus.unanswered, nullable=False, index=True)
    ai_score: Mapped[float] = mapped_column(default=0, nullable=False)
    final_score: Mapped[float] = mapped_column(default=0, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)


@register_model
class SubmissionAnswerImageModel(CreatedAtMixin, Base):
    __tablename__ = "submission_answer_image"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("submission_answer.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


@register_model
class AIGradingLogModel(CreatedAtMixin, Base):
    __tablename__ = "ai_grading_log"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("submission_answer.id"), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_score: Mapped[float] = mapped_column(default=0, nullable=False)


@register_model
class AnswerReviewLogModel(CreatedAtMixin, Base):
    __tablename__ = "answer_review_log"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("submission_answer.id"), nullable=False, index=True)
    reviewer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), nullable=False, index=True)
    action_type: Mapped[ReviewActionType] = mapped_column(SqlEnum(ReviewActionType, name="review_action_type", native_enum=False, length=20), nullable=False)
    old_result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_score: Mapped[float | None] = mapped_column(nullable=True)
    new_score: Mapped[float | None] = mapped_column(nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)


@register_model
class TypicalErrorPatternModel(TimeMixin, Base):
    __tablename__ = "typical_error_pattern"
    __table_args__ = (UniqueConstraint("question_id", "pattern_name", name="uq_typical_error_pattern"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question.id"), nullable=False, index=True)
    pattern_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pattern_desc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    suggestion_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


@register_model
class AnswerTypicalErrorRelModel(CreatedAtMixin, Base):
    __tablename__ = "answer_typical_error_rel"
    __table_args__ = (UniqueConstraint("answer_id", "pattern_id", name="uq_answer_typical_error_rel"),)

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("submission_answer.id"), nullable=False, index=True)
    pattern_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("typical_error_pattern.id"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


AppUser = AppUserModel
StudentProfile = StudentProfileModel
TeacherProfile = TeacherProfileModel
ClassRoom = ClassRoomModel
ClassStudent = ClassStudentModel
StudentImportBatch = StudentImportBatchModel
StudentImportBatchItem = StudentImportBatchItemModel
Question = QuestionModel
QuestionImage = QuestionImageModel
Tag = TagModel
QuestionTagRel = QuestionTagRelModel
Quiz = QuizModel
QuizClassRel = QuizClassRelModel
QuizQuestion = QuizQuestionModel
QuizSubmission = QuizSubmissionModel
SubmissionAnswer = SubmissionAnswerModel
SubmissionAnswerImage = SubmissionAnswerImageModel
AIGradingLog = AIGradingLogModel
AnswerReviewLog = AnswerReviewLogModel
TypicalErrorPattern = TypicalErrorPatternModel
AnswerTypicalErrorRel = AnswerTypicalErrorRelModel
