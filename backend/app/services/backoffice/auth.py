from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import Admin
from app.core.security import create_access_token, verify_password
from app.exceptions.http_exceptions import AuthenticationError

class BackofficeAuthService:

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> dict:

        admin_user = await db.scalar(select(Admin).where(Admin.email == email))

        if not admin_user or not verify_password(password, admin_user.hashed_password):
            raise AuthenticationError(message="邮箱或密码错误")

        if admin_user.is_active is False:
            raise AuthenticationError("管理员账号已停用")

        access_token = create_access_token(str(admin_user.id), scope="backoffice")
        return {"access_token": access_token, "token_type": "bearer"}
