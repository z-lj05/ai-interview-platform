"""
题库管理 API（管理端）
"""
import logging
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal

from app.db.session import get_db
from app.api.backoffice.deps import get_current_admin
from app.models.admin import Admin
from app.schemas.response import ApiResponse
from app.schemas.backoffice.question_bank import (
    QuestionBankCreate,
    QuestionBankUpdate,
    QuestionBankToggle,
    QuestionBankBatchImport,
    QuestionBankResponse,
    QuestionBankTestRetrieve,
)
from app.services.backoffice.question_bank_service import QuestionBankService
from app.services.common.question_parser import build_items, parse_question_file, summarize_parse

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(q) -> dict:
    """ORM 对象 → 响应字典（含 has_embedding 标志）"""
    return {
        "id": q.id,
        "category": q.category,
        "position_tag": q.position_tag,
        "difficulty": q.difficulty,
        "question": q.question,
        "reference_answer": q.reference_answer,
        "key_points": q.key_points,
        "tags": q.tags,
        "source": q.source,
        "use_count": q.use_count,
        "is_active": q.is_active,
        "has_embedding": q.embedding is not None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
    }


# ── 1. 列表 ────────────────────────────────────────────────────────────

@router.get("")
async def list_questions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    position_tag: Optional[str] = Query(None),
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="题面/参考答案关键字"),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """题库列表（分页 + 筛选）"""
    result = await QuestionBankService.get_list(
        db=db, page=page, size=per_page,
        category=category, position_tag=position_tag,
        difficulty=difficulty, is_active=is_active, search=search,
    )
    return ApiResponse.success({
        "items": [_to_response(q) for q in result["items"]],
        "total": result["total"],
        "page": page,
        "per_page": per_page,
    })


# ── 2. 创建 ────────────────────────────────────────────────────────────

@router.post("")
async def create_question(
    payload: QuestionBankCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """新增题目（保存后自动向量化）"""
    data = payload.model_dump()
    data["created_by"] = current_admin.id
    q = await QuestionBankService.create(db, data)
    return ApiResponse.success(_to_response(q), message="创建成功")


# ── 3. 详情 ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_question_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """题库统计（总数、按分类/难度分布、热门题）"""
    stats = await QuestionBankService.get_stats(db)
    return ApiResponse.success(stats)


@router.get("/{question_id}")
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    q = await QuestionBankService.get_by_id(db, question_id)
    if not q:
        return ApiResponse.failed("题目不存在", body_code=404, http_code=404)
    return ApiResponse.success(_to_response(q))


# ── 4. 更新 ────────────────────────────────────────────────────────────

@router.put("/{question_id}")
async def update_question(
    question_id: int,
    payload: QuestionBankUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """更新题目（若改了 question/reference_answer 则自动重新向量化）"""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return ApiResponse.failed("没有任何更新字段", body_code=400)
    q = await QuestionBankService.update(db, question_id, data)
    if not q:
        return ApiResponse.failed("题目不存在", body_code=404, http_code=404)
    return ApiResponse.success(_to_response(q), message="更新成功")


# ── 5. 删除 ────────────────────────────────────────────────────────────

@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    ok = await QuestionBankService.delete(db, question_id)
    if not ok:
        return ApiResponse.failed("题目不存在", body_code=404, http_code=404)
    return ApiResponse.success(message="删除成功")


# ── 6. 启用/禁用 ───────────────────────────────────────────────────────

@router.patch("/{question_id}/toggle")
async def toggle_question(
    question_id: int,
    payload: QuestionBankToggle,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    ok = await QuestionBankService.toggle(db, question_id, payload.is_active)
    if not ok:
        return ApiResponse.failed("题目不存在", body_code=404, http_code=404)
    return ApiResponse.success(message="状态已更新")


# ── 7. 批量导入 ────────────────────────────────────────────────────────

@router.post("/batch-import")
async def batch_import_questions(
    payload: QuestionBankBatchImport,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    批量导入题目。先全部入库（embedding=NULL），再后台异步向量化。

    两条导入入口共用这一个落库口：管理端粘贴 JSON / 上传文件解析后回填的 items。
    """
    inserted_ids = await QuestionBankService.batch_import(db, payload.items, current_admin.id)

    # 后台批量向量化（走 Celery，避免阻塞请求）
    from app.schedule.jobs.knowledge_tasks import batch_embed_questions_task
    batch_embed_questions_task.delay(inserted_ids)

    return ApiResponse.success(
        {"inserted_count": len(inserted_ids), "ids": inserted_ids},
        message=f"已导入 {len(inserted_ids)} 题，向量化任务已提交",
    )


# ── 7b. 文件解析预览（PDF / MD → 题目列表，不落库）──────────────────────

@router.post("/parse-file")
async def parse_import_file(
    file: UploadFile = File(...),
    category: str = Form("technical"),
    position_tag: str = Form("python_backend"),
    difficulty: str = Form("medium"),
    source: str = Form("file-import"),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    上传 PDF / MD / TXT，切题后返回预览——**不落库**，一题都不写。

    为什么拆成"解析"和"导入"两步：切题规则是照语料长相定的，换个排版的 PDF
    就可能切错（09-13 切知识库时误杀过 3 道真题）。先在页面上看见切出多少题、
    长什么样，确认无误再点导入——这是唯一能拦住"切错了却已经进库"的防线。

    解析是同步阻塞的（pdfplumber 没有异步版），必须丢线程池：
    直接 await 一个几十页的 PDF，会把整个事件循环堵住，所有人的请求一起等。
    """
    file_name = file.filename or "untitled"
    file_bytes = await file.read()
    if not file_bytes:
        return ApiResponse.failed("文件是空的", body_code=400)

    try:
        result = await run_in_threadpool(parse_question_file, file_name, file_bytes)
    except ValueError as e:                       # 不支持的扩展名
        return ApiResponse.failed(str(e), body_code=400)
    except Exception as e:                        # PDF 损坏/加密等
        logger.exception(f"解析文件失败: {file_name}")
        return ApiResponse.failed(f"文件解析失败：{e}", body_code=400)

    items = build_items(
        result["parsed"],
        category=category,
        position_tag=position_tag,
        difficulty=difficulty,
        source=source,
    )
    stats = summarize_parse(result["parsed"])

    # 唯一的硬预警：数量超上限（这是事实，不是猜测）
    warn = None
    if len(items) > 500:
        warn = f"切出 {len(items)} 题，超过单次 500 题的上限——请拆成多个文件导入"

    return ApiResponse.success({
        "file_name": file_name,
        "strategy": result["strategy"],           # 实际用了哪套切题规则（txt 是量出来的）
        "count": len(items),
        "items": items,                           # 回填给前端，确认后原样打给 /batch-import
        # 首尾都取样例：切错经常塌在尾部（"最后一道题把后记/附录全吃了"）
        "preview": {
            "head": [i["question"] for i in items[:5]],
            "tail": items[-1]["question"] if items else None,
        },
        "stats": stats,
        "warn": warn,
    })


# ── 8. 全量重建 ────────────────────────────────────────────────────────

@router.post("/reindex-all")
async def reindex_all_questions(
    current_admin: Admin = Depends(get_current_admin),
):
    """异步全量重建题库 embedding（升级模型时用）"""
    from app.schedule.jobs.knowledge_tasks import reindex_all_questions_task
    task = reindex_all_questions_task.delay()
    return ApiResponse.success(
        {"task_id": task.id},
        message="全量重建任务已提交，请稍后查看",
    )


# ── 9. 检索测试 ────────────────────────────────────────────────────────

@router.post("/test-retrieve")
async def test_retrieve_questions(
    payload: QuestionBankTestRetrieve,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """测试题库召回效果（输入岗位/技能，看返回的 Top N 题）"""
    items = await QuestionBankService.retrieve_questions(
        query=payload.query,
        db=db,
        k=payload.k,
        position_tag=payload.position_tag,
        difficulty=payload.difficulty,
        min_score=payload.min_score,
    )
    return ApiResponse.success({
        "query": payload.query,
        "count": len(items),
        "items": items,
    })
