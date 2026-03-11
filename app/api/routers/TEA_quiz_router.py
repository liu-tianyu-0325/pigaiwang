from fastapi import APIRouter

from app.api.form_validation.TEA_form_validation.TEA_quiz_validation import (
    TEAQuizCreateRequest,
    TEAQuizListRequest,
)
from app.auth.jwt_manager import get_current_user_dependency
from app.services.TEA_services.TEA_quiz_service import TEA_quiz_service

router = APIRouter(tags=["教师端-测验管理"])


def _get_current_teacher_id(current_user) -> int:
    if isinstance(current_user, dict):
        for key in ("id", "user_id"):
            if key in current_user:
                return int(current_user[key])

    for key in ("id", "user_id"):
        if hasattr(current_user, key):
            return int(getattr(current_user, key))

    raise ValueError("无法识别当前登录用户 ID")


@router.post("/list")
async def quiz_list(
    request: TEAQuizListRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_quiz_service.list_quizzes(
        teacher_id=teacher_id,
        quiz_status=request.status,
        page=request.page,
        page_size=request.page_size,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/create")
async def quiz_create(
    request: TEAQuizCreateRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_quiz_service.create_quiz(
        teacher_id=teacher_id,
        quiz_name=request.quiz_name,
        class_ids=request.class_ids,
        question_ids=request.question_ids,
        deadline_at=request.deadline_at,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }