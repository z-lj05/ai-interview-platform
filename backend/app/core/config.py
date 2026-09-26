from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_PORT: int = 8000
    # 默认值里不带口令：连接串一律从 .env 读，免得本地库口令被带进版本库
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/interview_db"
    # ── 数据库连接池与 SQL 日志（压测定位出来的两个吞吐瓶颈）────────────────
    # echo=True 把每条 SQL 都打到控制台，压测时是实打实的 I/O 开销；本地想看 SQL 就在 .env 打开
    SQL_ECHO: bool = False
    # SQLAlchemy 默认 pool_size=5 + max_overflow=10 = 最多 15 条连接。
    # 并发上到 50 时大量请求在排队等连接 → QPS 卡住不涨、P99 延迟翻数倍。
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800        # 30 分钟回收一次，防被 PG 侧空闲超时掐掉连接
    ALGORITHM: str = "HS256"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_V1_STR: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"
    # 密钥一律走 .env，代码里不写默认值（写了真 key 还有个副作用：
    # .env 忘了配也不会报错，会静默用代码里的值，线上换 key 时特别坑）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DASHSCOPE_API_KEY: str = "sk-your-dashscope-key"
    KNOWLEDGE_EMBEDDING_MODEL: str = "text-embedding-v3"
    KNOWLEDGE_EMBEDDING_DIM: int = 1024
    QUESTION_BANK_MIN_SCORE: float = 0.7      # 题库召回相似度阈值，低于该值不算相关
    QUESTION_BANK_RECALL_FACTOR: int = 2      # 召回倍数：目标 N 题先捞 N×2 回来供 AI 挑选
    QUESTION_BANK_TOP_K: int = 20             # 单次检索返回上限
    # 邮件配置
    MAIL_MAILER: str = "smtp"
    MAIL_HOST: str = "localhost"
    MAIL_PORT: int = 1025
    MAIL_USERNAME: str = "user"
    MAIL_PASSWORD: str = "password"
    MAIL_FROM_ADDRESS: str = "noreply@example.com"
    MAIL_FROM_NAME: str = "AI 模拟面试平台"
    MAIL_ENCRYPTION: str = "none"
    ADMIN_EMAIL: str = "admin@example.com"
    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    # Celery 配置
    CELERY_BROKER_URL: str = ""  # 在 __init__ 中设置
    CELERY_RESULT_BACKEND: str = ""  # 在 __init__ 中设置
    class Config:
        env_file = '.env'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 从 Redis 配置推导 Celery 的 broker/backend 地址
        if self.REDIS_PASSWORD:
            redis_url = (
                f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
            )
        else:
            redis_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        self.CELERY_BROKER_URL = redis_url
        self.CELERY_RESULT_BACKEND = redis_url

settings = Settings()