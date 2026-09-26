# AI 模拟面试与岗位匹配平台

面向求职者的 AI 模拟面试系统。上传简历后自动解析并匹配岗位，再按岗位考点从题库/知识库中检索出题，
逐题流式提问与评分，最后生成面试报告。

## 功能

**用户端**
- 简历上传与解析（PDF / Word），AI 岗位匹配打分
- RAG 检索出题：按岗位考点从题库与知识库中召回题目
- 模拟面试：逐题出题、流式作答、逐题评分
- 面试报告：整体表现、各题得分与评语

**管理后台**
- 题库管理：单题录入、Markdown / PDF 批量导入、向量化
- 知识库管理：文档上传、切片预览、检索测试、重建索引
- 岗位模板、用户与面试记录管理

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| ORM / 迁移 | SQLAlchemy 2.x（async） + Alembic |
| 数据库 | PostgreSQL 16 + pgvector（向量检索） |
| 缓存 / 队列 | Redis 7 |
| 异步任务 | Celery |
| LLM | DeepSeek（对话与评分）、DashScope Embedding（1024 维） |
| Agent / RAG | LangChain（Agent + `@tool`）、结构感知切分、向量 + 全文检索 |
| 前端 | Vue 3 + Vite（用户端与管理端两套独立 SPA） |
| 部署 | Docker Compose |

## 快速开始

### 前置

- Docker Desktop（跑 PostgreSQL / Redis）
- Python 3.11+、Node.js 18+

### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`，**至少填两个 key，否则 AI 相关功能不可用**：

```
DEEPSEEK_API_KEY=<platform.deepseek.com 申请>
DASHSCOPE_API_KEY=<阿里云百炼申请，用于 Embedding>
```

### 2. 起依赖服务

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

会拉起：应用、Celery worker、PostgreSQL（含 pgvector，宿主机映射 `5434`）、Redis（映射 `6382`）、Flower。

> 端口特意选了 5434 / 6382，避开本机常见的 5432 / 6379，两套环境可以共存。

### 3. 迁移与初始化数据

```bash
docker compose exec app alembic upgrade head
docker compose exec app python seed_admin.py      # 管理员账号
docker compose exec app python seed_positions.py  # 岗位模板
```

### 4. 起前端

```bash
cd frontend && npm install && npm run dev   # 用户端，默认 5173
cd admin    && npm install && npm run dev   # 管理端，默认 3001（见 vite.config）
```

### 不走 Docker 的本地开发

依赖自己装好后（本机 PostgreSQL + Redis 在跑），改 `backend/.env` 里的 `DATABASE_URL` /
`REDIS_HOST` 指向 localhost，然后：

```bash
cd backend
alembic upgrade head
uvicorn main:app --reload --port 8000

# 另开一个终端跑 worker（Windows 上必须 --pool=solo，见 celery_worker.py）
python celery_worker.py
```

`scripts/start-all.ps1`（或双击根目录的 `启动全部服务.bat`）会把上面这几件事按依赖顺序全部拉起来，
每个长驻服务各占一个窗口。

## 目录结构

```
backend/
  app/
    api/            # 路由层：client（用户端）/ backoffice（管理端）
    services/       # 业务逻辑：agent、rag、评分、邮件…
    models/         # SQLAlchemy 模型
    schemas/        # Pydantic 出入参
    core/           # 配置、Celery
    prompts/        # 提示词模板
  migrations/       # Alembic 迁移
  docker-compose.yml / .dev.yml / .prod.yml
  seed_*.py         # 初始化脚本
frontend/           # 用户端 SPA
admin/              # 管理后台 SPA
scripts/            # 本地一键启动脚本
```

## 几个实现上的取舍

**RAG 相似度阈值按实际分布校准，而不是沿用默认值。**
常见的默认阈值是 0.7，但实测本题库的命中相似度只有 0.44~0.53，用 0.7 会导致召回为 0。
按实际分布校准后既能召回到相关题，又能挡掉无关题。阈值可通过
`QUESTION_BANK_MIN_SCORE` 配置。

**知识切分按「题」的边界切，而不是固定长度切。**
固定 `chunk_size` 会把完整题目从中间劈开，检索回来的是半道题。
改为整题保留、超长题再按句二次切分，保证每个切片是一道完整的题。

**Agent 工具内部自管 DB Session。**
LangChain 的 `@tool` 无法接入 FastAPI 的 `Depends` 依赖注入，所以工具内部自己管理
Session 生命周期，而不是把请求级的 Session 透传进去。

**Celery 任务用独立的 engine，用完即 `dispose()`。**
worker 是长驻进程、每个任务用 `asyncio.run` 新建事件循环，而连接池会跨事件循环复用
绑定在已关闭 loop 上的 asyncpg 连接，表现为「第一个任务正常、第二个任务必崩」。
改用独立 engine 并在用后清池解决。

## 说明

个人项目。项目中的示例数据、提示词与知识库语料仅用于演示，不构成任何专业建议。
