"""教师端班级管理业务逻辑。"""

from datetime import datetime
from io import BytesIO

import pandas as pd
from fastapi import UploadFile, status
from sqlalchemy import and_, func, select, update, text

from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    AppUser,
    ClassRoom,
    ClassStudent,
    ClassStudentStatus,
    ImportItemResultStatus,
    ImportStatus,
    QuizSubmission,
    SubmissionStatus,
    StudentImportBatch,
    StudentImportBatchItem,
    StudentProfile,
    UserRole,
    UserStatus,
)
from app.utils.validation import validation_service


class TEAClassService:
    """教师端班级管理服务。"""

    @staticmethod
    def _formal_submission_statuses() -> tuple[SubmissionStatus, ...]:
        return (
            SubmissionStatus.submitted,
            SubmissionStatus.grading,
            SubmissionStatus.reviewed,
        )

    async def list_classes(
        self,
        teacher_id: int | str,
        keyword: str | None = None,
    ) -> tuple[bool, int, str, list[dict] | None]:
        """班级列表。"""
        async with AsyncSessionLocal() as session:
            stmt = select(ClassRoom).where(
                and_(
                    ClassRoom.teacher_id == int(teacher_id),
                    ClassRoom.status == 1,
                )
            )

            if keyword:
                stmt = stmt.where(ClassRoom.class_name.ilike(f"%{keyword}%"))

            stmt = stmt.order_by(ClassRoom.id.desc())
            result = await session.execute(stmt)
            items = result.scalars().all()

            data = [
                {
                    "class_id": item.id,
                    "class_name": item.class_name,
                    "grade_name": item.grade_name,
                    "student_count": item.student_count,
                    "finished_quiz_count": item.finished_quiz_count,
                    "remark": item.remark,
                }
                for item in items
            ]
            return True, status.HTTP_200_OK, "查询班级列表成功", data

    async def create_class(
        self,
        teacher_id: int | str,
        class_name: str,
        grade_name: str,
        remark: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """创建班级。"""
        async with AsyncSessionLocal() as session:
            try:
                new_class = ClassRoom(
                    class_name=class_name,
                    grade_name=grade_name,
                    teacher_id=int(teacher_id),
                    remark=remark,
                    status=1,
                )
                session.add(new_class)
                await session.commit()
                await session.refresh(new_class)

                data = {
                    "class_id": new_class.id,
                    "class_name": new_class.class_name,
                    "grade_name": new_class.grade_name,
                    "student_count": new_class.student_count,
                    "finished_quiz_count": new_class.finished_quiz_count,
                    "remark": new_class.remark,
                }
                return True, status.HTTP_200_OK, "创建班级成功", data
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "创建班级失败，请稍后重试" + str(e),
                    None,
                )

    async def get_class_detail(
        self,
        teacher_id: int | str,
        class_id: int,
    ) -> tuple[bool, int, str, dict | None]:
        """获取班级详情。"""
        async with AsyncSessionLocal() as session:
            stmt = select(ClassRoom).where(
                and_(
                    ClassRoom.id == class_id,
                    ClassRoom.teacher_id == int(teacher_id),
                    ClassRoom.status == 1,
                )
            )
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                return False, status.HTTP_404_NOT_FOUND, "班级不存在", None

            data = {
                "class_id": item.id,
                "class_name": item.class_name,
                "grade_name": item.grade_name,
                "student_count": item.student_count,
                "finished_quiz_count": item.finished_quiz_count,
                "remark": item.remark,
            }
            return True, status.HTTP_200_OK, "获取班级详情成功", data

    async def update_class(
        self,
        teacher_id: int | str,
        class_id: int,
        class_name: str,
        grade_name: str,
        remark: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """编辑班级。"""
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(ClassRoom).where(
                    and_(
                        ClassRoom.id == class_id,
                        ClassRoom.teacher_id == int(teacher_id),
                        ClassRoom.status == 1,
                    )
                )
                result = await session.execute(stmt)
                item = result.scalar_one_or_none()

                if not item:
                    return False, status.HTTP_404_NOT_FOUND, "班级不存在", None

                item.class_name = class_name
                item.grade_name = grade_name
                item.remark = remark

                await session.commit()
                await session.refresh(item)

                data = {
                    "class_id": item.id,
                    "class_name": item.class_name,
                    "grade_name": item.grade_name,
                    "student_count": item.student_count,
                    "finished_quiz_count": item.finished_quiz_count,
                    "remark": item.remark,
                }
                return True, status.HTTP_200_OK, "编辑班级成功", data
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "编辑班级失败，请稍后重试" + str(e),
                    None,
                )

    async def delete_class(
        self,
        teacher_id: int | str,
        class_id: int,
    ) -> tuple[bool, int, str, None]:
        """删除班级。

        当前先采用业务软删除：status = 0。
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(ClassRoom).where(
                    and_(
                        ClassRoom.id == class_id,
                        ClassRoom.teacher_id == int(teacher_id),
                        ClassRoom.status == 1,
                    )
                )
                result = await session.execute(stmt)
                item = result.scalar_one_or_none()

                if not item:
                    return False, status.HTTP_404_NOT_FOUND, "班级不存在或已删除", None

                item.status = 0
                await session.commit()
                return True, status.HTTP_200_OK, "删除班级成功", None
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "删除班级失败，请稍后重试" + str(e),
                    None,
                )

    async def get_class_students(
        self,
        teacher_id: int | str,
        class_id: int,
    ) -> tuple[bool, int, str, list[dict] | None]:
        """获取某个班级的学生列表。"""
        async with AsyncSessionLocal() as session:
            class_stmt = select(ClassRoom).where(
                and_(
                    ClassRoom.id == class_id,
                    ClassRoom.teacher_id == int(teacher_id),
                    ClassRoom.status == 1,
                )
            )
            class_result = await session.execute(class_stmt)
            class_obj = class_result.scalar_one_or_none()

            if not class_obj:
                return False, status.HTTP_404_NOT_FOUND, "班级不存在", None

            stmt = (
                select(
                    AppUser.id.label("student_id"),
                    AppUser.real_name.label("student_name"),
                    StudentProfile.student_no.label("student_no"),
                    func.count(QuizSubmission.id).label("participated_quiz_count"),
                    func.coalesce(func.avg(QuizSubmission.accuracy_rate), 0).label(
                        "average_accuracy_rate"
                    ),
                    func.max(QuizSubmission.submitted_at).label("recent_submitted_at"),
                )
                .select_from(ClassStudent)
                .join(AppUser, AppUser.id == ClassStudent.student_id)
                .join(StudentProfile, StudentProfile.user_id == AppUser.id)
                .outerjoin(
                    QuizSubmission,
                    and_(
                        QuizSubmission.student_id == AppUser.id,
                        QuizSubmission.class_id == class_id,
                        QuizSubmission.status.in_(self._formal_submission_statuses()),
                    ),
                )
                .where(ClassStudent.class_id == class_id)
                .where(ClassStudent.join_status == ClassStudentStatus.active)
                .group_by(AppUser.id, AppUser.real_name, StudentProfile.student_no)
                .order_by(AppUser.id.desc())
            )

            result = await session.execute(stmt)
            rows = result.all()

            data = [
                {
                    "student_id": row.student_id,
                    "student_no": row.student_no,
                    "student_name": row.student_name,
                    "participated_quiz_count": int(row.participated_quiz_count or 0),
                    "average_accuracy_rate": float(row.average_accuracy_rate or 0),
                    "recent_submitted_at": row.recent_submitted_at,
                }
                for row in rows
            ]
            return True, status.HTTP_200_OK, "获取班级学生列表成功", data

    async def import_students(
        self,
        operator_id: int | str,
        class_id: int,
        students: list[dict],
    ) -> tuple[bool, int, str, dict | None]:
        """批量导入学生。

        当前先做 JSON 批量导入版本，不做 Excel / 文件上传。
        """
        async with AsyncSessionLocal() as session:
            try:
                class_stmt = select(ClassRoom).where(
                    and_(
                        ClassRoom.id == class_id,
                        ClassRoom.status == 1,
                    )
                )
                class_result = await session.execute(class_stmt)
                class_obj = class_result.scalar_one_or_none()

                if not class_obj:
                    return False, status.HTTP_404_NOT_FOUND, "班级不存在", None

                # 自动校正 class_student 主键序列，避免历史数据导致主键冲突
                await session.execute(
                    text(
                        """
                        SELECT setval(
                            pg_get_serial_sequence('class_student', 'id'),
                            COALESCE((SELECT MAX(id) FROM class_student), 1),
                            true
                        )
                        """
                    )
                )

                batch_no = f"TEA_IMPORT_{class_id}_{int(datetime.utcnow().timestamp())}"

                batch = StudentImportBatch(
                    class_id=class_id,
                    operator_id=int(operator_id),
                    batch_no=batch_no,
                    total_count=len(students),
                    success_count=0,
                    fail_count=0,
                    import_status=ImportStatus.processing,
                )
                session.add(batch)
                await session.flush()

                success_count = 0
                fail_count = 0

                for idx, student in enumerate(students, start=1):
                    student_no = student["student_no"]
                    student_name = student["student_name"]
                    initial_password = student["initial_password"]

                    exist_stmt = (
                        select(AppUser, StudentProfile)
                        .join(StudentProfile, StudentProfile.user_id == AppUser.id)
                        .where(StudentProfile.student_no == student_no)
                    )
                    exist_result = await session.execute(exist_stmt)
                    exist_row = exist_result.first()

                    if exist_row:
                        fail_count += 1
                        session.add(
                            StudentImportBatchItem(
                                batch_id=batch.id,
                                row_no=idx,
                                student_no=student_no,
                                student_name=student_name,
                                username=student_no,
                                result_status=ImportItemResultStatus.duplicate,
                                error_message="学号已存在",
                            )
                        )
                        continue

                    password_hash = validation_service.get_hashed_password(
                        initial_password
                    )

                    new_user = AppUser(
                        role=UserRole.student,
                        username=student_no,
                        password_hash=password_hash,
                        real_name=student_name,
                        status=UserStatus.enabled.value,
                    )
                    session.add(new_user)
                    await session.flush()

                    new_profile = StudentProfile(
                        user_id=new_user.id,
                        student_no=student_no,
                    )
                    session.add(new_profile)

                    new_rel = ClassStudent(
                        class_id=class_id,
                        student_id=new_user.id,
                        join_status=ClassStudentStatus.active,
                    )
                    session.add(new_rel)

                    session.add(
                        StudentImportBatchItem(
                            batch_id=batch.id,
                            row_no=idx,
                            student_no=student_no,
                            student_name=student_name,
                            username=student_no,
                            result_status=ImportItemResultStatus.success,
                            user_id=new_user.id,
                        )
                    )
                    success_count += 1

                batch.success_count = success_count
                batch.fail_count = fail_count
                batch.import_status = (
                    ImportStatus.finished
                    if fail_count == 0
                    else ImportStatus.partial_failed
                )
                batch.finished_at = datetime.utcnow()

                await session.execute(
                    update(ClassRoom)
                    .where(ClassRoom.id == class_id)
                    .values(student_count=ClassRoom.student_count + success_count)
                )

                await session.commit()

                data = {
                    "batch_no": batch_no,
                    "total_count": len(students),
                    "success_count": success_count,
                    "fail_count": fail_count,
                }
                return True, status.HTTP_200_OK, "批量导入学生完成", data

            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "批量导入学生失败，请稍后重试" + str(e),
                    None,
                )

    async def import_students_xlsx(
        self,
        operator_id: int | str,
        class_id: int,
        file: UploadFile,
    ) -> tuple[bool, int, str, dict | None]:
        """通过 xlsx 文件批量导入学生。"""
        try:
            filename = file.filename or ""
            if not filename.lower().endswith(".xlsx"):
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "仅支持 .xlsx 文件导入",
                    None,
                )

            file_bytes = await file.read()
            if not file_bytes:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "上传文件为空",
                    None,
                )

            df = pd.read_excel(BytesIO(file_bytes), dtype=str)
            df.columns = [str(col).strip() for col in df.columns]

            if df.empty:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Excel 中没有可导入的数据",
                    None,
                )

            column_alias_map = {
                "student_no": ["student_no", "学号"],
                "student_name": ["student_name", "姓名", "学生姓名"],
                "initial_password": ["initial_password", "初始密码", "密码"],
            }

            resolved_columns: dict[str, str] = {}
            for standard_name, alias_list in column_alias_map.items():
                matched_column = next(
                    (alias for alias in alias_list if alias in df.columns), None
                )
                if not matched_column:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        f"Excel 缺少必要列: {standard_name}",
                        None,
                    )
                resolved_columns[standard_name] = matched_column

            students: list[dict[str, str]] = []
            for excel_index, row in df.iterrows():
                row_no = excel_index + 2

                student_no = str(
                    row.get(resolved_columns["student_no"], "") or ""
                ).strip()
                student_name = str(
                    row.get(resolved_columns["student_name"], "") or ""
                ).strip()
                initial_password = str(
                    row.get(resolved_columns["initial_password"], "") or ""
                ).strip()

                if student_no.lower() == "nan":
                    student_no = ""
                if student_name.lower() == "nan":
                    student_name = ""
                if initial_password.lower() == "nan":
                    initial_password = ""

                if not student_no:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        f"第 {row_no} 行学号为空",
                        None,
                    )

                if not student_name:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        f"第 {row_no} 行姓名为空",
                        None,
                    )

                if not initial_password:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        f"第 {row_no} 行初始密码为空",
                        None,
                    )

                students.append(
                    {
                        "student_no": student_no,
                        "student_name": student_name,
                        "initial_password": initial_password,
                    }
                )

            if not students:
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    "Excel 中没有可导入的数据",
                    None,
                )

            return await self.import_students(
                operator_id=operator_id,
                class_id=class_id,
                students=students,
            )

        except Exception as e:
            return (
                False,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "解析 xlsx 文件失败，请检查文件内容格式" + str(e),
                None,
            )


TEA_class_service = TEAClassService()