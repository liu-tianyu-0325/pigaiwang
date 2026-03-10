"""学生认证相关API路由。"""

from fastapi import APIRouter
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
from app.services.stu_auth_service import stu_auth_service

router = APIRouter(tags=["学生认证"])


@router.post(
    "/logout",
    response_model=BaseResponseModel[StuLogoutResponseModel],
    summary="学生退出登录",
)
async def stu_logout(request: StuLogoutRequest):
    """学生退出登录。"""
    log = logger.bind(log_type="user", student_id=request.student_id)
    log.info("学生退出登录")
    res, code, message, data = await stu_auth_service.logout(request.student_id)
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
