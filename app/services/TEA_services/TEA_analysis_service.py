from datetime import datetime
from typing import Any

from fastapi import status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time_ import time_now_naive, to_naive_beijing
from app.configs import base_configs
from app.core import s3_client
from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    AnswerTypicalErrorRel,
    AppUser,
    ClassRoom,
    ClassStudent,
    ClassStudentStatus,
    GradingStatus,
    Question,
    QuestionImage,
    Quiz,
    QuizClassRel,
    QuizQuestion,
    QuizSubmission,
    ResultStatus,
    StudentProfile,
    SubmissionAnswer,
    SubmissionAnswerImage,
    SubmissionStatus,
    TypicalErrorPattern,
)


class TEAAnalysisService:
    """教师端测验分析业务逻辑。"""

    @staticmethod
    def _get_image_bucket_name() -> str:
        candidate_attr_names = [
            "QUESTION_IMAGE_BUCKET",
            "QUESTION_S3_BUCKET",
            "S3_BUCKET_NAME",
            "S3_BUCKET",
            "RUSTFS_BUCKET",
        ]
        for attr_name in candidate_attr_names:
            bucket_name = getattr(base_configs, attr_name, None)
            if bucket_name:
                return str(bucket_name)
        raise ValueError("未找到图片桶配置，请补充 QUESTION_IMAGE_BUCKET / S3_BUCKET_NAME")

    @staticmethod
    def _pick_attr(model_or_obj: Any, *names: str) -> Any:
        for name in names:
            if hasattr(model_or_obj, name):
                return getattr(model_or_obj, name)
        return None

    @staticmethod
    def _now() -> datetime:
        return time_now_naive()

    @staticmethod
    def _normalize_naive_datetime(value: datetime | None) -> datetime | None:
        return to_naive_beijing(value)

    def _enum_to_str(self, value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def _map_result_status(self, value: Any) -> str:
        raw = self._enum_to_str(value)
        if raw in {"correct"}:
            return "correct"
        if raw in {"wrong", "partial"}:
            return "wrong"
        if raw in {"unanswered", "", "none"}:
            return "wrong"
        return raw

    def _map_submission_status(self, value: Any) -> str:
        raw = self._enum_to_str(value)
        return raw or "not_submitted"

    def _map_grading_status(self, value: Any) -> str:
        raw = self._enum_to_str(value)
        return raw or "pending"

    def _build_list_result_status(
        self,
        *,
        submission_status: str,
        answer_obj: Any | None,
    ) -> str:
        if submission_status == "not_submitted":
            return "unanswered"
        if answer_obj is None:
            return "wrong"
        return self._map_result_status(getattr(answer_obj, "result_status", None))

    def _build_list_grading_status(
        self,
        *,
        submission_status: str,
        answer_obj: Any | None,
    ) -> str:
        if submission_status == "not_submitted":
            return "pending"
        if answer_obj is None:
            if submission_status == "reviewed":
                return "graded"
            return "grading"
        return self._map_grading_status(getattr(answer_obj, "grading_status", None))

    @staticmethod
    def _formal_submission_statuses() -> tuple[SubmissionStatus, ...]:
        return (
            SubmissionStatus.submitted,
            SubmissionStatus.grading,
            SubmissionStatus.reviewed,
        )

    def _get_quiz_name(self, quiz_obj: Any) -> str:
        value = self._pick_attr(quiz_obj, "quiz_name", "name", "title")
        return str(value or "")

    def _get_quiz_deadline(self, quiz_obj: Any) -> datetime | None:
        return self._pick_attr(
            quiz_obj,
            "due_at",
            "deadline_at",
            "deadline",
            "end_at",
            "end_time",
        )

    def _get_question_content(self, question_obj: Any) -> str:
        value = self._pick_attr(question_obj, "content_md", "content", "title")
        return str(value or "")

    def _get_class_name(self, class_obj: Any) -> str:
        value = self._pick_attr(class_obj, "class_name", "name")
        return str(value or "")

    async def _get_question_image_urls(
        self,
        session: AsyncSession,
        question_id: int,
    ) -> list[str]:
        result = await session.execute(
            select(QuestionImage.image_url)
            .where(QuestionImage.question_id == question_id)
            .order_by(QuestionImage.sort_no.asc(), QuestionImage.id.asc())
        )
        bucket_name = self._get_image_bucket_name()
        image_urls = list(result.scalars().all())
        resolved_urls: list[str] = []
        for image_url in image_urls:
            resolved_urls.append(
                await s3_client.resolve_download_url(image_url, bucket_name)
            )
        return resolved_urls

    async def _get_answer_image_urls(
        self,
        session: AsyncSession,
        answer_id: int,
    ) -> list[str]:
        result = await session.execute(
            select(SubmissionAnswerImage.image_url)
            .where(SubmissionAnswerImage.answer_id == answer_id)
            .order_by(SubmissionAnswerImage.sort_no.asc(), SubmissionAnswerImage.id.asc())
        )
        bucket_name = self._get_image_bucket_name()
        image_urls = list(result.scalars().all())
        resolved_urls: list[str] = []
        for image_url in image_urls:
            resolved_urls.append(
                await s3_client.resolve_download_url(image_url, bucket_name)
            )
        return resolved_urls

    async def _get_answer_typical_errors(
        self,
        session: AsyncSession,
        answer_id: int,
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(TypicalErrorPattern, AnswerTypicalErrorRel)
                .join(
                    AnswerTypicalErrorRel,
                    AnswerTypicalErrorRel.pattern_id == TypicalErrorPattern.id,
                )
                .where(AnswerTypicalErrorRel.answer_id == answer_id)
                .order_by(
                    AnswerTypicalErrorRel.is_primary.desc(),
                    TypicalErrorPattern.hit_count.desc(),
                    TypicalErrorPattern.id.asc(),
                )
            )
        ).all()
        return [
            {
                "pattern_id": int(pattern.id),
                "pattern_name": pattern.pattern_name,
                "pattern_desc": pattern.pattern_desc,
                "suggestion_text": pattern.suggestion_text,
                "is_primary": bool(rel.is_primary),
            }
            for pattern, rel in rows
        ]

    async def _get_correct_answer_samples(
        self,
        session: AsyncSession,
        quiz_id: int,
        class_id: int,
        question_id: int,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(SubmissionAnswer, AppUser)
                .join(QuizSubmission, QuizSubmission.id == SubmissionAnswer.submission_id)
                .join(AppUser, AppUser.id == QuizSubmission.student_id)
                .where(
                    QuizSubmission.quiz_id == quiz_id,
                    QuizSubmission.class_id == class_id,
                    QuizSubmission.status.in_(self._formal_submission_statuses()),
                    SubmissionAnswer.question_id == question_id,
                    SubmissionAnswer.result_status == ResultStatus.correct,
                )
                .order_by(SubmissionAnswer.final_score.desc(), SubmissionAnswer.id.desc())
                .limit(limit)
            )
        ).all()
        items: list[dict[str, Any]] = []
        for answer_obj, user_obj in rows:
            items.append(
                {
                    "answer_id": int(answer_obj.id),
                    "student_id": int(user_obj.id),
                    "student_name": str(getattr(user_obj, "real_name", "") or ""),
                    "answer_text": getattr(answer_obj, "answer_md", None),
                    "image_urls": await self._get_answer_image_urls(session, int(answer_obj.id)),
                }
            )
        return items

    async def _get_typical_error_samples(
        self,
        session: AsyncSession,
        quiz_id: int,
        class_id: int,
        question_id: int,
        limit_per_pattern: int = 3,
    ) -> list[dict[str, Any]]:
        patterns = (
            await session.execute(
                select(TypicalErrorPattern)
                .where(TypicalErrorPattern.question_id == question_id)
                .order_by(TypicalErrorPattern.hit_count.desc(), TypicalErrorPattern.id.asc())
            )
        ).scalars().all()
        items: list[dict[str, Any]] = []
        for pattern in patterns:
            rows = (
                await session.execute(
                    select(SubmissionAnswer, AppUser, AnswerTypicalErrorRel)
                    .join(QuizSubmission, QuizSubmission.id == SubmissionAnswer.submission_id)
                    .join(AppUser, AppUser.id == QuizSubmission.student_id)
                    .join(
                        AnswerTypicalErrorRel,
                        AnswerTypicalErrorRel.answer_id == SubmissionAnswer.id,
                    )
                    .where(
                        QuizSubmission.quiz_id == quiz_id,
                        QuizSubmission.class_id == class_id,
                        QuizSubmission.status.in_(self._formal_submission_statuses()),
                        SubmissionAnswer.question_id == question_id,
                        AnswerTypicalErrorRel.pattern_id == pattern.id,
                    )
                    .order_by(
                        AnswerTypicalErrorRel.is_primary.desc(),
                        SubmissionAnswer.id.desc(),
                    )
                    .limit(limit_per_pattern)
                )
            ).all()
            sample_answers: list[dict[str, Any]] = []
            for answer_obj, user_obj, rel in rows:
                sample_answers.append(
                    {
                        "answer_id": int(answer_obj.id),
                        "student_id": int(user_obj.id),
                        "student_name": str(getattr(user_obj, "real_name", "") or ""),
                        "answer_text": getattr(answer_obj, "answer_md", None),
                        "image_urls": await self._get_answer_image_urls(session, int(answer_obj.id)),
                        "is_primary": bool(rel.is_primary),
                    }
                )
            items.append(
                {
                    "pattern_id": int(pattern.id),
                    "pattern_name": pattern.pattern_name,
                    "pattern_desc": pattern.pattern_desc,
                    "suggestion_text": pattern.suggestion_text,
                    "hit_count": int(pattern.hit_count or 0),
                    "sample_answers": sample_answers,
                }
            )
        return items

    def _calc_quiz_status(
        self,
        deadline_at: datetime | None,
        submitted_student_count: int,
        total_student_count: int,
    ) -> str:
        now = self._now()
        deadline_at = self._normalize_naive_datetime(deadline_at)

        if total_student_count > 0 and submitted_student_count >= total_student_count:
            return "completed"
        if deadline_at is not None and deadline_at < now:
            return "expired"
        return "ongoing"

    async def _get_owned_class_ids(
        self,
        session: AsyncSession,
        teacher_id: int,
    ) -> list[int]:
        creator_col = self._pick_attr(ClassRoom, "creator_id", "teacher_id", "created_by")
        status_col = self._pick_attr(ClassRoom, "status")
        stmt = select(ClassRoom.id).where(creator_col == teacher_id)
        if status_col is not None:
            stmt = stmt.where(status_col != 0)
        result = await session.execute(stmt)
        return [int(item) for item in result.scalars().all()]

    async def _get_quiz_ids_by_teacher(
        self,
        session: AsyncSession,
        teacher_id: int,
    ) -> list[int]:
        owned_class_ids = await self._get_owned_class_ids(session, teacher_id)
        if not owned_class_ids:
            return []

        stmt = (
            select(Quiz.id)
            .join(QuizClassRel, QuizClassRel.quiz_id == Quiz.id)
            .where(QuizClassRel.class_id.in_(owned_class_ids))
            .distinct()
        )
        result = await session.execute(stmt)
        return [int(item) for item in result.scalars().all()]

    async def _get_quiz_class_ids(
        self,
        session: AsyncSession,
        quiz_id: int,
    ) -> list[int]:
        stmt = select(QuizClassRel.class_id).where(QuizClassRel.quiz_id == quiz_id)
        result = await session.execute(stmt)
        return [int(item) for item in result.scalars().all()]

    async def _get_quiz_question_ids(
        self,
        session: AsyncSession,
        quiz_id: int,
    ) -> list[int]:
        stmt = select(QuizQuestion.question_id).where(QuizQuestion.quiz_id == quiz_id)
        result = await session.execute(stmt)
        return [int(item) for item in result.scalars().all()]

    async def _get_class_student_count_map(
        self,
        session: AsyncSession,
        class_ids: list[int],
    ) -> dict[int, int]:
        if not class_ids:
            return {}

        stmt = (
            select(
                ClassStudent.class_id,
                func.count(ClassStudent.id),
            )
            .where(
                ClassStudent.class_id.in_(class_ids),
                ClassStudent.join_status == ClassStudentStatus.active,
            )
            .group_by(ClassStudent.class_id)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return {int(row[0]): int(row[1] or 0) for row in rows}

    async def _get_quiz_submitted_student_count_map(
        self,
        session: AsyncSession,
        quiz_id: int,
        class_ids: list[int],
    ) -> dict[int, int]:
        if not class_ids:
            return {}

        class_id_col = self._pick_attr(QuizSubmission, "class_id")
        student_id_col = self._pick_attr(QuizSubmission, "student_id", "user_id", "submitter_id")

        if class_id_col is None or student_id_col is None:
            return {class_id: 0 for class_id in class_ids}

        stmt = (
            select(
                class_id_col,
                func.count(func.distinct(student_id_col)),
            )
            .where(
                and_(
                    QuizSubmission.quiz_id == quiz_id,
                    class_id_col.in_(class_ids),
                    QuizSubmission.status.in_(self._formal_submission_statuses()),
                )
            )
            .group_by(class_id_col)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return {int(row[0]): int(row[1] or 0) for row in rows}

    async def _calc_submission_accuracy(
        self,
        session: AsyncSession,
        submission_id: int,
    ) -> float:
        submission_id_col = self._pick_attr(SubmissionAnswer, "submission_id")
        result_status_col = self._pick_attr(SubmissionAnswer, "result_status")
        score_col = self._pick_attr(SubmissionAnswer, "final_score", "score")

        if submission_id_col is None:
            return 0.0

        stmt = select(SubmissionAnswer).where(submission_id_col == submission_id)
        result = await session.execute(stmt)
        answer_rows = result.scalars().all()
        if not answer_rows:
            return 0.0

        if result_status_col is not None:
            correct_count = 0
            total_count = 0
            for row in answer_rows:
                total_count += 1
                if self._map_result_status(getattr(row, result_status_col.key, None)) == "correct":
                    correct_count += 1
            if total_count == 0:
                return 0.0
            return round(correct_count / total_count * 100, 2)

        if score_col is not None:
            total_score = 0.0
            count = 0
            for row in answer_rows:
                total_score += float(getattr(row, score_col.key, 0) or 0)
                count += 1
            if count == 0:
                return 0.0
            return round(total_score / count, 2)

        return 0.0

    async def _get_quiz_average_score(
        self,
        session: AsyncSession,
        quiz_id: int,
        class_id: int | None = None,
    ) -> float:
        stmt = select(func.coalesce(func.avg(QuizSubmission.final_score), 0)).where(
            QuizSubmission.quiz_id == quiz_id,
            QuizSubmission.status.in_(self._formal_submission_statuses()),
        )
        if class_id is not None:
            stmt = stmt.where(QuizSubmission.class_id == class_id)

        avg_score = await session.scalar(stmt)
        return round(float(avg_score or 0), 2)

    async def _get_quiz_duration_stats(
        self,
        session: AsyncSession,
        quiz_ids: list[int],
    ) -> tuple[float, int]:
        if not quiz_ids:
            return 0.0, 0

        avg_stmt = select(func.coalesce(func.avg(QuizSubmission.total_duration_sec), 0)).where(
            QuizSubmission.quiz_id.in_(quiz_ids),
            QuizSubmission.status.in_(self._formal_submission_statuses()),
            QuizSubmission.total_duration_sec > 0,
        )
        min_stmt = select(func.coalesce(func.min(QuizSubmission.total_duration_sec), 0)).where(
            QuizSubmission.quiz_id.in_(quiz_ids),
            QuizSubmission.status.in_(self._formal_submission_statuses()),
            QuizSubmission.total_duration_sec > 0,
        )

        avg_duration = await session.scalar(avg_stmt)
        fastest_duration = await session.scalar(min_stmt)
        return round(float(avg_duration or 0), 2), int(fastest_duration or 0)

    async def _get_score_distribution(
        self,
        session: AsyncSession,
        quiz_ids: list[int],
    ) -> dict[str, int]:
        if not quiz_ids:
            return {
                "0_59": 0,
                "60_69": 0,
                "70_79": 0,
                "80_89": 0,
                "90_100": 0,
            }

        stmt = select(QuizSubmission.final_score).where(
            QuizSubmission.quiz_id.in_(quiz_ids),
            QuizSubmission.status.in_(self._formal_submission_statuses()),
        )
        result = await session.execute(stmt)
        scores = [float(item or 0) for item in result.scalars().all()]

        distribution = {
            "0_59": 0,
            "60_69": 0,
            "70_79": 0,
            "80_89": 0,
            "90_100": 0,
        }

        for score in scores:
            if score < 60:
                distribution["0_59"] += 1
            elif score < 70:
                distribution["60_69"] += 1
            elif score < 80:
                distribution["70_79"] += 1
            elif score < 90:
                distribution["80_89"] += 1
            else:
                distribution["90_100"] += 1

        return distribution

    async def _get_question_accuracy_list(
        self,
        session: AsyncSession,
        quiz_ids: list[int],
    ) -> list[dict[str, Any]]:
        if not quiz_ids:
            return []

        question_stmt = (
            select(QuizQuestion.question_id)
            .where(QuizQuestion.quiz_id.in_(quiz_ids))
            .distinct()
        )
        question_result = await session.execute(question_stmt)
        question_ids = [int(item) for item in question_result.scalars().all()]
        if not question_ids:
            return []

        result_status_col = self._pick_attr(SubmissionAnswer, "result_status")
        if result_status_col is None:
            return []

        question_rows_stmt = select(Question).where(Question.id.in_(question_ids)).order_by(Question.id.asc())
        question_rows_result = await session.execute(question_rows_stmt)
        question_rows = question_rows_result.scalars().all()

        data: list[dict[str, Any]] = []
        for question_obj in question_rows:
            question_id = int(question_obj.id)
            question_quiz_ids_result = await session.execute(
                select(QuizQuestion.quiz_id).where(QuizQuestion.question_id == question_id)
            )
            question_quiz_ids = [
                int(item)
                for item in question_quiz_ids_result.scalars().all()
                if int(item) in quiz_ids
            ]
            if not question_quiz_ids:
                continue

            submission_rows = (
                await session.execute(
                    select(QuizSubmission.id)
                    .where(
                        QuizSubmission.quiz_id.in_(question_quiz_ids),
                        QuizSubmission.status.in_(self._formal_submission_statuses()),
                    )
                )
            ).scalars().all()
            submission_ids = [int(item) for item in submission_rows]
            total_count = len(submission_ids)
            correct_count = 0
            if submission_ids:
                answer_rows = (
                    await session.execute(
                        select(SubmissionAnswer).where(
                            SubmissionAnswer.submission_id.in_(submission_ids),
                            SubmissionAnswer.question_id == question_id,
                        )
                    )
                ).scalars().all()

                answer_by_submission_id = {
                    int(getattr(answer_obj, "submission_id", 0)): answer_obj
                    for answer_obj in answer_rows
                }

                for submission_id in submission_ids:
                    answer_obj = answer_by_submission_id.get(submission_id)
                    if answer_obj is None:
                        continue
                    if self._map_result_status(
                        getattr(answer_obj, result_status_col.key, None)
                    ) == "correct":
                        correct_count += 1

            accuracy_rate = 0.0
            if total_count > 0:
                accuracy_rate = round(correct_count / total_count * 100, 2)

            data.append(
                {
                    "question_id": question_id,
                    "content_md": self._get_question_content(question_obj),
                    "accuracy_rate": accuracy_rate,
                }
            )

        return data

    async def get_analysis_summary(
        self,
        teacher_id: int | str,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                quiz_ids = await self._get_quiz_ids_by_teacher(session, teacher_id)

                if not quiz_ids:
                    return (
                        True,
                        status.HTTP_200_OK,
                        "获取测验分析总信息成功",
                        {
                            "total_quiz_count": 0,
                            "ongoing_quiz_count": 0,
                            "completed_quiz_count": 0,
                            "expired_quiz_count": 0,
                            "submitted_student_count": 0,
                            "expected_student_count": 0,
                            "unsubmitted_student_count": 0,
                            "submit_rate": 0.0,
                            "average_score": 0.0,
                            "full_score": 100,
                            "average_accuracy": 0.0,
                            "score_compare_last_quiz": 0.0,
                            "score_trend": "flat",
                            "average_duration_sec": 0.0,
                            "fastest_duration_sec": 0,
                            "score_distribution": {
                                "0_59": 0,
                                "60_69": 0,
                                "70_79": 0,
                                "80_89": 0,
                                "90_100": 0,
                            },
                            "question_accuracy_list": [],
                        },
                    )

                stmt = select(Quiz).where(Quiz.id.in_(quiz_ids)).order_by(Quiz.id.desc())
                result = await session.execute(stmt)
                quiz_rows = result.scalars().all()

                ongoing_quiz_count = 0
                completed_quiz_count = 0
                expired_quiz_count = 0
                expected_student_count = 0
                submitted_student_count = 0

                per_quiz_avg_score_list: list[float] = []

                for quiz_obj in quiz_rows:
                    quiz_id = int(quiz_obj.id)
                    class_ids = await self._get_quiz_class_ids(session, quiz_id)
                    class_student_count_map = await self._get_class_student_count_map(session, class_ids)
                    submitted_student_count_map = await self._get_quiz_submitted_student_count_map(
                        session, quiz_id, class_ids
                    )

                    total_student_count = sum(class_student_count_map.values())
                    submitted_count = sum(submitted_student_count_map.values())

                    expected_student_count += total_student_count
                    submitted_student_count += submitted_count

                    current_status = self._calc_quiz_status(
                        deadline_at=self._get_quiz_deadline(quiz_obj),
                        submitted_student_count=submitted_count,
                        total_student_count=total_student_count,
                    )

                    if current_status == "ongoing":
                        ongoing_quiz_count += 1
                    elif current_status == "completed":
                        completed_quiz_count += 1
                    else:
                        expired_quiz_count += 1

                    per_quiz_avg_score_list.append(
                        await self._get_quiz_average_score(session, quiz_id)
                    )

                submission_stmt = select(QuizSubmission).where(
                    QuizSubmission.quiz_id.in_(quiz_ids),
                    QuizSubmission.status.in_(self._formal_submission_statuses()),
                )
                submission_result = await session.execute(submission_stmt)
                submission_rows = submission_result.scalars().all()

                accuracy_list: list[float] = []
                score_list: list[float] = []
                for submission_obj in submission_rows:
                    accuracy = float(getattr(submission_obj, "accuracy_rate", 0) or 0)
                    score = float(getattr(submission_obj, "final_score", 0) or 0)
                    accuracy_list.append(accuracy)
                    score_list.append(score)

                average_accuracy = round(sum(accuracy_list) / len(accuracy_list), 2) if accuracy_list else 0.0
                average_score = round(sum(score_list) / len(score_list), 2) if score_list else 0.0

                unsubmitted_student_count = max(expected_student_count - submitted_student_count, 0)
                submit_rate = (
                    round(submitted_student_count / expected_student_count * 100, 2)
                    if expected_student_count > 0
                    else 0.0
                )

                average_duration_sec, fastest_duration_sec = await self._get_quiz_duration_stats(
                    session, quiz_ids
                )

                score_distribution = await self._get_score_distribution(session, quiz_ids)
                question_accuracy_list = await self._get_question_accuracy_list(session, quiz_ids)

                score_compare_last_quiz = 0.0
                score_trend = "flat"
                if len(per_quiz_avg_score_list) >= 2:
                    current_avg = per_quiz_avg_score_list[0]
                    prev_avg = per_quiz_avg_score_list[1]
                    score_compare_last_quiz = round(current_avg - prev_avg, 2)
                    if score_compare_last_quiz > 0:
                        score_trend = "up"
                    elif score_compare_last_quiz < 0:
                        score_trend = "down"

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取测验分析总信息成功",
                    {
                        "total_quiz_count": len(quiz_rows),
                        "ongoing_quiz_count": ongoing_quiz_count,
                        "completed_quiz_count": completed_quiz_count,
                        "expired_quiz_count": expired_quiz_count,
                        "submitted_student_count": submitted_student_count,
                        "expected_student_count": expected_student_count,
                        "unsubmitted_student_count": unsubmitted_student_count,
                        "submit_rate": submit_rate,
                        "average_score": average_score,
                        "full_score": 100,
                        "average_accuracy": average_accuracy,
                        "score_compare_last_quiz": score_compare_last_quiz,
                        "score_trend": score_trend,
                        "average_duration_sec": average_duration_sec,
                        "fastest_duration_sec": fastest_duration_sec,
                        "score_distribution": score_distribution,
                        "question_accuracy_list": question_accuracy_list,
                    },
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取测验分析总信息失败，请稍后重试" + str(e),
                    None,
                )

    async def get_quiz_name_list(
        self,
        teacher_id: int | str,
    ) -> tuple[bool, int, str, list[dict] | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                quiz_ids = await self._get_quiz_ids_by_teacher(session, teacher_id)
                if not quiz_ids:
                    return True, status.HTTP_200_OK, "获取测试名称列表成功", []

                stmt = select(Quiz).where(Quiz.id.in_(quiz_ids)).order_by(Quiz.id.desc())
                result = await session.execute(stmt)
                quiz_rows = result.scalars().all()

                data = [
                    {
                        "quiz_id": int(row.id),
                        "quiz_name": self._get_quiz_name(row),
                    }
                    for row in quiz_rows
                ]
                return True, status.HTTP_200_OK, "获取测试名称列表成功", data
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取测试名称列表失败，请稍后重试" + str(e),
                    None,
                )

    async def get_quiz_class_stats(
        self,
        teacher_id: int | str,
        quiz_id: int,
    ) -> tuple[bool, int, str, list[dict] | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                owned_class_ids = set(await self._get_owned_class_ids(session, teacher_id))
                quiz_class_ids = await self._get_quiz_class_ids(session, quiz_id)

                visible_class_ids = [item for item in quiz_class_ids if item in owned_class_ids]
                if not visible_class_ids:
                    return False, status.HTTP_404_NOT_FOUND, "测验不存在或无权限", None

                class_student_count_map = await self._get_class_student_count_map(session, visible_class_ids)
                submitted_student_count_map = await self._get_quiz_submitted_student_count_map(
                    session, quiz_id, visible_class_ids
                )

                class_stmt = select(ClassRoom).where(ClassRoom.id.in_(visible_class_ids))
                class_result = await session.execute(class_stmt)
                class_rows = class_result.scalars().all()

                data: list[dict[str, Any]] = []
                for class_obj in class_rows:
                    class_id = int(class_obj.id)
                    total_student_count = int(class_student_count_map.get(class_id, 0))
                    submitted_student_count = int(submitted_student_count_map.get(class_id, 0))
                    submit_rate = 0.0
                    if total_student_count > 0:
                        submit_rate = round(submitted_student_count / total_student_count * 100, 2)

                    average_score = await self._get_quiz_average_score(session, quiz_id, class_id)

                    data.append(
                        {
                            "class_id": class_id,
                            "class_name": self._get_class_name(class_obj),
                            "student_count": total_student_count,
                            "submitted_student_count": submitted_student_count,
                            "submit_rate": submit_rate,
                            "average_score": average_score,
                        }
                    )

                data.sort(key=lambda item: item["class_id"])
                return True, status.HTTP_200_OK, "获取某测试下的班级列表及统计成功", data
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取某测试下的班级列表及统计失败，请稍后重试" + str(e),
                    None,
                )

    async def get_quiz_class_question_stats(
        self,
        teacher_id: int | str,
        quiz_id: int,
        class_id: int,
    ) -> tuple[bool, int, str, list[dict] | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                owned_class_ids = set(await self._get_owned_class_ids(session, teacher_id))
                if class_id not in owned_class_ids:
                    return False, status.HTTP_404_NOT_FOUND, "班级不存在或无权限", None

                quiz_class_ids = await self._get_quiz_class_ids(session, quiz_id)
                if class_id not in quiz_class_ids:
                    return False, status.HTTP_404_NOT_FOUND, "该班级不在此测验中", None

                question_ids = await self._get_quiz_question_ids(session, quiz_id)
                if not question_ids:
                    return True, status.HTTP_200_OK, "获取某测试某班级下的题目列表成功", []

                question_stmt = select(Question).where(Question.id.in_(question_ids)).order_by(Question.id.asc())
                question_result = await session.execute(question_stmt)
                question_rows = question_result.scalars().all()
                total_student_count = int(
                    (await self._get_class_student_count_map(session, [class_id])).get(class_id, 0)
                )
                submission_rows = (
                    await session.execute(
                        select(QuizSubmission.id)
                        .where(
                            QuizSubmission.quiz_id == quiz_id,
                            QuizSubmission.class_id == class_id,
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                    )
                ).scalars().all()
                submission_ids = [int(item) for item in submission_rows]

                data: list[dict[str, Any]] = []
                for question_obj in question_rows:
                    question_id = int(question_obj.id)

                    answer_rows = []
                    if submission_ids:
                        answer_rows = (
                            await session.execute(
                                select(SubmissionAnswer).where(
                                    SubmissionAnswer.submission_id.in_(submission_ids),
                                    SubmissionAnswer.question_id == question_id,
                                )
                            )
                        ).scalars().all()

                    answer_by_submission_id = {
                        int(getattr(answer_obj, "submission_id", 0)): answer_obj
                        for answer_obj in answer_rows
                    }

                    answer_count = len(submission_ids)
                    correct_count = 0
                    wrong_count = 0
                    unanswered_count = max(total_student_count - len(submission_ids), 0)
                    typical_error_count = 0

                    for submission_id in submission_ids:
                        answer_obj = answer_by_submission_id.get(submission_id)
                        if answer_obj is None:
                            wrong_count += 1
                            continue

                        result_value = self._map_result_status(
                            getattr(answer_obj, "result_status", None)
                        )
                        if result_value == "correct":
                            correct_count += 1
                        else:
                            wrong_count += 1

                        rel_count = await session.scalar(
                            select(func.count(AnswerTypicalErrorRel.id)).where(
                                AnswerTypicalErrorRel.answer_id == int(answer_obj.id)
                            )
                        )
                        if int(rel_count or 0) > 0:
                            typical_error_count += 1

                    accuracy_rate = round(correct_count / answer_count * 100, 2) if answer_count > 0 else 0.0
                    typical_error_rate = (
                        round(typical_error_count / answer_count * 100, 2) if answer_count > 0 else 0.0
                    )

                    data.append(
                        {
                            "question_id": question_id,
                            "content_md": self._get_question_content(question_obj),
                            "question_image_urls": await self._get_question_image_urls(session, question_id),
                            "answer_count": answer_count,
                            "correct_count": correct_count,
                            "wrong_count": wrong_count,
                            "unanswered_count": unanswered_count,
                            "accuracy_rate": accuracy_rate,
                            "typical_error_rate": typical_error_rate,
                            "correct_answer_samples": await self._get_correct_answer_samples(
                                session, quiz_id, class_id, question_id
                            ),
                            "typical_error_samples": await self._get_typical_error_samples(
                                session, quiz_id, class_id, question_id
                            ),
                        }
                    )

                return True, status.HTTP_200_OK, "获取某测试某班级下的题目列表成功", data
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取某测试某班级下的题目列表失败，请稍后重试" + str(e),
                    None,
                )

    async def get_student_answer_list(
        self,
        teacher_id: int | str,
        quiz_id: int,
        class_id: int | None,
        question_id: int | None,
        page: int,
        page_size: int,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                owned_class_ids = set(await self._get_owned_class_ids(session, teacher_id))
                quiz_class_ids = set(await self._get_quiz_class_ids(session, quiz_id))
                visible_class_ids = sorted(list(owned_class_ids.intersection(quiz_class_ids)))

                if not visible_class_ids:
                    return False, status.HTTP_404_NOT_FOUND, "测验不存在或无权限", None

                if class_id is not None:
                    if class_id not in visible_class_ids:
                        return False, status.HTTP_404_NOT_FOUND, "班级不存在或无权限", None
                    visible_class_ids = [class_id]

                if question_id is not None:
                    quiz_question_ids = set(await self._get_quiz_question_ids(session, quiz_id))
                    if question_id not in quiz_question_ids:
                        return False, status.HTTP_404_NOT_FOUND, "题目不存在或不属于该测验", None

                student_stmt = (
                    select(AppUser, StudentProfile, ClassStudent, ClassRoom)
                    .join(ClassStudent, ClassStudent.student_id == AppUser.id)
                    .join(StudentProfile, StudentProfile.user_id == AppUser.id)
                    .join(ClassRoom, ClassRoom.id == ClassStudent.class_id)
                    .where(
                        ClassStudent.class_id.in_(visible_class_ids),
                        ClassStudent.join_status == ClassStudentStatus.active,
                    )
                    .order_by(ClassStudent.class_id.asc(), AppUser.id.desc())
                )
                student_result = await session.execute(student_stmt)
                student_rows = student_result.all()

                items: list[dict[str, Any]] = []
                for user_obj, profile_obj, class_student_obj, class_obj in student_rows:
                    student_id = int(user_obj.id)
                    current_class_id = int(class_student_obj.class_id)
                    current_class_name = self._get_class_name(class_obj)

                    submission_stmt = (
                        select(QuizSubmission)
                        .where(
                            QuizSubmission.quiz_id == quiz_id,
                            QuizSubmission.class_id == current_class_id,
                            QuizSubmission.student_id == student_id,
                            QuizSubmission.status.in_(self._formal_submission_statuses()),
                        )
                        .order_by(QuizSubmission.id.desc())
                    )
                    submission_result = await session.execute(submission_stmt)
                    submission_obj = submission_result.scalars().first()

                    result_value = "unanswered"
                    is_typical_error = False
                    submitted_at = None
                    duration_sec = 0
                    submission_id = None
                    submission_status = "not_submitted"
                    grading_status = "not_submitted"
                    ai_score = 0.0
                    final_score = 0.0
                    ai_feedback = None

                    if submission_obj is not None:
                        submission_id = int(submission_obj.id)
                        submitted_at = getattr(submission_obj, "submitted_at", None)
                        submission_status = self._map_submission_status(
                            getattr(submission_obj, "status", None)
                        )
                        answer_stmt = select(SubmissionAnswer).where(
                            SubmissionAnswer.submission_id == submission_id
                        )
                        if question_id is not None:
                            answer_stmt = answer_stmt.where(SubmissionAnswer.question_id == question_id)

                        answer_stmt = answer_stmt.order_by(SubmissionAnswer.id.desc())
                        answer_result = await session.execute(answer_stmt)
                        answer_obj = answer_result.scalars().first()

                        grading_status = self._build_list_grading_status(
                            submission_status=submission_status,
                            answer_obj=answer_obj,
                        )

                        if answer_obj is not None:
                            result_value = self._build_list_result_status(
                                submission_status=submission_status,
                                answer_obj=answer_obj,
                            )
                            duration_sec = int(getattr(answer_obj, "duration_sec", 0) or 0)
                            ai_score = float(getattr(answer_obj, "ai_score", 0) or 0)
                            final_score = float(getattr(answer_obj, "final_score", 0) or 0)
                            ai_feedback = getattr(answer_obj, "ai_feedback", None)

                            rel_count = await session.scalar(
                                select(func.count(AnswerTypicalErrorRel.id)).where(
                                    AnswerTypicalErrorRel.answer_id == int(answer_obj.id)
                                )
                            )
                            is_typical_error = int(rel_count or 0) > 0
                        else:
                            result_value = self._build_list_result_status(
                                submission_status=submission_status,
                                answer_obj=None,
                            )

                    items.append(
                        {
                            "submission_id": submission_id,
                            "class_id": current_class_id,
                            "class_name": current_class_name,
                            "student_id": student_id,
                            "student_no": str(getattr(profile_obj, "student_no", "") or ""),
                            "student_name": str(getattr(user_obj, "real_name", "") or ""),
                            "submission_status": submission_status,
                            "grading_status": grading_status,
                            "result": result_value,
                            "ai_score": ai_score,
                            "final_score": final_score,
                            "ai_feedback": ai_feedback,
                            "is_typical_error": is_typical_error,
                            "submitted_at": submitted_at,
                            "duration_sec": duration_sec,
                        }
                    )

                total = len(items)
                start = (page - 1) * page_size
                end = start + page_size

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取学生作答列表成功",
                    {
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "items": items[start:end],
                    },
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取学生作答列表失败，请稍后重试" + str(e),
                    None,
                )

    async def get_student_answer_detail(
        self,
        teacher_id: int | str,
        submission_id: int,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                submission_stmt = select(QuizSubmission).where(QuizSubmission.id == submission_id)
                submission_result = await session.execute(submission_stmt)
                submission_obj = submission_result.scalar_one_or_none()

                if not submission_obj:
                    return False, status.HTTP_404_NOT_FOUND, "作答记录不存在", None
                if getattr(submission_obj, "status", None) not in self._formal_submission_statuses():
                    return False, status.HTTP_404_NOT_FOUND, "作答记录尚未正式提交", None

                class_id_col = self._pick_attr(QuizSubmission, "class_id")
                student_id_col = self._pick_attr(QuizSubmission, "student_id", "user_id", "submitter_id")
                submitted_at_col = self._pick_attr(QuizSubmission, "submitted_at", "created_at", "submit_time")

                owned_class_ids = set(await self._get_owned_class_ids(session, teacher_id))
                submission_class_id = (
                    int(getattr(submission_obj, class_id_col.key)) if class_id_col is not None else 0
                )
                if submission_class_id not in owned_class_ids:
                    return False, status.HTTP_404_NOT_FOUND, "作答记录不存在或无权限", None

                quiz_stmt = select(Quiz).where(Quiz.id == int(submission_obj.quiz_id))
                quiz_result = await session.execute(quiz_stmt)
                quiz_obj = quiz_result.scalar_one_or_none()

                student_id = int(getattr(submission_obj, student_id_col.key)) if student_id_col is not None else 0

                user_stmt = select(AppUser).where(AppUser.id == student_id)
                user_result = await session.execute(user_stmt)
                user_obj = user_result.scalar_one_or_none()

                profile_stmt = select(StudentProfile).where(
                    self._pick_attr(StudentProfile, "user_id", "student_id", "app_user_id") == student_id
                )
                profile_result = await session.execute(profile_stmt)
                profile_obj = profile_result.scalar_one_or_none()

                student_no = ""
                student_name = ""
                if profile_obj is not None:
                    student_no = str(self._pick_attr(profile_obj, "student_no", "stu_no") or "")
                if user_obj is not None:
                    student_name = str(getattr(user_obj, "real_name", "") or "")

                class_stmt = select(ClassRoom).where(ClassRoom.id == submission_class_id)
                class_result = await session.execute(class_stmt)
                class_obj = class_result.scalar_one_or_none()

                answer_items: list[dict[str, Any]] = []
                question_ids_result = await session.execute(
                    select(QuizQuestion.question_id)
                    .where(QuizQuestion.quiz_id == int(submission_obj.quiz_id))
                    .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
                )
                quiz_question_ids = [int(item) for item in question_ids_result.scalars().all()]

                answer_rows: list[Any] = []
                if hasattr(SubmissionAnswer, "submission_id"):
                    answer_stmt = select(SubmissionAnswer).where(SubmissionAnswer.submission_id == submission_id)
                    answer_result = await session.execute(answer_stmt)
                    answer_rows = answer_result.scalars().all()

                answer_by_question_id = {
                    int(self._pick_attr(answer_obj, "question_id") or 0): answer_obj
                    for answer_obj in answer_rows
                }

                question_result = await session.execute(
                    select(Question).where(Question.id.in_(quiz_question_ids))
                )
                question_rows = question_result.scalars().all()
                question_by_id = {int(question_obj.id): question_obj for question_obj in question_rows}

                submission_status = self._map_submission_status(
                    getattr(submission_obj, "status", None)
                )
                for question_id in quiz_question_ids:
                    answer_obj = answer_by_question_id.get(question_id)
                    question_obj = question_by_id.get(question_id)
                    answer_items.append(
                        {
                            "answer_id": int(answer_obj.id) if answer_obj is not None else None,
                            "question_id": question_id,
                            "question_content": self._get_question_content(question_obj)
                            if question_obj is not None
                            else "",
                            "question_image_urls": await self._get_question_image_urls(session, question_id),
                            "answer_text": self._pick_attr(
                                answer_obj,
                                "answer_md",
                                "answer_text",
                                "content",
                                "text_answer",
                            )
                            if answer_obj is not None
                            else None,
                            "answer_image_urls": await self._get_answer_image_urls(session, int(answer_obj.id))
                            if answer_obj is not None
                            else [],
                            "result": self._build_list_result_status(
                                submission_status=submission_status,
                                answer_obj=answer_obj,
                            ),
                            "grading_status": self._build_list_grading_status(
                                submission_status=submission_status,
                                answer_obj=answer_obj,
                            ),
                            "ai_score": float(getattr(answer_obj, "ai_score", 0) or 0)
                            if answer_obj is not None
                            else 0.0,
                            "score": self._pick_attr(answer_obj, "final_score", "score")
                            if answer_obj is not None
                            else 0,
                            "ai_feedback": self._pick_attr(answer_obj, "ai_feedback")
                            if answer_obj is not None
                            else None,
                            "teacher_feedback": self._pick_attr(answer_obj, "teacher_feedback")
                            if answer_obj is not None
                            else None,
                            "typical_errors": await self._get_answer_typical_errors(session, int(answer_obj.id))
                            if answer_obj is not None
                            else [],
                        }
                    )

                data = {
                    "submission_id": int(submission_obj.id),
                    "quiz_id": int(submission_obj.quiz_id),
                    "quiz_name": self._get_quiz_name(quiz_obj) if quiz_obj is not None else "",
                    "class_id": submission_class_id,
                    "class_name": self._get_class_name(class_obj) if class_obj is not None else "",
                    "student_id": student_id,
                    "student_no": student_no,
                    "student_name": student_name,
                    "submission_status": self._map_submission_status(
                        getattr(submission_obj, "status", None)
                    ),
                    "submitted_at": getattr(submission_obj, submitted_at_col.key, None)
                    if submitted_at_col is not None
                    else None,
                    "accuracy_rate": await self._calc_submission_accuracy(session, submission_id),
                    "answers": answer_items,
                }
                return True, status.HTTP_200_OK, "获取学生作答详情成功", data
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取学生作答详情失败，请稍后重试" + str(e),
                    None,
                )


TEA_analysis_service = TEAAnalysisService()