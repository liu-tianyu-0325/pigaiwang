from fastapi import APIRouter

from app.api.form_validation.TEA_form_validation.TEA_analysis_validation import (
    TEAQuizAnalysisSummaryRequest,
    TEAQuizClassQuestionStatsRequest,
    TEAQuizClassStatsRequest,
    TEAQuizNameListRequest,
    TEAQuizStudentAnswerDetailRequest,
    TEAQuizStudentAnswerListRequest,
)
from app.auth.jwt_manager import get_current_user_dependency
from app.services.TEA_services.TEA_analysis_service import TEA_analysis_service

router = APIRouter(tags=["教师端-测验分析"])


def _get_current_teacher_id(current_user) -> int:
    if isinstance(current_user, dict):
        for key in ("id", "user_id"):
            if key in current_user:
                return int(current_user[key])

    for key in ("id", "user_id"):
        if hasattr(current_user, key):
            return int(getattr(current_user, key))

    raise ValueError("无法识别当前登录用户 ID")


@router.post("/summary")
async def analysis_summary(
    request: TEAQuizAnalysisSummaryRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_analysis_summary(
        teacher_id=teacher_id,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/quiz_name_list")
async def quiz_name_list(
    request: TEAQuizNameListRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_quiz_name_list(
        teacher_id=teacher_id,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/quiz_class_stats")
async def quiz_class_stats(
    request: TEAQuizClassStatsRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_quiz_class_stats(
        teacher_id=teacher_id,
        quiz_id=request.quiz_id,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/quiz_class_question_stats")
async def quiz_class_question_stats(
    request: TEAQuizClassQuestionStatsRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_quiz_class_question_stats(
        teacher_id=teacher_id,
        quiz_id=request.quiz_id,
        class_id=request.class_id,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/student_answer_list")
async def student_answer_list(
    request: TEAQuizStudentAnswerListRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_student_answer_list(
        teacher_id=teacher_id,
        quiz_id=request.quiz_id,
        class_id=request.class_id,
        question_id=request.question_id,
        page=request.page,
        page_size=request.page_size,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }


@router.post("/student_answer_detail")
async def student_answer_detail(
    request: TEAQuizStudentAnswerDetailRequest,
    current_user=get_current_user_dependency,
):
    teacher_id = _get_current_teacher_id(current_user)
    res, code, message, data = await TEA_analysis_service.get_student_answer_detail(
        teacher_id=teacher_id,
        submission_id=request.submission_id,
    )
    return {
        "res": res,
        "code": code,
        "message": message,
        "data": data,
    }