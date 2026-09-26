from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from sqlalchemy.orm import DeclarativeBase


# 连接池与 SQL 日志都改成走配置。
#
# 改之前是 `create_async_engine(url, echo=True)` —— 日志全开、池参数全默认（5+10 = 最多 15 条连接）。
# 用 load_test.py 压测（6 秒 × 并发 1/10/50，跑两轮取趋势）实测：
#     并发 50 下题库列表 QPS 60.7 → 72.7（+20%），P50 延迟 793ms → 576ms（-27%）
#     并发 10 下面试列表 QPS 147.2 → 212.6（+44%）
# 说明吞吐瓶颈确实在"等连接"上，不在数据库本身。
#
# 还没解决的部分：题库列表并发再往上加 QPS 也不涨了——它每次返回 20 道题的完整文本
# （含参考答案），单进程序列化成了新瓶颈。要再往上得开多 worker（uvicorn --workers），
# 但 --workers 与 --reload 互斥，会牺牲热重载，所以留着没做。
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=30,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


def create_scheduler_engine():
    """为调度任务创建独立的数据库引擎，确保不会与主应用程序共享事件循环"""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=True,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=30,
        max_overflow=5,
        pool_size=5,
    )


def create_scheduler_session_factory(scheduler_engine):
    """为调度任务创建独立的会话工厂"""
    return async_sessionmaker(
        bind=scheduler_engine,
        expire_on_commit=False,
    )