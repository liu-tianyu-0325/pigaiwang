from datetime import datetime
from typing import Any

from fastapi import status
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    ClassRoom,
    ClassStudent,
    Question,
    Quiz,
    QuizClassRel,
    QuizQuestion,
    QuizSubmission,
)
from app.utils.snowflake_id import generate_id


class TEAQuizService:
    """教师端测验管理业务逻辑。"""

    @staticmethod
    def _pick_attr(model_or_obj: Any, *names: str) -> Any:
        for name in names:
            if hasattr(model_or_obj, name):
                return getattr(model_or_obj, name)
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    @staticmethod
    def _normalize_naive_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

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

    def _get_quiz_db_status(self, quiz_obj: Any) -> str:
        status_value = self._pick_attr(quiz_obj, "status")
        if status_value is None:
            return ""
        if hasattr(status_value, "value"):
            return str(status_value.value)
        return str(status_value)

    async def _sync_table_id_sequence(
        self,
        session: AsyncSession,
        table_name: str,
        id_column: str = "id",
    ) -> None:
        """自动对齐 PostgreSQL 自增序列。"""
        await session.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{id_column}'),
                    COALESCE((SELECT MAX({id_column}) FROM {table_name}), 1),
                    true
                )
                """
            )
        )

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

    async def _validate_class_ids(
        self,
        session: AsyncSession,
        teacher_id: int,
        class_ids: list[int],
    ) -> tuple[bool, str]:
        owned_class_ids = await self._get_owned_class_ids(session, teacher_id)
        owned_class_id_set = set(owned_class_ids)

        invalid_ids = [item for item in class_ids if item not in owned_class_id_set]
        if invalid_ids:
            return False, f"班级不存在或无权限: {invalid_ids}"
        return True, ""

    async def _validate_question_ids(
        self,
        session: AsyncSession,
        teacher_id: int,
        question_ids: list[int],
    ) -> tuple[bool, str]:
        creator_col = self._pick_attr(Question, "creator_id", "teacher_id", "created_by")
        status_col = self._pick_attr(Question, "status")

        stmt = select(Question.id).where(
            and_(
                Question.id.in_(question_ids),
                creator_col == teacher_id,
            )
        )

        if status_col is not None:
            stmt = stmt.where(status_col != "disabled")

        result = await session.execute(stmt)
        existing_ids = {int(item) for item in result.scalars().all()}
        invalid_ids = [item for item in question_ids if item not in existing_ids]
        if invalid_ids:
            return False, f"题目不存在或无权限: {invalid_ids}"
        return True, ""

    async def _get_class_info_list(
        self,
        session: AsyncSession,
        class_ids: list[int],
    ) -> list[dict[str, Any]]:
        if not class_ids:
            return []

        status_col = self._pick_attr(ClassRoom, "status")
        stmt = select(ClassRoom).where(ClassRoom.id.in_(class_ids))
        if status_col is not None:
            stmt = stmt.where(status_col != 0)

        result = await session.execute(stmt)
        class_rows = result.scalars().all()

        data: list[dict[str, Any]] = []
        for row in class_rows:
            class_name = self._pick_attr(row, "class_name", "name") or ""
            data.append(
                {
                    "class_id": int(row.id),
                    "class_name": str(class_name),
                }
            )

        data.sort(key=lambda item: item["class_id"])
        return data

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
            .where(ClassStudent.class_id.in_(class_ids))
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
        student_id_col = self._pick_attr(
            QuizSubmission, "student_id", "user_id", "submitter_id"
        )

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
                )
            )
            .group_by(class_id_col)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return {int(row[0]): int(row[1] or 0) for row in rows}

    async def _get_quiz_average_score(
        self,
        session: AsyncSession,
        quiz_id: int,
    ) -> float:
        avg_score = await session.scalar(
            select(func.coalesce(func.avg(QuizSubmission.final_score), 0)).where(
                QuizSubmission.quiz_id == quiz_id
            )
        )
        return round(float(avg_score or 0), 2)

    async def _resolve_and_sync_quiz_status(
        self,
        session: AsyncSession,
        quiz_obj: Any,
        total_student_count: int,
        submitted_student_count: int,
    ) -> str:
        """统一业务状态并同步回数据库。

        规则：
        - 总人数 > 0 且 已提交人数 >= 总人数 -> completed
        - 否则如果已过截止时间 -> expired
        - 否则 -> ongoing
        """
        deadline_at = self._normalize_naive_datetime(self._get_quiz_deadline(quiz_obj))
        now = self._now()
        db_status = self._get_quiz_db_status(quiz_obj)

        if total_student_count > 0 and submitted_student_count >= total_student_count:
            target_status = "completed"
        elif deadline_at is not None and deadline_at < now:
            target_status = "expired"
        else:
            target_status = "ongoing"

        if db_status != target_status:
            setattr(quiz_obj, "status", target_status)
            await session.flush()

        return target_status

    async def list_quizzes(
        self,
        teacher_id: int | str,
        quiz_status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                owned_class_ids = await self._get_owned_class_ids(session, teacher_id)
                if not owned_class_ids:
                    return (
                        True,
                        status.HTTP_200_OK,
                        "获取测验列表成功",
                        {
                            "total": 0,
                            "page": page,
                            "page_size": page_size,
                            "items": [],
                        },
                    )

                stmt = (
                    select(Quiz)
                    .join(QuizClassRel, QuizClassRel.quiz_id == Quiz.id)
                    .where(QuizClassRel.class_id.in_(owned_class_ids))
                    .distinct()
                    .order_by(Quiz.id.desc())
                )
                result = await session.execute(stmt)
                quiz_rows = result.scalars().all()

                items: list[dict[str, Any]] = []
                for quiz_obj in quiz_rows:
                    quiz_id = int(quiz_obj.id)

                    class_ids = await self._get_quiz_class_ids(session, quiz_id)
                    question_ids = await self._get_quiz_question_ids(session, quiz_id)
                    class_info_list = await self._get_class_info_list(session, class_ids)
                    class_student_count_map = await self._get_class_student_count_map(
                        session, class_ids
                    )
                    submitted_student_count_map = (
                        await self._get_quiz_submitted_student_count_map(
                            session, quiz_id, class_ids
                        )
                    )

                    total_student_count = sum(class_student_count_map.values())
                    submitted_student_count = sum(submitted_student_count_map.values())

                    submit_rate = 0.0
                    if total_student_count > 0:
                        submit_rate = round(
                            submitted_student_count / total_student_count * 100, 2
                        )

                    average_score = await self._get_quiz_average_score(session, quiz_id)

                    biz_status = await self._resolve_and_sync_quiz_status(
                        session=session,
                        quiz_obj=quiz_obj,
                        total_student_count=total_student_count,
                        submitted_student_count=submitted_student_count,
                    )

                    if quiz_status and quiz_status != "all" and biz_status != quiz_status:
                        continue

                    items.append(
                        {
                            "quiz_id": quiz_id,
                            "quiz_name": self._get_quiz_name(quiz_obj),
                            "class_list": class_info_list,
                            "question_count": len(question_ids),
                            "deadline_at": self._get_quiz_deadline(quiz_obj),
                            "status": biz_status,
                            "submit_rate": submit_rate,
                            "average_score": average_score,
                        }
                    )

                await session.commit()

                total = len(items)
                start = (page - 1) * page_size
                end = start + page_size
                paged_items = items[start:end]

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取测验列表成功",
                    {
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "items": paged_items,
                    },
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "获取测验列表失败，请稍后重试" + str(e),
                    None,
                )

    async def create_quiz(
        self,
        teacher_id: int | str,
        quiz_name: str,
        class_ids: list[int],
        question_ids: list[int],
        deadline_at: datetime,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                teacher_id = int(teacher_id)
                deadline_at = self._normalize_naive_datetime(deadline_at)

                ok, error_message = await self._validate_class_ids(
                    session, teacher_id, class_ids
                )
                if not ok:
                    return False, status.HTTP_400_BAD_REQUEST, error_message, None

                ok, error_message = await self._validate_question_ids(
                    session, teacher_id, question_ids
                )
                if not ok:
                    return False, status.HTTP_400_BAD_REQUEST, error_message, None

                # 只对 quiz 主表做自增序列修复
                await self._sync_table_id_sequence(session, "quiz")

                quiz_name_col = self._pick_attr(Quiz, "quiz_name", "name", "title")
                due_at_col = self._pick_attr(
                    Quiz,
                    "due_at",
                    "deadline_at",
                    "deadline",
                    "end_at",
                    "end_time",
                )
                creator_col = self._pick_attr(Quiz, "creator_id", "teacher_id", "created_by")
                question_count_col = self._pick_attr(Quiz, "question_count")
                total_score_col = self._pick_attr(Quiz, "total_score")
                status_col = self._pick_attr(Quiz, "status")

                new_quiz = Quiz()

                if quiz_name_col is not None:
                    setattr(new_quiz, quiz_name_col.key, quiz_name.strip())

                if due_at_col is not None:
                    setattr(new_quiz, due_at_col.key, deadline_at)

                if creator_col is not None:
                    setattr(new_quiz, creator_col.key, teacher_id)

                if question_count_col is not None:
                    setattr(new_quiz, question_count_col.key, len(question_ids))

                if total_score_col is not None:
                    setattr(new_quiz, total_score_col.key, float(len(question_ids) * 100))

                if status_col is not None:
                    setattr(new_quiz, status_col.key, "ongoing")

                session.add(new_quiz)
                await session.flush()
                new_quiz_id = int(new_quiz.id)

                for class_id in class_ids:
                    session.add(
                        QuizClassRel(
                            id=int(generate_id()),
                            quiz_id=new_quiz_id,
                            class_id=class_id,
                        )
                    )

                for sort_no, question_id in enumerate(question_ids, start=1):
                    payload = {
                        "id": int(generate_id()),
                        "quiz_id": new_quiz_id,
                        "question_id": question_id,
                    }
                    if hasattr(QuizQuestion, "sort_no"):
                        payload["sort_no"] = sort_no
                    session.add(QuizQuestion(**payload))

                response_data = {
                    "quiz_id": new_quiz_id,
                    "quiz_name": quiz_name.strip(),
                    "class_ids": class_ids,
                    "question_ids": question_ids,
                    "deadline_at": deadline_at,
                }

                await session.commit()

                return (
                    True,
                    status.HTTP_200_OK,
                    "新增测验成功",
                    response_data,
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "新增测验失败，请稍后重试" + str(e),
                    None,
                )


TEA_quiz_service = TEAQuizService()