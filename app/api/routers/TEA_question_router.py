"""教师端习题管理相关API路由。"""

from fastapi import APIRouter, File, Form, UploadFile
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.TEA_form_response.TEA_question_response import (
    TEAQuestionCountResponseModel,
    TEAQuestionDetailResponseModel,
    TEAQuestionSearchResponseModel,
    TEATagItemResponseModel,
)
from app.api.form_validation.TEA_form_validation.TEA_question_validation import (
    TEACreateTagRequest,
    TEADeleteQuestionRequest,
    TEADeleteTagRequest,
    TEAGetQuestionDetailRequest,
    TEAQuestionSearchRequest,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.TEA_services.TEA_question_service import TEA_question_service

router = APIRouter(tags=["教师端习题管理"])


def _normalize_upload_files(
    images: list[UploadFile] | None,
) -> list[UploadFile]:
    """过滤 Swagger 未上传文件时的空占位。"""
    if not images:
        return []

    valid_files: list[UploadFile] = []
    for image in images:
        if image is None:
            continue

        filename = (image.filename or "").strip()
        content_type = (image.content_type or "").strip()

        if filename in {"", "string"} and content_type in {"", "application/octet-stream"}:
            continue

        valid_files.append(image)

    return valid_files


@router.get(
    "/count",
    response_model=BaseResponseModel[TEAQuestionCountResponseModel],
    summary="获取题目总数",
)
async def get_question_count(
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师查询题目总数")
    res, code, message, data = await TEA_question_service.get_question_count(
        teacher_id=current_user.user_id
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/tag/create",
    response_model=BaseResponseModel[TEATagItemResponseModel],
    summary="新增标签",
)
async def create_tag(
    request: TEACreateTagRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师新增标签 tag_name={request.tag_name}")
    res, code, message, data = await TEA_question_service.create_tag(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/tag/delete",
    response_model=BaseResponseModel,
    summary="删除标签",
)
async def delete_tag(
    request: TEADeleteTagRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师删除标签 tag_id={request.tag_id}")
    res, code, message, data = await TEA_question_service.delete_tag(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.get(
    "/tag/list",
    response_model=BaseResponseModel[list[TEATagItemResponseModel]],
    summary="标签列表",
)
async def list_tags(
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师查询标签列表")
    res, code, message, data = await TEA_question_service.list_tags(
        teacher_id=current_user.user_id
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/create",
    response_model=BaseResponseModel[TEAQuestionDetailResponseModel],
    summary="新增题目（支持多图上传）",
)
async def create_question(
    content_md: str | None = Form(default=None, description="题目内容"),
    reference_answer: str | None = Form(default=None, description="参考答案"),
    tag_ids_json: str | None = Form(default="[]", description='标签ID列表，支持 "[1,2]" 或 "1,2"'),
    images: list[UploadFile] | None = File(default=None, description="题目图片（可多张）"),
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师新增题目")

    normalized_images = _normalize_upload_files(images)

    res, code, message, data = await TEA_question_service.create_question(
        teacher_id=current_user.user_id,
        content_md=content_md,
        reference_answer=reference_answer,
        tag_ids_json=tag_ids_json,
        images=normalized_images,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/update",
    response_model=BaseResponseModel[TEAQuestionDetailResponseModel],
    summary="编辑题目（支持替换图片或追加图片）",
)
async def update_question(
    question_id: int = Form(..., description="题目ID"),
    content_md: str | None = Form(default=None, description="题目内容"),
    reference_answer: str | None = Form(default=None, description="参考答案"),
    tag_ids_json: str | None = Form(default=None, description='标签ID列表，支持 "[1,2]" 或 "1,2"'),
    replace_images: bool = Form(default=False, description="是否替换原图片，false 为追加"),
    images: list[UploadFile] | None = File(default=None, description="题目图片（可多张）"),
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(
        f"教师编辑题目 question_id={question_id}, "
        f"replace_images={replace_images}"
    )

    normalized_images = _normalize_upload_files(images)

    res, code, message, data = await TEA_question_service.update_question(
        teacher_id=current_user.user_id,
        question_id=question_id,
        content_md=content_md,
        reference_answer=reference_answer,
        tag_ids_json=tag_ids_json,
        replace_images=replace_images,
        images=normalized_images,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/delete",
    response_model=BaseResponseModel,
    summary="删除题目",
)
async def delete_question(
    request: TEADeleteQuestionRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师删除题目 question_id={request.question_id}")
    res, code, message, data = await TEA_question_service.delete_question(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/detail",
    response_model=BaseResponseModel[TEAQuestionDetailResponseModel],
    summary="获取题目详情",
)
async def get_question_detail(
    request: TEAGetQuestionDetailRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师获取题目详情 question_id={request.question_id}")
    res, code, message, data = await TEA_question_service.get_question_detail(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/search",
    response_model=BaseResponseModel[TEAQuestionSearchResponseModel],
    summary="搜索题目",
)
async def search_questions(
    request: TEAQuestionSearchRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师搜索题目")
    res, code, message, data = await TEA_question_service.search_questions(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}