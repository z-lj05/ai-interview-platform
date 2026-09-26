from fastapi import Depends, UploadFile, File, Form, APIRouter
from app.api.client.deps import get_current_user
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import ValidationError
from app.models.user import User
from app.schemas.response import ApiResponse
from app.models.resume import Resume
from app.services.client.resume_service import ResumeService

router = APIRouter()

@router.post("/upload")
async def upload_resume(
        file: UploadFile = File(...),
        target_position: str = Form(default="Python后端开发工程师"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise ValidationError(message="仅支持PDF格式")

    content = await file.read()
    if len(content) >= 10 * 1024 * 1024:
        raise ValidationError(message="文件大小过大")


    result = await ResumeService.upload_and_parse(
        db=db,
        user_id=current_user.id,
        file_content=content,
        file_name=file.filename,
        target_position=target_position,
    )
    return ApiResponse.success(data=result)


@router.get("/{resume_id}")
async def get_resume(
        resume_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """获取简历详情（含解析内容和分析报告）"""
    result = await ResumeService.get_resume(db, resume_id, current_user.id)
    return ApiResponse.success(data=result)



