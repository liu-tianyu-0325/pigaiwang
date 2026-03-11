"""学生用户相关API路由。"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.stu_user_response import StuProfileResponseModel
from app.api.form_validation.stu_user_validation import StuProfileRequest
from app.auth import UserClaims, get_current_user_dependency
from app.services.stu_user_service import stu_user_service

router = APIRouter(tags=["学生用户"])


def _ensure_student_identity(
    current_user: UserClaims,
    requested_student_id: str | None,
) -> str:
    student_id = current_user.user_id
    if requested_student_id is not None and requested_student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他学生数据",
        )
    return student_id


@router.post(
    "/profile",
    response_model=BaseResponseModel[StuProfileResponseModel],
    summary="获取学生个人信息",
)
async def get_stu_profile(
    request: StuProfileRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    """获取学生个人信息。"""
    student_id = _ensure_student_identity(current_user, request.student_id)
    log = logger.bind(log_type="user", student_id=student_id)
    log.info("学生请求个人信息")
    res, code, message, data = await stu_user_service.get_profile(student_id)
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}
