"""
健康检查路由：给 Docker healthcheck 和部署后自检用。

只留 /health 一个端点 —— 没做独立的版本发布配置（那需要一整套 RELEASE_CONFIG
和配套模块），当前规模用不上。
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import get_db
from app.schemas.response import ApiResponse
from app.services.common.redis import redis_client

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    健康检查端点：检查应用、数据库、Redis 三路是否都通
    （Docker 的 healthcheck 就打在它身上）
    """
    health_status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "database": "unknown",
            "redis": "unknown",
        },
    }

    # 检查数据库连接
    try:
        async for db in get_db():
            result = await db.execute(text("SELECT 1"))
            if result.scalar() == 1:
                health_status["services"]["database"] = "up"
            break
    except Exception:
        health_status["services"]["database"] = "down"
        health_status["status"] = "unhealthy"

    # 检查 Redis 连接
    try:
        await redis_client.redis.ping()
        health_status["services"]["redis"] = "up"
    except Exception:
        health_status["services"]["redis"] = "down"
        health_status["status"] = "unhealthy"

    if health_status["status"] == "unhealthy":
        return ApiResponse.failed(
            message="Service unhealthy",
            body_code=503,
            http_code=503,
            data=health_status,
        )

    return ApiResponse.success(data=health_status)
