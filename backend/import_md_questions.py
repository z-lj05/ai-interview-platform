"""import_md_questions.py — 命令行版题库导入（md / txt，管理端页面导入的等价物）

链路：本地 .md → parse_question_file 切题 → POST /batch-import → Celery 向量化

用法（在 backend 目录下）：../.venv/Scripts/python import_md_questions.py

与 import_pdf_questions.py 只差几个常量——切题逻辑同住
app/services/common/question_parser.py，和管理端页面共用。

导之前先看一眼切出来是不是真题目：md 的切题规则是"### 标题 = 一道题"，
如果这份 md 的标题是**话术小标题/章节名**（不是问题），切出来的就不是题。
命令行没有预览，先跑一遍看上面打印的样例：
    1.分诊Agent工作流：      ← 这种是话术稿，别导
    先用一句话介绍一下你的项目  ← 这种才是题
管理端页面的「解析预览」就是为这一步准备的。

前置：后端服务运行中（8000）；管理端账号可登录。
"""
import os

import httpx

from app.services.common.question_parser import build_items, parse_question_file

FILE_PATH = r"D:\桌面\ai-interview-agent\ai-interview-agent\AI面试项目问答清单.md"
BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "a@new.com"
ADMIN_PASSWORD = "123456"

CATEGORY = "project"              # 分类 = 项目（管理端筛选"项目"可见）
POSITION_TAG = "python_backend"   # 出题检索按它筛：想被模拟面试捞到就保持这个值
DIFFICULTY = "medium"
SOURCE = "project-qa"             # 来源标记


def main():
    # ① 读文件 → 切题
    with open(FILE_PATH, "rb") as f:
        file_bytes = f.read()
    result = parse_question_file(os.path.basename(FILE_PATH), file_bytes)
    parsed = result["parsed"]
    print(f"[1/3] 读取文件：{len(file_bytes)} 字节，切题方式 = {result['strategy']}")
    print(f"[2/3] 切出 {len(parsed)} 道题")
    for i, p in enumerate(parsed[:3], 1):
        print(f"      样例 {i}: [{p.get('chapter', '')}] {p['question'][:50]}")
    if parsed:
        last = parsed[-1]
        print(f"      末题: [{last.get('chapter', '')}] {last['question'][:50]}"
              f"（答案 {len(last['reference_answer'])} 字）")

    # ② 登录管理端拿 token
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        resp = client.post(
            "/api/v1/backoffice/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        token = resp.json()["data"]["access_token"]

        # ③ 批量导入
        resp = client.post(
            "/api/v1/backoffice/question-bank/batch-import",
            json={"items": build_items(
                parsed,
                category=CATEGORY,
                position_tag=POSITION_TAG,
                difficulty=DIFFICULTY,
                source=SOURCE,
            )},
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"[3/3] 导入响应 {resp.status_code}: {resp.json().get('message')}")

    print("\n完成。管理端「题库管理」→ 分类筛选选「项目」即可看到。")


if __name__ == "__main__":
    main()
