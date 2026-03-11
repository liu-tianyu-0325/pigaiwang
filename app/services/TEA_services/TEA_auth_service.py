"""教师端认证业务逻辑。"""

from fastapi import status
from sqlalchemy import select, update

from app.auth import jwt_manager
from app.common.time_ import time_now_naive
from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    AppUser,
    TeacherProfile,
    UserRole,
    UserStatus,
)
from app.utils.validation import validation_service


class TEAAuthService:
    """教师端认证服务。"""

    async def login_by_username_password(
        self,
        username: str,
        password: str,
        device_id: str | None = None,
    ) -> tuple[bool, int, str, dict | None]:
        """教师账号密码登录。"""
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    select(AppUser, TeacherProfile)
                    .outerjoin(TeacherProfile, TeacherProfile.user_id == AppUser.id)
                    .where(AppUser.username == username)
                    .where(AppUser.role == UserRole.teacher)
                )
                result = await session.execute(stmt)
                row = result.first()

                if not row:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "用户名或密码错误",
                        None,
                    )

                user, teacher_profile = row

                if not validation_service.verify_password(password, user.password_hash):
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "用户名或密码错误",
                        None,
                    )

                if user.status == UserStatus.disabled.value:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "该账号已被禁用",
                        None,
                    )

                token_info = await jwt_manager.generate_token(
                    str(user.id),
                    device_id=device_id,
                )

                stmt = (
                    update(AppUser)
                    .where(AppUser.id == user.id)
                    .values(last_login_at=time_now_naive())
                )
                await session.execute(stmt)
                await session.flush()

                data = {
                    "user_id": user.id,
                    "username": user.username,
                    "real_name": user.real_name,
                    "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                    "subject_name": teacher_profile.subject_name if teacher_profile else None,
                    "title_name": teacher_profile.title_name if teacher_profile else None,
                    "token_info": {
                        "access_token": token_info.access_token,
                        "token_type": token_info.token_type,
                        "expires_in": token_info.expires_in,
                    },
                }
                return True, status.HTTP_200_OK, "登录成功", data

            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "操作失败，请稍后重试" + str(e),
                    None,
                )

    async def logout(self, user_id: int | str) -> tuple[bool, int, str, None]:
        """教师退出登录。"""
        try:
            await jwt_manager.logout_user(str(user_id))
            return True, status.HTTP_200_OK, "安全退出", None
        except Exception:
            return (
                False,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "操作失败，请稍后重试",
                None,
            )


TEA_auth_service = TEAAuthService()