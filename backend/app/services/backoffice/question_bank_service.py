import logging
from sqlalchemy import select, delete, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_bank import QuestionBank
from app.services.common.embedding import embed_text, embed_texts

logger = logging.getLogger(__name__)


def _build_embedding_text(question: str, reference_answer: str | None) -> str:
    """构造用于向量化的文本：题面 + 参考答案"""
    parts = [question.strip()]
    if reference_answer and reference_answer.strip():
        parts.append(f"参考答案：{reference_answer.strip()}")
    return "\n\n".join(parts)


class QuestionBankService:

    # ── CRUD ────────────────────────────────────────────────────────────

    @staticmethod
    async def create(db: AsyncSession, data: dict) -> QuestionBank:
        """新增题目，保存后自动向量化"""
        emb_text = _build_embedding_text(data["question"], data.get("reference_answer"))
        try:
            embedding = await embed_text(emb_text)
        except Exception as e:
            logger.warning(f"题目向量化失败（降级为 NULL，补配 Embedding key 后重建即可生效）: {e}")
            embedding = None

        q = QuestionBank(
            category=data["category"],
            position_tag=data["position_tag"],
            difficulty=data["difficulty"],
            question=data["question"],
            reference_answer=data.get("reference_answer"),
            key_points=data.get("key_points"),
            tags=data.get("tags"),
            source=data.get("source", "manual"),
            created_by=data.get("created_by"),
            embedding=embedding,
            embedding_text=emb_text,
        )
        db.add(q)
        await db.commit()
        await db.refresh(q)
        logger.info(f"题目 {q.id} 已创建")
        return q

    @staticmethod
    async def get_by_id(db: AsyncSession, question_id: int) -> QuestionBank | None:
        """按主键获取单道题目，不存在时返回 None。"""
        return await db.get(QuestionBank, question_id)

    @staticmethod
    async def update(db: AsyncSession, question_id: int, data: dict) -> QuestionBank | None:
        """更新题目，若修改了题面或答案则重新向量化"""
        q = await db.get(QuestionBank, question_id)
        if not q:
            return None

        need_reembed = False
        for field in ("question", "reference_answer"):
            if field in data and data[field] != getattr(q, field):
                need_reembed = True

        for field, val in data.items():
            if hasattr(q, field):
                setattr(q, field, val)

        if need_reembed:
            emb_text = _build_embedding_text(q.question, q.reference_answer)
            try:
                q.embedding = await embed_text(emb_text)
            except Exception as e:
                logger.warning(f"更新后向量化失败（降级为 NULL）: {e}")
                q.embedding = None
            q.embedding_text = emb_text

        await db.commit()
        await db.refresh(q)
        return q

    @staticmethod
    async def delete(db: AsyncSession, question_id: int) -> bool:
        """删除单道题目，返回是否删除成功。"""
        result = await db.execute(
            delete(QuestionBank).where(QuestionBank.id == question_id)
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def toggle(db: AsyncSession, question_id: int, is_active: bool) -> bool:
        """启用或禁用题目，返回是否更新成功。"""
        result = await db.execute(
            update(QuestionBank)
            .where(QuestionBank.id == question_id)
            .values(is_active=is_active)
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def batch_import(db: AsyncSession, items: list, admin_id: int) -> list[int]:
        """批量导入：先全部入库（embedding=NULL），返回新题 id 列表

        和 create() 的关键区别：这里**一句向量都不算**。几百道题逐个调 embedding
        会把请求拖到超时，所以走"落库 → 后台批量向量化"两段式——路由拿到 id 列表后
        丢一个 Celery 任务（batch_embed_questions_task），批量算、批量写回。

        代价是中间有个窗口期题目 embedding 为 NULL（检索不到）。这是取舍：
        导入接口要秒回，向量化本来就慢（84 题约 6 秒，几百题更久）。
        """
        inserted_ids: list[int] = []
        for item in items:
            q = QuestionBank(**item.model_dump(), created_by=admin_id)
            db.add(q)
            await db.flush()          # flush 而非 commit：先拿到自增 id，最后一次性提交
            inserted_ids.append(q.id)
        await db.commit()
        logger.info(f"批量导入 {len(inserted_ids)} 题（向量化待后台执行）")
        return inserted_ids

    @staticmethod
    async def get_list(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        category: str | None = None,
        position_tag: str | None = None,
        difficulty: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> dict:
        """按条件分页查询题库列表，供后台管理页展示和筛选。"""
        stmt = select(QuestionBank)
        if category:
            stmt = stmt.where(QuestionBank.category == category)
        if position_tag:
            stmt = stmt.where(QuestionBank.position_tag.contains(position_tag))
        if difficulty:
            stmt = stmt.where(QuestionBank.difficulty == difficulty)
        if is_active is not None:
            stmt = stmt.where(QuestionBank.is_active == is_active)
        if search:
            stmt = stmt.where(
                or_(
                    QuestionBank.question.ilike(f"%{search}%"),
                    QuestionBank.reference_answer.ilike(f"%{search}%"),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(QuestionBank.created_at.desc()).offset((page - 1) * size).limit(size)
        items = (await db.execute(stmt)).scalars().all()
        return {"items": items, "total": total, "page": page, "size": size}

    # ── 向量化 ──────────────────────────────────────────────────────────

    @staticmethod
    async def embed_question(db: AsyncSession, question_id: int) -> bool:
        """单题重新向量化"""
        q = await db.get(QuestionBank, question_id)
        if not q:
            return False
        emb_text = _build_embedding_text(q.question, q.reference_answer)
        q.embedding = await embed_text(emb_text)
        q.embedding_text = emb_text
        await db.commit()
        return True

    @staticmethod
    def batch_embed_sync(question_ids: list[int]) -> dict:
        """
        同步批量向量化（供 Celery 任务调用）。
        因 Celery 无事件循环，这里直接操作数据库。

        注意：Celery worker 是长驻进程，每次 asyncio.run 都会开新的事件循环。
        必须用独立 engine 且用完 dispose，不能共用主 engine——否则第二次任务
        会复用上一个事件循环建出的连接，报
        AttributeError: 'NoneType' object has no attribute 'send'。
        """
        import asyncio
        from app.db.base import create_scheduler_engine, create_scheduler_session_factory

        scheduler_engine = create_scheduler_engine()
        SchedulerSessionLocal = create_scheduler_session_factory(scheduler_engine)

        async def _run():
            """在独立会话中批量生成 embedding 并回写数据库。"""
            try:
                async with SchedulerSessionLocal() as db:
                    stmt = select(QuestionBank).where(QuestionBank.id.in_(question_ids))
                    rows = (await db.execute(stmt)).scalars().all()

                    texts = [_build_embedding_text(q.question, q.reference_answer) for q in rows]
                    embeddings = await embed_texts(texts)  # async batch

                    for q, emb, txt in zip(rows, embeddings, texts):
                        q.embedding = emb
                        q.embedding_text = txt

                    await db.commit()
                    return len(rows)
            finally:
                await scheduler_engine.dispose()   # 清空连接池：防止下一个事件循环复用旧连接

        count = asyncio.run(_run())
        logger.info(f"批量向量化完成：{count} 题")
        return {"embedded": count}

    @staticmethod
    def reindex_all_sync() -> dict:
        """全量重建 embedding（升级模型时使用）——独立 engine，用完 dispose（同 batch_embed_sync 的跨循环防护）"""
        import asyncio
        from app.db.base import create_scheduler_engine, create_scheduler_session_factory

        scheduler_engine = create_scheduler_engine()
        SchedulerSessionLocal = create_scheduler_session_factory(scheduler_engine)

        async def _run():
            """遍历全量题目 ID，分批内联向量化（不能调 batch_embed_sync：它会再开事件循环）。"""
            try:
                async with SchedulerSessionLocal() as db:
                    stmt = select(QuestionBank)
                    rows = (await db.execute(stmt)).scalars().all()
                    ids = [q.id for q in rows]

                    # 分批处理：每批 50 题，在同一事件循环内批量向量化
                    total = 0
                    batch_size = 50
                    for i in range(0, len(ids), batch_size):
                        batch_ids = ids[i: i + batch_size]
                        stmt_batch = select(QuestionBank).where(QuestionBank.id.in_(batch_ids))
                        batch_rows = (await db.execute(stmt_batch)).scalars().all()

                        texts = [_build_embedding_text(q.question, q.reference_answer) for q in batch_rows]
                        embeddings = await embed_texts(texts)

                        for q, emb, txt in zip(batch_rows, embeddings, texts):
                            q.embedding = emb
                            q.embedding_text = txt

                        await db.commit()
                        total += len(batch_rows)
                return total
            finally:
                await scheduler_engine.dispose()

        total = asyncio.run(_run())
        return {"total_reindexed": total}

    # ── 统计 ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """题库统计：按分类、难度的分布 + 使用率排行"""
        by_category = (
            await db.execute(
                select(QuestionBank.category, func.count().label("cnt"))
                .group_by(QuestionBank.category)
            )
        ).all()

        by_difficulty = (
            await db.execute(
                select(QuestionBank.difficulty, func.count().label("cnt"))
                .group_by(QuestionBank.difficulty)
            )
        ).all()

        top_used = (
            await db.execute(
                select(QuestionBank.id, QuestionBank.question, QuestionBank.use_count)
                .order_by(QuestionBank.use_count.desc())
                .limit(10)
            )
        ).all()

        total = (await db.execute(select(func.count()).select_from(QuestionBank))).scalar_one()
        embedded = (
            await db.execute(
                select(func.count()).select_from(QuestionBank).where(QuestionBank.embedding.is_not(None))
            )
        ).scalar_one()

        return {
            "total": total,
            "embedded": embedded,
            "by_category": {row[0]: row[1] for row in by_category},
            "by_difficulty": {row[0]: row[1] for row in by_difficulty},
            "top_used": [{"id": r[0], "question": r[1][:50], "use_count": r[2]} for r in top_used],
        }

    # ── 检索 ─────────────────────────────────────────────────────────────

    @staticmethod
    async def retrieve_questions(
        query: str,
        db: AsyncSession,
        k: int = 20,
        position_tag: str | None = None,
        difficulty: str | None = None,
        min_score: float = 0.7,
    ) -> list[dict]:
        """
        题库语义检索，返回相似度 >= min_score 的题目。
        返回列表：[{id, category, position_tag, difficulty, question, reference_answer, key_points, similarity}, ...]
        """
        query_vec = await embed_text(query)
        distance_threshold = 1.0 - min_score

        stmt = (
            select(
                QuestionBank.id,
                QuestionBank.category,
                QuestionBank.position_tag,
                QuestionBank.difficulty,
                QuestionBank.question,
                QuestionBank.reference_answer,
                QuestionBank.key_points,
                QuestionBank.embedding.cosine_distance(query_vec).label("distance"),
            )
            .where(
                QuestionBank.is_active == True,
                QuestionBank.embedding.is_not(None),
                QuestionBank.embedding.cosine_distance(query_vec) <= distance_threshold,
            )
            .order_by(QuestionBank.embedding.cosine_distance(query_vec))
            .limit(k)
        )

        if position_tag:
            stmt = stmt.where(QuestionBank.position_tag.contains(position_tag))
        if difficulty:
            stmt = stmt.where(QuestionBank.difficulty == difficulty)

        result = await db.execute(stmt)
        rows = result.mappings().all()
        return [
            {
                "id": row["id"],
                "category": row["category"],
                "position_tag": row["position_tag"],
                "difficulty": row["difficulty"],
                "question": row["question"],
                "reference_answer": row["reference_answer"],
                "key_points": row["key_points"],
                "similarity": round(1.0 - float(row["distance"]), 4),
                "source": "from_bank",
            }
            for row in rows
        ]

    @staticmethod
    async def increment_use_count(db: AsyncSession, question_ids: list[int]) -> None:
        """面试选题后增加使用次数"""
        if not question_ids:
            return
        await db.execute(
            update(QuestionBank)
            .where(QuestionBank.id.in_(question_ids))
            .values(use_count=QuestionBank.use_count + 1)
        )
        await db.commit()
