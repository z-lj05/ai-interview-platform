import io
import pdfplumber
import json
from sqlalchemy import select
from app.services.client.ai_service import AIService
from app.exceptions.http_exceptions import ValidationError, NotFoundError
from app.models.resume import Resume

class ResumeService:
    @staticmethod
    def _extract_pdf_text(file: bytes) -> str:
        text = ""
        with pdfplumber.open(io.BytesIO(file)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return text

    @staticmethod
    async def upload_and_parse(db, user_id, file_content, file_name, target_position) -> dict:
        resume = Resume(
            user_id=user_id,
            file_name=file_name,
            target_position=target_position,
            status="pending"
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)


        try:
            resume_text = ResumeService._extract_pdf_text(file_content)
            if not resume_text.strip():
                raise ValidationError(message="无法从PDF中提取文本内容")

        except Exception as e:
            resume.status = "failed"
            await db.commit()
            raise ValidationError(message=f"PDF解析失败：{str(e)}")


        try:
            parsed = await AIService.parse_resume(resume_text)
            resume.parsed_content = json.dumps(parsed, ensure_ascii=False)
            analysis = await AIService.analyze_resume(parsed, target_position)
            resume.analysis = json.dumps(analysis, ensure_ascii=False)

            resume.status = "completed"
            await db.commit()
            await db.refresh(resume)
        except Exception as e:
            resume.status = "failed"
            await db.commit()
            raise

        return {"resume_id": resume.id, "status": resume.status, "message": "简历上传并解析成功"}

    @staticmethod
    async def get_resume(db, resume_id: int, user_id: int) -> dict:
        """根据 ID 获取简历详情（含解析内容和分析报告）"""
        query = select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == user_id
        )
        result = await db.execute(query)
        resume = result.scalar_one_or_none()

        if not resume:
            raise NotFoundError(message="简历不存在")

        parsed_content = None
        if resume.parsed_content:
            try:
                parsed_content = json.loads(resume.parsed_content)
            except json.JSONDecodeError:
                parsed_content = None

        analysis = None
        if resume.analysis:
            try:
                analysis = json.loads(resume.analysis)
            except json.JSONDecodeError:
                analysis = None

        return {
            "resume_id": resume.id,
            "status": resume.status,
            "file_name": resume.file_name,
            "target_position": resume.target_position,
            "parsed_content": parsed_content,
            "analysis": analysis,
            "created_at": resume.created_at.isoformat() if resume.created_at else None
        }










