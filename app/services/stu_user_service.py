"""学生用户服务。"""

from fastapi import status
from sqlalchemy import func, select

from app.storage import AsyncSessionLocal
from app.storage.database_models import (
    AppUser,
    ClassRoom,
    ClassStudent,
    ClassStudentStatus,
    QuizSubmission,
    SubmissionStatus,
    StudentProfile,
)


class StuUserService:
    """处理学生个人信息相关逻辑。"""

    @staticmethod
    def _formal_submission_statuses() -> tuple[SubmissionStatus, ...]:
        return (
            SubmissionStatus.submitted,
            SubmissionStatus.grading,
            SubmissionStatus.reviewed,
        )

    async def get_profile(self, student_id: str) -> tuple[bool, int, str, dict | None]:
        """获取学生个人信息。"""
        async with AsyncSessionLocal() as session:
            try:
                student_row = (
                    await session.execute(
                        select(AppUser, StudentProfile)
                        .join(StudentProfile, StudentProfile.user_id == AppUser.id)
                        .where(AppUser.id == int(student_id))
                    )
                ).first()
                if student_row is None:
                    return False, status.HTTP_404_NOT_FOUND, "学生不存在", None

                user, profile = student_row
                class_name = (
                    (
                        await session.execute(
                            select(ClassRoom.class_name)
                            .join(ClassStudent, ClassStudent.class_id == ClassRoom.id)
                            .where(
                                ClassStudent.student_id == int(student_id),
                                ClassStudent.join_status == ClassStudentStatus.active,
                            )
                            .order_by(ClassRoom.id.desc())
                        )
                    )
                    .scalars()
                    .first()
                )

                stats_row = (
                    await session.execute(
                        select(
                            func.count(QuizSubmission.id),
                            func.coalesce(func.avg(QuizSubmission.accuracy_rate), 0),
                            func.coalesce(func.sum(QuizSubmission.answered_count), 0),
                        ).where(
                            QuizSubmission.student_id == int(student_id),
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                    )
                ).first()
                quiz_count = int(stats_row[0] or 0)
                avg_accuracy_rate = float(stats_row[1] or 0)
                answered_count = int(stats_row[2] or 0)

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取成功",
                    {
                        "student_id": str(user.id),
                        "real_name": user.real_name,
                        "class_name": class_name,
                        "student_no": profile.student_no,
                        "quiz_count": quiz_count,
                        "avg_accuracy_rate": avg_accuracy_rate,
                        "answered_count": answered_count,
                    },
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )


stu_user_service = StuUserService()
