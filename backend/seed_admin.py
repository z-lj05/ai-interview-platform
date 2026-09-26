import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.admin import Admin
from app.core.security import hash_password


async def seed():
    async with AsyncSessionLocal() as db:  # 开店（4a 学过）
        admin = Admin(
            email="a@new.com",  # 空1：管理员邮箱，你来定
            hashed_password=hash_password("123456"),  # 空2：密码要走哈希（刚讲的）
            first_name="Admin",
            is_active=True  # 空3：这行什么意思？注释写上
        )

        yhu = await db.scalar(select(Admin).where(Admin.email == "a@new.com"))
        if yhu:
            print("已存在")
        else:

            db.add(admin)  # 动作①
            await db.commit() # 动作②
            await db.refresh(admin)
            print(f"✅ 管理员创建成功 id={admin.id}")


asyncio.run(seed())



