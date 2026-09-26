from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_template import PositionTemplate
from sqlalchemy import select, or_, func, delete, update


class PositionTemplateService:

    @staticmethod
    async def get_list(db: AsyncSession, page=1, size=20, category=None, is_active=None, search=None) -> dict:
        stmt = select(PositionTemplate)
        if category:
            stmt = stmt.where(PositionTemplate.category == category)
        if is_active is not None:
            stmt = stmt.where(PositionTemplate.is_active == is_active)
        if search:
            stmt = stmt.where(or_(
                PositionTemplate.title.ilike(f"%{search}%"),
                PositionTemplate.position_tag.ilike(f"%{search}%"),
            ))

        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(PositionTemplate.sort_order, PositionTemplate.id).offset((page - 1) * size).limit(size)
        items = (await db.execute(stmt)).scalars().all()
        return {"items": items, "total": total, "page": page, "size": size}

    @staticmethod
    async def get_active_list(db: AsyncSession) -> list[PositionTemplate]:
        """供 Agent 工具使用：获取所有启用中的岗位模板"""
        result = await db.execute(
            select(PositionTemplate)
            .where(PositionTemplate.is_active == True)
            .order_by(PositionTemplate.sort_order.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_tag(db: AsyncSession, position_tag):
        result = await db.execute(select(PositionTemplate).where(PositionTemplate.position_tag == position_tag))
        return result.scalar_one_or_none()


    @staticmethod
    async def create(db: AsyncSession, data):
        existing = await PositionTemplateService.get_by_tag(db, data['position_tag'])
        if existing:
            raise ValueError(f"岗位标签 {data['position_tag']} 已存在")
        t = PositionTemplate(**data)
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t

    @staticmethod
    async def update(db: AsyncSession, template_id, data):
        """动态赋值：只改传进来的字段"""
        t = await db.get(PositionTemplate, template_id) # 按主键取
        if not t:
            return None
        for field, val in data.items():
            if hasattr(t, field): # 防御：字段不存在就跳过，不炸
                setattr(t, field, val) # 相当于 t.field = val，但字段名是变量

        await db.commit()
        await db.refresh(t)
        return t

    @staticmethod
    async def delete(db: AsyncSession, template_id):
        """语句式删除：直接对数据库说话，不取对象"""
        result = await db.execute(delete(PositionTemplate).where(PositionTemplate.id == template_id))
        await db.commit()
        return result.rowcount > 0 # rowcount = 受影响行数：1=真删到，0=不存在

    @staticmethod
    async def toggle(db: AsyncSession, template_id, is_active):
        """语句式更新：UPDATE ... SET is_active = ? WHERE id = ?"""
        result = await db.execute(update(PositionTemplate).where(PositionTemplate.id == template_id).values(is_active=is_active))
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_by_id(db: AsyncSession, template_id: int) -> PositionTemplate | None:
        """根据岗位模板主键查询单条记录。"""
        return await db.get(PositionTemplate, template_id)






