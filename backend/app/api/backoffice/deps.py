from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import decode_token
from app.exceptions.http_exceptions import AuthenticationError
from app.models.admin import Admin

async def get_current_admin(
        authorization: str = Header(...),
        db: AsyncSession = Depends(get_db),
) -> Admin:
    # 1. 抠卡：去掉 "Bearer "前缀
    token = authorization.split(" ")[1]
    # 2. 验卡：decode_token
    payload = decode_token(token)

    if not payload:
        raise AuthenticationError(message="登录已过期，请重新登录")
    if payload.get("scope") != "backoffice":
        raise AuthenticationError(message="无权限")

    admin_user_id = int(payload["sub"])
    admin_user = await db.scalar(select(Admin).where(Admin.id == admin_user_id))
    if not admin_user:
        raise AuthenticationError("用户不存在")
    if admin_user.is_active is False:
        raise AuthenticationError("管理员账号已停用")
    return admin_user
