from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import decode_token
from app.exceptions.http_exceptions import AuthenticationError
from app.models.user import User


async def get_current_user(
        authorization: str = Header(...),
        db: AsyncSession = Depends(get_db),
) -> User:
    # 抠 token：去掉 "Bearer " 前缀（按空格切开取第二段）
    token = authorization.split(" ")[1]

    # 验卡：解码 + 验签 + 查过期
    payload = decode_token(token)
    if not payload:
        raise AuthenticationError(message="登录已过期，请重新登录")

    # 取持卡人身份 → 查库
    user_id = int(payload["sub"])
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AuthenticationError(message="用户不存在")
    if not user.is_active:
        raise AuthenticationError(message="账号已被禁用，请联系管理员")
    return user





