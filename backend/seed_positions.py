"""重建岗位模板数据（管理端接口用）"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def call(path, data, token=None, method="POST"):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with urllib.request.urlopen(req, body, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


# 1. 管理端登录（9a）
login = call("/backoffice/auth/login", {"email": "a@new.com", "password": "123456"})
token = login["data"]["access_token"]
print("管理员登录 OK")

POSITIONS = [
    {
        "position_tag": "python_backend",
        "title": "Python 后端开发工程师",
        "category": "backend",
        "level": "junior",
        "core_skills": ["Python", "FastAPI", "SQLAlchemy", "REST API", "PostgreSQL"],
        "nice_to_have_skills": ["Redis", "Celery", "Docker", "AI 应用"],
        "project_keywords": ["电商后端", "AI应用", "API平台"],
        "focus_topics": ["异步编程", "ORM 与数据库设计", "中间件与鉴权", "缓存与队列", "API 设计"],
        "recommended_query_keywords": ["Python", "FastAPI", "异步", "ORM"],
        "recommended_difficulty": "medium",
        "recommended_question_count": 8,
        "jd_summary": "负责电商后端 API 开发，使用 Python/FastAPI 技术栈，涉及数据库设计与接口安全。",
        "typical_companies": ["字节跳动", "美团", "阿里"],
        "sort_order": 1,
        "is_active": True,
    },
    {
        "position_tag": "java_backend",
        "title": "Java 后端开发工程师",
        "category": "backend",
        "level": "junior",
        "core_skills": ["Java", "Spring Boot", "MyBatis", "MySQL", "微服务"],
        "nice_to_have_skills": ["Kafka", "Redis", "Docker"],
        "project_keywords": ["电商后端", "订单系统", "微服务"],
        "focus_topics": ["Spring 核心", "JVM 内存模型", "并发编程", "分布式事务", "消息队列"],
        "recommended_query_keywords": ["Java", "Spring", "并发", "JVM"],
        "recommended_difficulty": "medium",
        "recommended_question_count": 8,
        "jd_summary": "负责交易系统后端开发，Java/Spring Boot 技术栈，涉及高并发与分布式场景。",
        "typical_companies": ["京东", "携程", "拼多多"],
        "sort_order": 2,
        "is_active": True,
    },
    {
        "position_tag": "vue_frontend",
        "title": "Vue 前端开发工程师",
        "category": "frontend",
        "level": "junior",
        "core_skills": ["JavaScript", "Vue3", "TypeScript", "Vite", "HTML/CSS"],
        "nice_to_have_skills": ["Pinia", "SSR", "微前端"],
        "project_keywords": ["管理后台", "可视化", "中台系统"],
        "focus_topics": ["响应式原理", "组件通信", "状态管理", "路由与权限", "性能优化"],
        "recommended_query_keywords": ["Vue", "JavaScript", "组件", "状态管理"],
        "recommended_difficulty": "medium",
        "recommended_question_count": 8,
        "jd_summary": "负责管理后台与数据可视化前端开发，Vue3/Vite 技术栈。",
        "typical_companies": ["腾讯", "蚂蚁集团", "B站"],
        "sort_order": 3,
        "is_active": True,
    },
]

for p in POSITIONS:
    try:
        r = call("/backoffice/position-templates", p, token)
        print(f"创建 {p['position_tag']} -> id={r['data']['id']}")
    except Exception as e:
        # 查重 400：已存在则跳过
        print(f"{p['position_tag']}: {e}")
