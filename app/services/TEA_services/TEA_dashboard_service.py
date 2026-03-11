"""教师端总览业务逻辑。"""

from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy import and_, func, select

from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    ClassRoom,
    ClassStudent,
    ClassStudentStatus,
    Question,
    Quiz,
    QuizClassRel,
    QuizQuestion,
    QuizStatus,
    QuizSubmission,
    SubmissionStatus,
    TypicalErrorPattern,
)


class TEADashboardService:
    """教师端总览服务。"""

    @staticmethod
    def _formal_submission_statuses() -> tuple[SubmissionStatus, ...]:
        return (
            SubmissionStatus.submitted,
            SubmissionStatus.grading,
            SubmissionStatus.reviewed,
        )

    async def get_overview(
        self,
        teacher_id: int | str,
    ) -> tuple[bool, int, str, dict | None]:
        """获取教师端首页总览。"""
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)

                now = datetime.utcnow()
                week_start = now - timedelta(days=now.weekday())
                week_start = datetime(
                    week_start.year,
                    week_start.month,
                    week_start.day,
                    0,
                    0,
                    0,
                )
                week_end = week_start + timedelta(days=7)

                last_week_start = week_start - timedelta(days=7)
                last_week_end = week_start

                weekly_quiz_count = await session.scalar(
                    select(func.count(Quiz.id)).where(
                        and_(
                            Quiz.creator_id == teacher_id,
                            Quiz.created_at >= week_start,
                            Quiz.created_at < week_end,
                        )
                    )
                )

                ongoing_quiz_count = await session.scalar(
                    select(func.count(Quiz.id)).where(
                        and_(
                            Quiz.creator_id == teacher_id,
                            Quiz.status == QuizStatus.ongoing,
                        )
                    )
                )

                total_quiz_count = await session.scalar(
                    select(func.count(Quiz.id)).where(Quiz.creator_id == teacher_id)
                )

                total_class_count = await session.scalar(
                    select(func.count(ClassRoom.id)).where(
                        and_(
                            ClassRoom.teacher_id == teacher_id,
                            ClassRoom.status == 1,
                        )
                    )
                )

                total_student_count = await session.scalar(
                    select(func.count(ClassStudent.id))
                    .select_from(ClassStudent)
                    .join(ClassRoom, ClassRoom.id == ClassStudent.class_id)
                    .where(
                        and_(
                            ClassRoom.teacher_id == teacher_id,
                            ClassRoom.status == 1,
                        )
                    )
                )

                total_question_count = await session.scalar(
                    select(func.count(Question.id)).where(Question.creator_id == teacher_id)
                )

                weekly_new_question_count = await session.scalar(
                    select(func.count(Question.id)).where(
                        and_(
                            Question.creator_id == teacher_id,
                            Question.created_at >= week_start,
                            Question.created_at < week_end,
                        )
                    )
                )

                current_week_avg_accuracy = await session.scalar(
                    select(func.coalesce(func.avg(QuizSubmission.accuracy_rate), 0))
                    .select_from(QuizSubmission)
                    .join(Quiz, Quiz.id == QuizSubmission.quiz_id)
                    .where(
                        and_(
                            Quiz.creator_id == teacher_id,
                            QuizSubmission.submitted_at >= week_start,
                            QuizSubmission.submitted_at < week_end,
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                    )
                )

                last_week_avg_accuracy = await session.scalar(
                    select(func.coalesce(func.avg(QuizSubmission.accuracy_rate), 0))
                    .select_from(QuizSubmission)
                    .join(Quiz, Quiz.id == QuizSubmission.quiz_id)
                    .where(
                        and_(
                            Quiz.creator_id == teacher_id,
                            QuizSubmission.submitted_at >= last_week_start,
                            QuizSubmission.submitted_at < last_week_end,
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                    )
                )

                accuracy_rate_compare_last_week = float(
                    (current_week_avg_accuracy or 0) - (last_week_avg_accuracy or 0)
                )

                if accuracy_rate_compare_last_week > 0:
                    trend = "up"
                elif accuracy_rate_compare_last_week < 0:
                    trend = "down"
                else:
                    trend = "flat"

                recent_quiz_stmt = (
                    select(
                        Quiz.id,
                        Quiz.quiz_name,
                        Quiz.status,
                    )
                    .where(
                        and_(
                            Quiz.creator_id == teacher_id,
                            Quiz.created_at >= week_start,
                            Quiz.created_at < week_end,
                        )
                    )
                    .group_by(Quiz.id, Quiz.quiz_name, Quiz.status, Quiz.created_at)
                    .order_by(Quiz.created_at.desc())
                    .limit(10)
                )
                recent_quiz_result = await session.execute(recent_quiz_stmt)
                recent_quiz_rows = recent_quiz_result.all()

                recent_quizzes: list[dict] = []
                for row in recent_quiz_rows:
                    class_count_rows = await session.execute(
                        select(
                            QuizClassRel.class_id,
                            func.count(ClassStudent.id).label("student_count"),
                        )
                        .select_from(QuizClassRel)
                        .join(ClassRoom, ClassRoom.id == QuizClassRel.class_id)
                        .outerjoin(
                            ClassStudent,
                            and_(
                                ClassStudent.class_id == QuizClassRel.class_id,
                                ClassStudent.join_status == ClassStudentStatus.active,
                            ),
                        )
                        .where(QuizClassRel.quiz_id == row.id)
                        .group_by(QuizClassRel.class_id)
                    )
                    class_count_map = {
                        int(class_id): int(student_count or 0)
                        for class_id, student_count in class_count_rows.all()
                        if class_id is not None
                    }

                    submitted_count_rows = await session.execute(
                        select(
                            QuizSubmission.class_id,
                            func.count(func.distinct(QuizSubmission.student_id)).label(
                                "submitted_count"
                            ),
                        )
                        .where(
                            QuizSubmission.quiz_id == row.id,
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                        .group_by(QuizSubmission.class_id)
                    )
                    submitted_count_map = {
                        int(class_id): int(submitted_count or 0)
                        for class_id, submitted_count in submitted_count_rows.all()
                        if class_id is not None
                    }

                    total_student_count = sum(class_count_map.values())
                    submitted_student_count = sum(submitted_count_map.values())
                    submit_rate = (
                        round(submitted_student_count / total_student_count * 100, 2)
                        if total_student_count > 0
                        else 0.0
                    )

                    class_name_stmt = (
                        select(ClassRoom.class_name)
                        .select_from(QuizClassRel)
                        .join(ClassRoom, ClassRoom.id == QuizClassRel.class_id)
                        .where(QuizClassRel.quiz_id == row.id)
                    )
                    class_name_result = await session.execute(class_name_stmt)
                    class_names = [name for (name,) in class_name_result.all()]

                    recent_quizzes.append(
                        {
                            "quiz_id": row.id,
                            "quiz_name": row.quiz_name,
                            "class_names": class_names,
                            "submit_rate": submit_rate,
                            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                        }
                    )

                typical_error_stmt = (
                    select(
                        TypicalErrorPattern.id,
                        TypicalErrorPattern.pattern_name,
                        TypicalErrorPattern.question_id,
                        TypicalErrorPattern.hit_count,
                        Question.content_md,
                    )
                    .select_from(TypicalErrorPattern)
                    .join(Question, Question.id == TypicalErrorPattern.question_id)
                    .where(Question.creator_id == teacher_id)
                    .order_by(
                        TypicalErrorPattern.hit_count.desc(),
                        TypicalErrorPattern.id.desc(),
                    )
                    .limit(5)
                )
                typical_error_result = await session.execute(typical_error_stmt)
                typical_error_rows = typical_error_result.all()

                typical_errors_top5: list[dict] = []
                for row in typical_error_rows:
                    quiz_name_stmt = (
                        select(Quiz.quiz_name)
                        .select_from(QuizQuestion)
                        .join(Quiz, Quiz.id == QuizQuestion.quiz_id)
                        .where(
                            and_(
                                QuizQuestion.question_id == row.question_id,
                                Quiz.creator_id == teacher_id,
                            )
                        )
                        .order_by(Quiz.id.desc())
                        .limit(1)
                    )
                    quiz_name_result = await session.execute(quiz_name_stmt)
                    quiz_name = quiz_name_result.scalar_one_or_none()

                    typical_errors_top5.append(
                        {
                            "pattern_id": row.id,
                            "pattern_name": row.pattern_name,
                            "quiz_name": quiz_name,
                            "question_id": row.question_id,
                            "question_content": row.content_md,
                            "hit_count": int(row.hit_count or 0),
                        }
                    )

                data = {
                    "weekly_quiz_count": int(weekly_quiz_count or 0),
                    "ongoing_quiz_count": int(ongoing_quiz_count or 0),
                    "total_quiz_count": int(total_quiz_count or 0),
                    "total_class_count": int(total_class_count or 0),
                    "total_student_count": int(total_student_count or 0),
                    "total_question_count": int(total_question_count or 0),
                    "weekly_new_question_count": int(weekly_new_question_count or 0),
                    "average_accuracy_rate": float(current_week_avg_accuracy or 0),
                    "accuracy_rate_compare_last_week": accuracy_rate_compare_last_week,
                    "accuracy_rate_trend": trend,
                    "recent_quizzes": recent_quizzes,
                    "typical_errors_top5": typical_errors_top5,
                }
                return True, status.HTTP_200_OK, "获取教师端总览成功", data

            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取教师端总览失败，请稍后重试" + str(e),
                    None,
                )


TEA_dashboard_service = TEADashboardService()