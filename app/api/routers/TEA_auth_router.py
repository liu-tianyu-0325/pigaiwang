"""教师端认证相关API路由。"""

from fastapi import APIRouter
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.TEA_form_response.TEA_auth_response import (
    TEALoginResponseModel,
)
from app.api.form_validation.TEA_form_validation.TEA_auth_validation import (
    TEAUsernameLoginRequest,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.TEA_services.TEA_auth_service import TEA_auth_service

router = APIRouter(tags=["教师端认证"])


@router.post(
    "/login",
    response_model=BaseResponseModel[TEALoginResponseModel],
    summary="教师账号密码登录",
)
async def tea_login(login_request: TEAUsernameLoginRequest):
    """教师通过账号密码登录系统。"""
    payload = login_request.model_dump()
    log = logger.bind(log_type="user")

    log.info(f"教师账号 {login_request.username} 尝试登录教师端")
    res, code, message, data = await TEA_auth_service.login_by_username_password(
        **payload
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.get(
    "/logout",
    response_model=BaseResponseModel,
    summary="教师退出登录",
)
async def tea_logout(
    current_user: UserClaims = get_current_user_dependency,
):
    """教师主动退出登录。"""
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师退出登录")
    res, code, message, data = await TEA_auth_service.logout(current_user.user_id)
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}