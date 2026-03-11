"""学生认证相关API路由。"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.stu_user_response import (
    StuLoginResponseModel,
    StuLogoutResponseModel,
    StuRegisterResponseModel,
)
from app.api.form_validation.stu_user_validation import (
    StuLoginByStudentNoPasswordRequest,
    StuLogoutRequest,
    StuRegisterByStudentNoRequest,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.stu_auth_service import stu_auth_service

router = APIRouter(tags=["学生认证"])


def _ensure_student_identity(
    current_user: UserClaims,
    requested_student_id: str | None,
) -> str:
    student_id = current_user.user_id
    if requested_student_id is not None and requested_student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作其他学生账号",
        )
    return student_id


@router.post(
    "/logout",
    response_model=BaseResponseModel[StuLogoutResponseModel],
    summary="学生退出登录",
)
async def stu_logout(
    request: StuLogoutRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """学生退出登录。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(log_type="user", student_id=student_id)
    log.info("学生退出登录")
    res, code, message, data = await stu_auth_service.logout(student_id)
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/register",
    response_model=BaseResponseModel[StuRegisterResponseModel],
    summary="学生学号注册",
)
async def stu_register_by_student_no(
    register_request: StuRegisterByStudentNoRequest,
):
    """学生通过学号注册账号。"""
    payload = register_request.model_dump()
    log = logger.bind(log_type="user", student_no=register_request.student_no)

    log.info(f"学号为 {register_request.student_no} 的学生尝试注册")
    res, code, message, data = await stu_auth_service.register_by_student_no(**payload)
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/login",
    response_model=BaseResponseModel[StuLoginResponseModel],
    summary="学生学号密码登录",
)
async def stu_login_by_student_no_password(
    login_request: StuLoginByStudentNoPasswordRequest,
):
    """学生通过学号和密码登录系统，获取访问令牌。"""
    payload = login_request.model_dump()
    log = logger.bind(log_type="user", student_no=login_request.student_no)

    log.info(f"学号为 {login_request.student_no} 的学生尝试登录")
    res, code, message, data = await stu_auth_service.login_by_student_no_password(
        **payload
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}
