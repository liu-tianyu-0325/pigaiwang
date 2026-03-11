"""学生测验相关API路由。"""

from fastapi import APIRouter
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.stu_quiz_response import (
    StuAnswerGradingViewResponseModel,
    StuQuestionDetailResponseModel,
    StuQuizDetailResponseModel,
    StuQuizListResponseModel,
    StuSubmitAnswerResponseModel,
    StuSubmitQuizResponseModel,
)
from app.api.form_validation.stu_quiz_validation import (
    StuAnswerGradingViewRequest,
    StuQuestionDetailRequest,
    StuQuizDetailRequest,
    StuQuizListRequest,
    StuSubmitAnswerRequest,
    StuSubmitQuizRequest,
)
from app.services.stu_quiz_service import stu_quiz_service

router = APIRouter(tags=["学生测验"])


@router.post(
    "/list",
    response_model=BaseResponseModel[StuQuizListResponseModel],
    summary="获取学生测验列表",
)
async def get_stu_quiz_list(request: StuQuizListRequest):
    """获取测验列表。"""
    log = logger.bind(log_type="user", student_id=request.student_id)
    log.info("学生请求测验列表")
    res, code, message, data = await stu_quiz_service.get_quiz_list(
        request.student_id,
        request.status,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/detail",
    response_model=BaseResponseModel[StuQuizDetailResponseModel],
    summary="获取学生测验详情",
)
async def get_stu_quiz_detail(request: StuQuizDetailRequest):
    """获取测验详情与题目状态列表。"""
    log = logger.bind(
        log_type="user", student_id=request.student_id, quiz_id=request.quiz_id
    )
    log.info("学生请求测验详情")
    res, code, message, data = await stu_quiz_service.get_quiz_detail(
        request.student_id,
        request.quiz_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/question/detail",
    response_model=BaseResponseModel[StuQuestionDetailResponseModel],
    summary="获取学生题目详情",
)
async def get_stu_question_detail(request: StuQuestionDetailRequest):
    """获取题目详情、我的答案和批改信息。"""
    log = logger.bind(
        log_type="user",
        student_id=request.student_id,
        question_id=request.question_id,
        quiz_id=request.quiz_id,
    )
    log.info("学生请求题目详情")
    res, code, message, data = await stu_quiz_service.get_question_detail(
        request.student_id,
        request.question_id,
        request.quiz_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/answer/submit",
    response_model=BaseResponseModel[StuSubmitAnswerResponseModel],
    summary="学生提交答案",
)
async def submit_stu_answer(request: StuSubmitAnswerRequest):
    """学生提交题目答案。"""
    log = logger.bind(
        log_type="user",
        student_id=request.student_id,
        quiz_id=request.quiz_id,
        question_id=request.question_id,
    )
    log.info("学生提交答案")
    res, code, message, data = await stu_quiz_service.submit_answer(
        **request.model_dump()
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/submit",
    response_model=BaseResponseModel[StuSubmitQuizResponseModel],
    summary="学生提交测验",
)
async def submit_stu_quiz(request: StuSubmitQuizRequest):
    """学生提交整份测验，并自动触发 AI 批改。"""
    log = logger.bind(
        log_type="user",
        student_id=request.student_id,
        quiz_id=request.quiz_id,
    )
    log.info("学生提交测验")
    res, code, message, data = await stu_quiz_service.submit_quiz(
        **request.model_dump()
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/answer/grading-view",
    response_model=BaseResponseModel[StuAnswerGradingViewResponseModel],
    summary="查看 AI 批改视图",
)
async def get_stu_answer_grading_view(request: StuAnswerGradingViewRequest):
    """查看指定答案的 AI 批改详情。"""
    log = logger.bind(
        log_type="user",
        student_id=request.student_id,
        answer_id=request.answer_id,
    )
    log.info("学生查看 AI 批改视图")
    res, code, message, data = await stu_quiz_service.get_answer_grading_view(
        request.student_id,
        request.answer_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}
