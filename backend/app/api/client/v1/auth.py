from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.schemas.client.auth import UserRegister, UserLogin, AuthToken, UserInfo
from app.schemas.response import ApiResponse
from app.models.user import User
from app.core.security import hash_password, create_access_token, verify_password

router = APIRouter()

@router.post("/register")
async def register(
        user_data: UserRegister,
        db: AsyncSession = Depends(get_db),
):
    # 查重：邮箱已注册就拒绝
    exists = await db.scalar(select(User).where(User.email == user_data.email))
    if exists:
        return ApiResponse.failed(message="邮箱已被注册", body_code=1003, http_code=409)

    # 建用户，密码必须哈希
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
    )
    # 落库
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # 注册即登录：签发 token 返回
    token = create_access_token(user.id)
    return ApiResponse.success(
        data=AuthToken(
            access_token=token,
            user=UserInfo(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )
        )
    )


@router.post("/login")
async def login(
        login_data: UserLogin,
        db: AsyncSession = Depends(get_db),
):
    # 1.查用户
    user = await db.scalar(select(User).where(User.email == login_data.email))

    # 2. 统一验证：人不在 或 密码错，同一个提示（防枚举）
    if not user or not verify_password(login_data.password, user.hashed_password):
        return ApiResponse.failed(message="邮箱或密码错误", body_code=1002, http_code=401)

    # 3. 签发 token
    token = create_access_token(user.id)
    return ApiResponse.success(data=AuthToken(
        access_token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
    )))





















