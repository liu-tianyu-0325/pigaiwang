"""教师端班级管理相关API路由。"""

from fastapi import APIRouter, File, Form, UploadFile
from loguru import logger

from app.api.form_response import BaseResponseModel
from app.api.form_response.TEA_form_response.TEA_class_response import (
    TEAClassDetailResponseModel,
    TEAClassImportStudentsResponseModel,
    TEAClassListItemResponseModel,
    TEAClassStudentListItemResponseModel,
)
from app.api.form_validation.TEA_form_validation.TEA_class_validation import (
    TEABatchImportStudentsRequest,
    TEACreateClassRequest,
    TEAGetClassStudentsRequest,
    TEAListClassRequest,
    TEAUpdateClassRequest,
)
from app.auth import UserClaims, get_current_user_dependency
from app.services.TEA_services.TEA_class_service import TEA_class_service

router = APIRouter(tags=["教师端班级管理"])


@router.post(
    "/list",
    response_model=BaseResponseModel[list[TEAClassListItemResponseModel]],
    summary="班级列表",
)
async def list_classes(
    request: TEAListClassRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师查询班级列表")
    res, code, message, data = await TEA_class_service.list_classes(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/create",
    response_model=BaseResponseModel[TEAClassDetailResponseModel],
    summary="创建班级",
)
async def create_class(
    request: TEACreateClassRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info("教师创建班级")
    res, code, message, data = await TEA_class_service.create_class(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/detail",
    response_model=BaseResponseModel[TEAClassDetailResponseModel],
    summary="获取班级详情",
)
async def get_class_detail(
    class_id: int,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师查询班级详情 class_id={class_id}")
    res, code, message, data = await TEA_class_service.get_class_detail(
        teacher_id=current_user.user_id,
        class_id=class_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/update",
    response_model=BaseResponseModel[TEAClassDetailResponseModel],
    summary="编辑班级",
)
async def update_class(
    request: TEAUpdateClassRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师编辑班级 class_id={request.class_id}")
    res, code, message, data = await TEA_class_service.update_class(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/delete",
    response_model=BaseResponseModel,
    summary="删除班级",
)
async def delete_class(
    class_id: int,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师删除班级 class_id={class_id}")
    res, code, message, data = await TEA_class_service.delete_class(
        teacher_id=current_user.user_id,
        class_id=class_id,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/students",
    response_model=BaseResponseModel[list[TEAClassStudentListItemResponseModel]],
    summary="班级学生列表",
)
async def get_class_students(
    request: TEAGetClassStudentsRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师查询班级学生列表 class_id={request.class_id}")
    res, code, message, data = await TEA_class_service.get_class_students(
        teacher_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/import_students",
    response_model=BaseResponseModel[TEAClassImportStudentsResponseModel],
    summary="批量导入学生(JSON)",
)
async def import_students(
    request: TEABatchImportStudentsRequest,
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师批量导入学生(JSON) class_id={request.class_id}")
    res, code, message, data = await TEA_class_service.import_students(
        operator_id=current_user.user_id,
        **request.model_dump(),
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}


@router.post(
    "/import_students_xlsx",
    response_model=BaseResponseModel[TEAClassImportStudentsResponseModel],
    summary="批量导入学生(XLSX)",
)
async def import_students_xlsx(
    class_id: int = Form(..., description="班级ID"),
    file: UploadFile = File(..., description="xlsx文件"),
    current_user: UserClaims = get_current_user_dependency,
):
    log = logger.bind(log_type="user", user_id=current_user.user_id)
    log.info(f"教师批量导入学生(XLSX) class_id={class_id}, filename={file.filename}")
    res, code, message, data = await TEA_class_service.import_students_xlsx(
        operator_id=current_user.user_id,
        class_id=class_id,
        file=file,
    )
    log.info(message)
    return {"res": res, "code": code, "message": message, "data": data}