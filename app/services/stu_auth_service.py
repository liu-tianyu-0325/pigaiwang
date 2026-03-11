"""学生认证服务。"""

from fastapi import status
from sqlalchemy import select, update

from app.auth import jwt_manager
from app.common.time_ import time_now_naive
from app.storage import AsyncSessionLocal, UserStatus
from app.storage.database_models import AppUser, StudentProfile, UserRole
from app.utils.validation import validation_service


class StuAuthService:
    """处理学生登录认证相关逻辑。"""

    async def logout(self, student_id: str) -> tuple[bool, int, str, dict | None]:
        """学生退出登录。"""
        try:
            logged_out = await jwt_manager.logout_user(student_id)
            return (
                True,
                status.HTTP_200_OK,
                "退出成功",
                {"student_id": student_id, "logged_out": logged_out},
            )
        except Exception as e:
            return (
                False,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"操作失败，请稍后重试: {e}",
                None,
            )

    async def register_by_student_no(
        self,
        student_no: str,
        real_name: str,
        password: str,
        username: str | None = None,
        mobile: str | None = None,
        email: str | None = None,
        gender: int | None = None,
        remark: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """学生通过学号注册账号。"""
        login_username = username or student_no

        async with AsyncSessionLocal() as session:
            try:
                existing_user = await session.execute(
                    select(AppUser.id).where(AppUser.username == login_username)
                )
                if existing_user.scalar_one_or_none() is not None:
                    return False, status.HTTP_400_BAD_REQUEST, "用户名已存在", None

                existing_student = await session.execute(
                    select(StudentProfile.id).where(
                        StudentProfile.student_no == student_no
                    )
                )
                if existing_student.scalar_one_or_none() is not None:
                    return False, status.HTTP_400_BAD_REQUEST, "学号已存在", None

                user = AppUser(
                    role=UserRole.student,
                    username=login_username,
                    password_hash=validation_service.get_hashed_password(password),
                    real_name=real_name,
                    mobile=mobile,
                    email=email,
                    status=UserStatus.enabled.value,
                )
                session.add(user)
                await session.flush()

                student_profile = StudentProfile(
                    user_id=user.id,
                    student_no=student_no,
                    gender=gender,
                    remark=remark,
                )
                session.add(student_profile)
                await session.flush()
                response_data = {
                    "user_id": str(user.id),
                    "username": user.username,
                    "real_name": user.real_name,
                    "student_no": student_profile.student_no,
                }
                await session.commit()

                return (
                    True,
                    status.HTTP_200_OK,
                    "注册成功",
                    response_data,
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )

    async def login_by_student_no_password(
        self,
        student_no: str,
        password: str,
        device_id: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """学生通过学号和密码登录。"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(AppUser, StudentProfile)
                    .join(StudentProfile, StudentProfile.user_id == AppUser.id)
                    .where(StudentProfile.student_no == student_no)
                )
                row = result.first()

                if not row:
                    return False, status.HTTP_400_BAD_REQUEST, "学号或密码错误", None

                user, student_profile = row

                if user.role != UserRole.student:
                    return False, status.HTTP_403_FORBIDDEN, "该账号不是学生账号", None

                if user.status != UserStatus.enabled.value:
                    return False, status.HTTP_400_BAD_REQUEST, "该账号已被禁用", None

                if not validation_service.verify_password(password, user.password_hash):
                    return False, status.HTTP_400_BAD_REQUEST, "学号或密码错误", None

                token_info = await jwt_manager.generate_token(
                    str(user.id), device_id=device_id
                )

                stmt = (
                    update(AppUser)
                    .where(AppUser.id == user.id)
                    .values(last_login_at=time_now_naive())
                )
                await session.execute(stmt)
                response_data = {
                    "user_id": str(user.id),
                    "username": user.username,
                    "real_name": user.real_name,
                    "role": user.role.value,
                    "student_no": student_profile.student_no,
                    "token_info": token_info,
                }
                await session.commit()

                return (
                    True,
                    status.HTTP_200_OK,
                    "登录成功",
                    response_data,
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"操作失败，请稍后重试: {e}",
                    None,
                )


stu_auth_service = StuAuthService()
