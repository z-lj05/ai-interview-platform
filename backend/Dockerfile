# 生产镜像：Python 3.12-slim + gcc / libpq-dev（asyncpg 构建依赖）
# 用法：docker compose -f docker-compose.yml -f docker-compose.prod.yml build
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 换 Debian 源为阿里云（国内构建加速）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 系统依赖：gcc/g++（个别包要编译）、libpq-dev（asyncpg）、curl（健康检查调试）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    pkg-config \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖再拷代码：requirements.txt 不变时，pip 层可命中镜像缓存（改代码不用重装包）
COPY requirements.txt .
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs uploads/resumes \
    && useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["python", "main.py"]
