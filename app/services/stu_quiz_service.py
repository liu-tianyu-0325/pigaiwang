"""学生测验服务。"""

from __future__ import annotations

from datetime import datetime

from fastapi import status
from sqlalchemy import and_, delete, desc, func, select

from app.common.time_ import to_naive_utc
from app.storage import AsyncSessionLocal, GradingStatus, ResultStatus, SubmissionStatus
from app.storage.database_models import (
    AnswerTypicalErrorRel,
    ClassRoom,
    ClassStudent,
    ClassStudentStatus,
    Question,
    Quiz,
    QuizClassRel,
    QuizQuestion,
    QuizSubmission,
    SubmissionAnswer,
    SubmissionAnswerImage,
    TypicalErrorPattern,
)


class StuQuizService:
    """处理学生测验相关逻辑。"""

    completed_statuses = {
        SubmissionStatus.submitted,
        SubmissionStatus.grading,
        SubmissionStatus.reviewed,
    }

    def _build_display_status(
        self,
        submission_status: SubmissionStatus | None,
        due_at: datetime,
        now: datetime,
    ) -> str:
        if submission_status in self.completed_statuses:
            return "已完成"
        if due_at < now:
            return "过期"
        return "进行中"

    def _build_answer_grading_status(
        self,
        answer: SubmissionAnswer | None,
    ) -> str:
        if answer is None or not answer.is_answered:
            return "未作答"
        if answer.grading_status == GradingStatus.graded:
            return "已批改"
        return "已提交"

    def _build_result_status_text(self, answer: SubmissionAnswer | None) -> str:
        if answer is None or not answer.is_answered:
            return "未作答"
        mapping = {
            ResultStatus.correct: "正确",
            ResultStatus.wrong: "错误",
            ResultStatus.partial: "部分正确",
            ResultStatus.unanswered: "未作答",
        }
        return mapping.get(answer.result_status, "未作答")

    async def _get_student_class_context(
        self,
        session,
        student_id: int,
        quiz_id: int | None = None,
    ) -> tuple[int | None, str | None]:
        stmt = (
            select(ClassRoom.id, ClassRoom.class_name)
            .join(ClassStudent, ClassStudent.class_id == ClassRoom.id)
            .where(
                ClassStudent.student_id == student_id,
                ClassStudent.join_status == ClassStudentStatus.active,
            )
            .order_by(ClassRoom.id.desc())
        )
        if quiz_id is not None:
            stmt = stmt.join(QuizClassRel, QuizClassRel.class_id == ClassRoom.id).where(
                QuizClassRel.quiz_id == quiz_id
            )
        row = (await session.execute(stmt)).first()
        if row is None:
            return None, None
        return row[0], row[1]

    async def get_quiz_list(
        self,
        student_id: str,
        status_text: str,
    ) -> tuple[bool, int, str, dict | None]:
        """获取学生测验列表。"""
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    select(Quiz, QuizSubmission)
                    .join(QuizClassRel, QuizClassRel.quiz_id == Quiz.id)
                    .join(ClassStudent, ClassStudent.class_id == QuizClassRel.class_id)
                    .outerjoin(
                        QuizSubmission,
                        and_(
                            QuizSubmission.quiz_id == Quiz.id,
                            QuizSubmission.student_id == int(student_id),
                        ),
                    )
                    .where(
                        ClassStudent.student_id == int(student_id),
                        ClassStudent.join_status == ClassStudentStatus.active,
                    )
                    .order_by(Quiz.due_at.desc(), Quiz.id.desc())
                )
                rows = (await session.execute(stmt)).all()

                items: list[dict] = []
                seen_quiz_ids: set[int] = set()
                for quiz, submission in rows:
                    if quiz.id in seen_quiz_ids:
                        continue
                    seen_quiz_ids.add(quiz.id)
                    display_status = self._build_display_status(
                        submission.status if submission else None,
                        quiz.due_at,
                        now,
                    )
                    if status_text != "全部" and display_status != status_text:
                        continue
                    items.append(
                        {
                            "quiz_id": str(quiz.id),
                            "quiz_name": quiz.quiz_name,
                            "question_count": submission.question_count
                            if submission
                            else quiz.question_count,
                            "correct_count": submission.correct_count
                            if submission
                            else 0,
                            "status": display_status,
                            "due_at": quiz.due_at,
                            "score": submission.final_score if submission else 0,
                            "submitted_at": submission.submitted_at
                            if submission
                            else None,
                        }
                    )

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取成功",
                    {"total": len(items), "items": items},
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )

    async def get_quiz_detail(
        self,
        student_id: str,
        quiz_id: str,
    ) -> tuple[bool, int, str, dict | None]:
        """获取学生测验详情。"""
        async with AsyncSessionLocal() as session:
            try:
                quiz = await session.get(Quiz, int(quiz_id))
                if quiz is None:
                    return False, status.HTTP_404_NOT_FOUND, "测验不存在", None

                _, class_name = await self._get_student_class_context(
                    session, int(student_id), int(quiz_id)
                )
                submission = (
                    await session.execute(
                        select(QuizSubmission).where(
                            QuizSubmission.quiz_id == int(quiz_id),
                            QuizSubmission.student_id == int(student_id),
                        )
                    )
                ).scalar_one_or_none()

                stmt = (
                    select(QuizQuestion, Question, SubmissionAnswer)
                    .join(Question, Question.id == QuizQuestion.question_id)
                    .outerjoin(
                        SubmissionAnswer,
                        and_(
                            SubmissionAnswer.quiz_id == QuizQuestion.quiz_id,
                            SubmissionAnswer.question_id == QuizQuestion.question_id,
                            SubmissionAnswer.submission_id
                            == (submission.id if submission else -1),
                        ),
                    )
                    .where(QuizQuestion.quiz_id == int(quiz_id))
                    .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
                )
                rows = (await session.execute(stmt)).all()
                questions = [
                    {
                        "question_id": str(question.id),
                        "question": question.content_md,
                        "grading_status": self._build_answer_grading_status(answer),
                        "result_status": self._build_result_status_text(answer),
                        "is_answered": bool(answer.is_answered) if answer else False,
                    }
                    for _, question, answer in rows
                ]

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取成功",
                    {
                        "quiz_id": str(quiz.id),
                        "quiz_name": quiz.quiz_name,
                        "class_name": class_name,
                        "questions": questions,
                    },
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )

    async def get_question_detail(
        self,
        student_id: str,
        question_id: str,
        quiz_id: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """获取学生题目详情。"""
        async with AsyncSessionLocal() as session:
            try:
                question = await session.get(Question, int(question_id))
                if question is None:
                    return False, status.HTTP_404_NOT_FOUND, "题目不存在", None

                stmt = (
                    select(SubmissionAnswer, QuizSubmission)
                    .join(
                        QuizSubmission,
                        QuizSubmission.id == SubmissionAnswer.submission_id,
                    )
                    .where(
                        SubmissionAnswer.question_id == int(question_id),
                        QuizSubmission.student_id == int(student_id),
                    )
                    .order_by(
                        desc(SubmissionAnswer.submitted_at),
                        desc(SubmissionAnswer.updated_at),
                        desc(SubmissionAnswer.id),
                    )
                )
                if quiz_id is not None:
                    stmt = stmt.where(SubmissionAnswer.quiz_id == int(quiz_id))
                row = (await session.execute(stmt)).first()
                answer = row[0] if row else None

                image_urls: list[str] = []
                typical_errors: list[dict] = []
                if answer is not None:
                    image_rows = (
                        (
                            await session.execute(
                                select(SubmissionAnswerImage.image_url)
                                .where(SubmissionAnswerImage.answer_id == answer.id)
                                .order_by(
                                    SubmissionAnswerImage.sort_no.asc(),
                                    SubmissionAnswerImage.id.asc(),
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    image_urls = list(image_rows)

                    error_rows = (
                        await session.execute(
                            select(TypicalErrorPattern, AnswerTypicalErrorRel)
                            .join(
                                AnswerTypicalErrorRel,
                                AnswerTypicalErrorRel.pattern_id
                                == TypicalErrorPattern.id,
                            )
                            .where(AnswerTypicalErrorRel.answer_id == answer.id)
                            .order_by(
                                AnswerTypicalErrorRel.is_primary.desc(),
                                TypicalErrorPattern.hit_count.desc(),
                                TypicalErrorPattern.id.asc(),
                            )
                        )
                    ).all()
                    typical_errors = [
                        {
                            "pattern_name": pattern.pattern_name,
                            "pattern_desc": pattern.pattern_desc,
                            "suggestion_text": pattern.suggestion_text,
                            "is_primary": rel.is_primary,
                        }
                        for pattern, rel in error_rows
                    ]

                return (
                    True,
                    status.HTTP_200_OK,
                    "获取成功",
                    {
                        "question_id": str(question.id),
                        "question": question.content_md,
                        "my_answer": answer.answer_md if answer else None,
                        "duration_sec": answer.duration_sec if answer else 0,
                        "submitted_at": answer.submitted_at if answer else None,
                        "ai_feedback": answer.ai_feedback if answer else None,
                        "teacher_feedback": answer.teacher_feedback if answer else None,
                        "grading_status": self._build_answer_grading_status(answer),
                        "result_status": self._build_result_status_text(answer),
                        "is_answered": bool(answer.is_answered) if answer else False,
                        "image_urls": image_urls,
                        "typical_errors": typical_errors,
                    },
                )
            except Exception as e:
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )

    async def submit_answer(
        self,
        student_id: str,
        quiz_id: str,
        question_id: str,
        answer_md: str | None,
        image_urls: list[str],
        submitted_at: datetime | None,
        duration_sec: int,
    ) -> tuple[bool, int, str, dict | None]:
        """学生提交答案。"""
        submit_time = to_naive_utc(submitted_at) or datetime.utcnow()
        async with AsyncSessionLocal() as session:
            try:
                quiz = await session.get(Quiz, int(quiz_id))
                if quiz is None:
                    return False, status.HTTP_404_NOT_FOUND, "测验不存在", None

                question = await session.get(Question, int(question_id))
                if question is None:
                    return False, status.HTTP_404_NOT_FOUND, "题目不存在", None

                class_id, _ = await self._get_student_class_context(
                    session, int(student_id), int(quiz_id)
                )
                if class_id is None:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "学生未加入该测验对应班级",
                        None,
                    )

                quiz_question = (
                    await session.execute(
                        select(QuizQuestion).where(
                            QuizQuestion.quiz_id == int(quiz_id),
                            QuizQuestion.question_id == int(question_id),
                        )
                    )
                ).scalar_one_or_none()
                if quiz_question is None:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "该题目不属于当前测验",
                        None,
                    )

                submission = (
                    await session.execute(
                        select(QuizSubmission).where(
                            QuizSubmission.quiz_id == int(quiz_id),
                            QuizSubmission.student_id == int(student_id),
                        )
                    )
                ).scalar_one_or_none()
                if submission is None:
                    submission = QuizSubmission(
                        quiz_id=int(quiz_id),
                        class_id=class_id,
                        student_id=int(student_id),
                        status=SubmissionStatus.in_progress,
                        question_count=quiz.question_count,
                        started_at=submit_time,
                    )
                    session.add(submission)
                    await session.flush()

                answer = (
                    await session.execute(
                        select(SubmissionAnswer).where(
                            SubmissionAnswer.submission_id == submission.id,
                            SubmissionAnswer.question_id == int(question_id),
                        )
                    )
                ).scalar_one_or_none()
                if answer is None:
                    answer = SubmissionAnswer(
                        submission_id=submission.id,
                        quiz_id=int(quiz_id),
                        question_id=int(question_id),
                        sort_no=quiz_question.sort_no,
                    )
                    session.add(answer)
                    await session.flush()

                answer.answer_md = answer_md
                answer.is_answered = bool(answer_md or image_urls)
                answer.grading_status = (
                    GradingStatus.grading
                    if answer.is_answered
                    else GradingStatus.pending
                )
                answer.result_status = ResultStatus.unanswered
                answer.duration_sec = duration_sec
                answer.submitted_at = submit_time
                answer.ai_feedback = None
                answer.teacher_feedback = None

                await session.execute(
                    delete(SubmissionAnswerImage).where(
                        SubmissionAnswerImage.answer_id == answer.id
                    )
                )
                for index, image_url in enumerate(image_urls, start=1):
                    session.add(
                        SubmissionAnswerImage(
                            answer_id=answer.id,
                            image_url=image_url,
                            sort_no=index,
                        )
                    )

                answered_count = (
                    await session.execute(
                        select(func.count(SubmissionAnswer.id)).where(
                            SubmissionAnswer.submission_id == submission.id,
                            SubmissionAnswer.is_answered.is_(True),
                        )
                    )
                ).scalar_one()
                submission.answered_count = answered_count
                submission.question_count = quiz.question_count
                if answered_count >= quiz.question_count and quiz.question_count > 0:
                    submission.status = SubmissionStatus.submitted
                    submission.submitted_at = submit_time
                else:
                    submission.status = SubmissionStatus.in_progress

                response_data = {
                    "submission_id": str(submission.id),
                    "answer_id": str(answer.id),
                    "answered_count": answered_count,
                    "submission_status": submission.status.value,
                    "submitted_at": submit_time,
                }
                await session.commit()
                return True, status.HTTP_200_OK, "提交成功", response_data
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )


stu_quiz_service = StuQuizService()
