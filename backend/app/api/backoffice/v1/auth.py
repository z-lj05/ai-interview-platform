from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.backoffice.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.schemas.response import ApiResponse
from app.schemas.backoffice.auth import Login
from app.services.backoffice.auth import BackofficeAuthService

router = APIRouter()

@router.post('/login')
async def login(
        login_data: Login,
        db: AsyncSession = Depends(get_db)
):
    result = await BackofficeAuthService.login(db, login_data.email, login_data.password)
    return ApiResponse.success(data=result)

@router.get("/me")
async def me(current_admin: Admin = Depends(get_current_admin)):
    return ApiResponse.success(
        data={
            "id": current_admin.id,
            "email": current_admin.email,
            "is_active": current_admin.is_active,
        }
    )

