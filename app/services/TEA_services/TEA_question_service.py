"""教师端习题管理业务逻辑。"""

import json
import os
import uuid
from typing import Any

import boto3
from botocore.config import Config
from fastapi import UploadFile, status
from sqlalchemy import and_, delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import base_configs
from app.storage.base import AsyncSessionLocal
from app.storage.database_models import (
    Question,
    QuestionImage,
    QuestionStatus,
    QuestionTagRel,
    QuestionType,
    Tag,
)
from app.utils.snowflake_id import generate_id


class TEAQuestionService:
    """教师端习题管理服务。"""

    def _get_question_bucket_name(self) -> str:
        candidate_attr_names = [
            "QUESTION_IMAGE_BUCKET",
            "QUESTION_S3_BUCKET",
            "S3_BUCKET_NAME",
            "S3_BUCKET",
            "RUSTFS_BUCKET",
        ]
        for attr_name in candidate_attr_names:
            bucket_name = getattr(base_configs, attr_name, None)
            if bucket_name:
                return str(bucket_name)

        raise ValueError(
            "未找到题目图片桶配置，请在 base_configs 中补充 QUESTION_IMAGE_BUCKET / S3_BUCKET_NAME 等桶名配置"
        )

    def _build_s3_client(self):
        secure_value = getattr(base_configs, "S3_SECURE", False)
        if isinstance(secure_value, str):
            use_ssl = secure_value.lower() in {"1", "true", "yes", "on"}
        else:
            use_ssl = bool(secure_value)

        max_pool_connections = int(getattr(base_configs, "S3_MAX_POOL_CONNECTIONS", 50))

        return boto3.client(
            "s3",
            endpoint_url=getattr(base_configs, "S3_URL"),
            aws_access_key_id=getattr(base_configs, "S3_ACCESS_KEY"),
            aws_secret_access_key=getattr(base_configs, "S3_SECRET_KEY"),
            region_name=getattr(base_configs, "S3_REGION", "us-east-1"),
            use_ssl=use_ssl,
            config=Config(
                s3={"addressing_style": "path"},
                max_pool_connections=max_pool_connections,
                signature_version="s3v4",
            ),
        )

    def _build_public_object_url(self, bucket_name: str, object_key: str) -> str:
        s3_url = str(getattr(base_configs, "S3_URL")).rstrip("/")
        return f"{s3_url}/{bucket_name}/{object_key}"

    def _extract_object_key_from_url(self, image_url: str, bucket_name: str) -> str | None:
        s3_url = str(getattr(base_configs, "S3_URL")).rstrip("/")
        prefix = f"{s3_url}/{bucket_name}/"
        if image_url.startswith(prefix):
            return image_url[len(prefix):]
        return None

    def _parse_tag_ids_json(self, tag_ids_json: str | None) -> list[int]:
        """解析标签 ID 字符串。

        支持三种形式：
        1. None / "" -> []
        2. "[1,2,3]" -> [1,2,3]
        3. "1,2,3" -> [1,2,3]
        """
        if tag_ids_json is None:
            return []

        raw_value = str(tag_ids_json).strip()
        if raw_value == "":
            return []

        if raw_value.startswith("[") and raw_value.endswith("]"):
            raw_data = json.loads(raw_value)
            if not isinstance(raw_data, list):
                raise ValueError("tag_ids_json 必须是 JSON 数组字符串")
            return [int(item) for item in raw_data]

        parts = [part.strip() for part in raw_value.split(",") if part.strip() != ""]
        if not parts:
            return []

        return [int(part) for part in parts]

    def _normalize_upload_files(
        self,
        images: list[UploadFile] | None,
    ) -> list[UploadFile]:
        """过滤 Swagger 可能传进来的空占位文件。"""
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

    async def _get_question_tags(
        self,
        session: AsyncSession,
        question_id: int,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Tag.id, Tag.tag_name)
            .select_from(QuestionTagRel)
            .join(Tag, Tag.id == QuestionTagRel.tag_id)
            .where(QuestionTagRel.question_id == question_id)
            .order_by(Tag.id.asc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [{"tag_id": row.id, "tag_name": row.tag_name} for row in rows]

    async def _get_question_images(
        self,
        session: AsyncSession,
        question_id: int,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(QuestionImage)
            .where(QuestionImage.question_id == question_id)
            .order_by(QuestionImage.sort_no.asc(), QuestionImage.id.asc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "image_id": row.id,
                "image_url": row.image_url,
                "sort_no": row.sort_no,
            }
            for row in rows
        ]

    async def _build_question_detail_dict(
        self,
        session: AsyncSession,
        question_obj: Question,
    ) -> dict[str, Any]:
        tags = await self._get_question_tags(session, int(question_obj.id))
        images = await self._get_question_images(session, int(question_obj.id))

        return {
            "question_id": question_obj.id,
            "content_md": question_obj.content_md,
            "reference_answer": question_obj.reference_answer,
            "question_type": question_obj.question_type.value
            if hasattr(question_obj.question_type, "value")
            else str(question_obj.question_type),
            "status": question_obj.status.value
            if hasattr(question_obj.status, "value")
            else str(question_obj.status),
            "tags": tags,
            "images": images,
            "created_at": question_obj.created_at,
            "updated_at": question_obj.updated_at,
        }

    async def _validate_tag_ids(
        self,
        session: AsyncSession,
        tag_ids: list[int],
    ) -> tuple[bool, str]:
        if not tag_ids:
            return True, ""

        stmt = select(Tag.id).where(Tag.id.in_(tag_ids))
        result = await session.execute(stmt)
        existing_ids = {int(tag_id) for tag_id in result.scalars().all()}

        not_found_ids = [tag_id for tag_id in tag_ids if tag_id not in existing_ids]
        if not_found_ids:
            return False, f"标签不存在: {not_found_ids}"
        return True, ""

    async def _upload_question_image(
        self,
        question_id: int,
        sort_no: int,
        upload_file: UploadFile,
    ) -> str:
        bucket_name = self._get_question_bucket_name()
        s3_client = self._build_s3_client()

        file_bytes = await upload_file.read()
        if not file_bytes:
            raise ValueError("上传图片为空")

        original_filename = upload_file.filename or ""
        _, extension = os.path.splitext(original_filename)
        extension = extension.lower() or ".bin"

        object_key = (
            f"teacher/question/{question_id}/"
            f"{uuid.uuid4().hex}_{sort_no}{extension}"
        )

        extra_args: dict[str, Any] = {}
        if upload_file.content_type:
            extra_args["ContentType"] = upload_file.content_type

        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=file_bytes,
            **extra_args,
        )
        return self._build_public_object_url(bucket_name, object_key)

    def _delete_question_image_object(self, image_url: str) -> None:
        bucket_name = self._get_question_bucket_name()
        object_key = self._extract_object_key_from_url(image_url, bucket_name)
        if not object_key:
            return

        s3_client = self._build_s3_client()
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)

    async def get_question_count(
        self,
        teacher_id: int | str,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            total_count = await session.scalar(
                select(func.count(Question.id)).where(Question.creator_id == int(teacher_id))
            )
            return (
                True,
                status.HTTP_200_OK,
                "获取题目总数成功",
                {"total_question_count": int(total_count or 0)},
            )

    async def create_tag(
        self,
        teacher_id: int | str,
        tag_name: str,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Tag).where(Tag.tag_name == tag_name)
                result = await session.execute(stmt)
                exist_tag = result.scalar_one_or_none()

                if exist_tag:
                    return (
                        False,
                        status.HTTP_400_BAD_REQUEST,
                        "标签名称已存在",
                        None,
                    )

                new_tag = Tag(
                    tag_name=tag_name,
                    created_by=int(teacher_id),
                )
                session.add(new_tag)
                await session.commit()
                await session.refresh(new_tag)

                return (
                    True,
                    status.HTTP_200_OK,
                    "新增标签成功",
                    {
                        "tag_id": new_tag.id,
                        "tag_name": new_tag.tag_name,
                    },
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "新增标签失败，请稍后重试" + str(e),
                    None,
                )

    async def delete_tag(
        self,
        teacher_id: int | str,
        tag_id: int,
    ) -> tuple[bool, int, str, None]:
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Tag).where(Tag.id == tag_id)
                result = await session.execute(stmt)
                tag_obj = result.scalar_one_or_none()

                if not tag_obj:
                    return (
                        False,
                        status.HTTP_404_NOT_FOUND,
                        "标签不存在",
                        None,
                    )

                await session.execute(
                    delete(QuestionTagRel).where(QuestionTagRel.tag_id == tag_id)
                )
                await session.delete(tag_obj)
                await session.commit()

                return True, status.HTTP_200_OK, "删除标签成功", None
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "删除标签失败，请稍后重试" + str(e),
                    None,
                )

    async def list_tags(
        self,
        teacher_id: int | str,
    ) -> tuple[bool, int, str, list[dict] | None]:
        async with AsyncSessionLocal() as session:
            stmt = select(Tag).order_by(Tag.id.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()

            data = [
                {
                    "tag_id": row.id,
                    "tag_name": row.tag_name,
                }
                for row in rows
            ]
            return True, status.HTTP_200_OK, "获取标签列表成功", data

    async def create_question(
        self,
        teacher_id: int | str,
        content_md: str | None,
        reference_answer: str | None,
        question_type: str,
        tag_ids_json: str | None,
        images: list[UploadFile] | None,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                question_type_enum = QuestionType(question_type)
                tag_ids = self._parse_tag_ids_json(tag_ids_json)
                normalized_images = self._normalize_upload_files(images)

                ok, error_message = await self._validate_tag_ids(session, tag_ids)
                if not ok:
                    return False, status.HTTP_400_BAD_REQUEST, error_message, None

                new_question = Question(
                    creator_id=int(teacher_id),
                    content_md=content_md,
                    reference_answer=reference_answer,
                    question_type=question_type_enum,
                    status=QuestionStatus.active,
                )
                session.add(new_question)
                await session.flush()

                for tag_id in tag_ids:
                    session.add(
                        QuestionTagRel(
                            id=int(generate_id()),
                            question_id=int(new_question.id),
                            tag_id=tag_id,
                        )
                    )

                for index, image in enumerate(normalized_images, start=1):
                    image_url = await self._upload_question_image(
                        question_id=int(new_question.id),
                        sort_no=index,
                        upload_file=image,
                    )
                    session.add(
                        QuestionImage(
                            id=int(generate_id()),
                            question_id=int(new_question.id),
                            image_url=image_url,
                            sort_no=index,
                        )
                    )

                await session.commit()
                await session.refresh(new_question)

                data = await self._build_question_detail_dict(session, new_question)
                return True, status.HTTP_200_OK, "新增题目成功", data

            except ValueError as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    str(e),
                    None,
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "新增题目失败，请稍后重试" + str(e),
                    None,
                )

    async def update_question(
        self,
        teacher_id: int | str,
        question_id: int,
        content_md: str | None,
        reference_answer: str | None,
        question_type: str | None,
        tag_ids_json: str | None,
        replace_images: bool,
        images: list[UploadFile] | None,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Question).where(
                    and_(
                        Question.id == question_id,
                        Question.creator_id == int(teacher_id),
                    )
                )
                result = await session.execute(stmt)
                question_obj = result.scalar_one_or_none()

                if not question_obj:
                    return (
                        False,
                        status.HTTP_404_NOT_FOUND,
                        "题目不存在",
                        None,
                    )

                if content_md is not None:
                    question_obj.content_md = content_md

                if reference_answer is not None:
                    question_obj.reference_answer = reference_answer

                if question_type is not None:
                    question_obj.question_type = QuestionType(question_type)

                if tag_ids_json is not None:
                    tag_ids = self._parse_tag_ids_json(tag_ids_json)
                    ok, error_message = await self._validate_tag_ids(session, tag_ids)
                    if not ok:
                        return False, status.HTTP_400_BAD_REQUEST, error_message, None

                    await session.execute(
                        delete(QuestionTagRel).where(
                            QuestionTagRel.question_id == question_id
                        )
                    )
                    for tag_id in tag_ids:
                        session.add(
                            QuestionTagRel(
                                id=int(generate_id()),
                                question_id=question_id,
                                tag_id=tag_id,
                            )
                        )

                normalized_images = self._normalize_upload_files(images)

                if replace_images:
                    image_stmt = select(QuestionImage).where(
                        QuestionImage.question_id == question_id
                    )
                    image_result = await session.execute(image_stmt)
                    old_images = image_result.scalars().all()

                    for old_image in old_images:
                        self._delete_question_image_object(old_image.image_url)
                        await session.delete(old_image)

                if normalized_images:
                    start_sort_no = 1
                    if not replace_images:
                        max_sort_no = await session.scalar(
                            select(func.max(QuestionImage.sort_no)).where(
                                QuestionImage.question_id == question_id
                            )
                        )
                        start_sort_no = int(max_sort_no or 0) + 1

                    for offset, image in enumerate(normalized_images, start=0):
                        sort_no = start_sort_no + offset
                        image_url = await self._upload_question_image(
                            question_id=question_id,
                            sort_no=sort_no,
                            upload_file=image,
                        )
                        session.add(
                            QuestionImage(
                                id=int(generate_id()),
                                question_id=question_id,
                                image_url=image_url,
                                sort_no=sort_no,
                            )
                        )

                await session.commit()
                await session.refresh(question_obj)

                data = await self._build_question_detail_dict(session, question_obj)
                return True, status.HTTP_200_OK, "编辑题目成功", data

            except ValueError as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_400_BAD_REQUEST,
                    str(e),
                    None,
                )
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "编辑题目失败，请稍后重试" + str(e),
                    None,
                )

    async def delete_question(
        self,
        teacher_id: int | str,
        question_id: int,
    ) -> tuple[bool, int, str, None]:
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Question).where(
                    and_(
                        Question.id == question_id,
                        Question.creator_id == int(teacher_id),
                    )
                )
                result = await session.execute(stmt)
                question_obj = result.scalar_one_or_none()

                if not question_obj:
                    return False, status.HTTP_404_NOT_FOUND, "题目不存在", None

                image_stmt = select(QuestionImage).where(QuestionImage.question_id == question_id)
                image_result = await session.execute(image_stmt)
                image_rows = image_result.scalars().all()

                for image_row in image_rows:
                    self._delete_question_image_object(image_row.image_url)
                    await session.delete(image_row)

                await session.execute(
                    delete(QuestionTagRel).where(QuestionTagRel.question_id == question_id)
                )

                question_obj.status = QuestionStatus.disabled
                await session.commit()

                return True, status.HTTP_200_OK, "删除题目成功", None
            except Exception as e:
                await session.rollback()
                return (
                    False,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "删除题目失败，请稍后重试" + str(e),
                    None,
                )

    async def get_question_detail(
        self,
        teacher_id: int | str,
        question_id: int,
    ) -> tuple[bool, int, str, dict | None]:
        async with AsyncSessionLocal() as session:
            stmt = select(Question).where(
                and_(
                    Question.id == question_id,
                    Question.creator_id == int(teacher_id),
                )
            )
            result = await session.execute(stmt)
            question_obj = result.scalar_one_or_none()

            if not question_obj:
                return False, status.HTTP_404_NOT_FOUND, "题目不存在", None

            data = await self._build_question_detail_dict(session, question_obj)
            return True, status.HTTP_200_OK, "获取题目详情成功", data

    async def search_questions(
        self,
        teacher_id: int | str,
        keyword: str | None = None,
        tag_ids: list[int] | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[bool, int, str, dict | None]:
        """搜索题目。"""
        async with AsyncSessionLocal() as session:
            try:
                question_status = status

                base_stmt = select(distinct(Question.id)).where(
                    Question.creator_id == int(teacher_id)
                )

                if keyword:
                    base_stmt = base_stmt.where(
                        Question.content_md.ilike(f"%{keyword}%")
                    )

                if question_status:
                    try:
                        status_enum = QuestionStatus(question_status)
                    except ValueError:
                        return (
                            False,
                            400,
                            "题目状态不合法，仅支持 draft / active / disabled",
                            None,
                        )
                    base_stmt = base_stmt.where(Question.status == status_enum)

                if tag_ids:
                    base_stmt = (
                        base_stmt.join(
                            QuestionTagRel,
                            QuestionTagRel.question_id == Question.id,
                        )
                        .where(QuestionTagRel.tag_id.in_(tag_ids))
                    )

                total_stmt = select(func.count()).select_from(base_stmt.subquery())
                total = await session.scalar(total_stmt)

                page = max(page, 1)
                page_size = max(page_size, 1)
                offset_value = (page - 1) * page_size

                paged_id_stmt = (
                    base_stmt.order_by(Question.id.desc())
                    .offset(offset_value)
                    .limit(page_size)
                )
                id_result = await session.execute(paged_id_stmt)
                question_ids = [int(row[0]) for row in id_result.all()]

                items: list[dict[str, Any]] = []
                if question_ids:
                    question_stmt = (
                        select(Question)
                        .where(Question.id.in_(question_ids))
                        .order_by(Question.id.desc())
                    )
                    question_result = await session.execute(question_stmt)
                    question_rows = question_result.scalars().all()

                    for question_obj in question_rows:
                        items.append(
                            await self._build_question_detail_dict(session, question_obj)
                        )

                data = {
                    "total": int(total or 0),
                    "page": page,
                    "page_size": page_size,
                    "items": items,
                }
                return True, 200, "搜索题目成功", data

            except Exception as e:
                return (
                    False,
                    500,
                    "搜索题目失败，请稍后重试" + str(e),
                    None,
                )


TEA_question_service = TEAQuestionService()