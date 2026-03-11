"""教师端总览相关API路由。"""

from fastapi import APIRouter
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.TEA_form_response.TEA_dashboard_response import (
    TEADashboardOverviewResponseModel,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.TEA_services.TEA_dashboard_service import TEA_dashboard_service

router = APIRouter(tags=["教师端总览"])


@router.get(
    "/overview",
    response_model=BaseResponseModel[TEADashboardOverviewResponseModel],
    summary="教师端首页总览",
)
async def get_dashboard_overview(
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师查询总览首页")
    res, code, message, data = await TEA_dashboard_service.get_overview(
        teacher_id=current_user.user_id
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}