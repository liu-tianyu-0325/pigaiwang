"""学生用户相关API路由。"""

from fastapi import APIRouter
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.stu_user_response import StuProfileResponseModel
from app.api.form_validation.stu_user_validation import StuProfileRequest
from app.services.stu_user_service import stu_user_service

router = APIRouter(tags=["学生用户"])


@router.post(
    "/profile",
    response_model=BaseResponseModel[StuProfileResponseModel],
    summary="获取学生个人信息",
)
async def get_stu_profile(request: StuProfileRequest):
    """获取学生个人信息。"""
    log = logger.bind(log_type="user", student_id=request.student_id)
    log.info("学生请求个人信息")
    res, code, message, data = await stu_user_service.get_profile(request.student_id)
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}
