"""import_pdf_questions.py — 命令行版题库导入（管理端页面导入的等价物）

链路：本地文件 → parse_question_file 切题 → POST /batch-import → Celery 向量化

用法（在 backend 目录下）：../.venv/Scripts/python import_pdf_questions.py

切题逻辑**不在本文件**：它住在 app/services/common/question_parser.py，
管理端「批量导入题目 → 方式一：上传文件」调的是同一个函数——
改切题规则时两边一起变，不会像以前那样各留一份拷贝（那份旧拷贝题面长度还停在 80）。

什么时候用脚本、什么时候用页面：
- 页面：传一两个文件、想先看预览再导
- 脚本：一次灌十几个文件、或想写进定时任务

前置：后端服务运行中（8000）；管理端账号可登录。
"""
import logging
import os

import httpx

from app.services.common.question_parser import build_items, parse_question_file

# pdfminer 对某些 PDF 会刷 FontBBox 警告，静音处理（不影响提取结果）
logging.getLogger("pdfminer").setLevel(logging.ERROR)

FILE_PATH = r"C:\Users\zenglingjiang\Downloads\Nginx 面试题速记通关版 _ 面试刷题 mianshiya.com.pdf"
BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "a@new.com"
ADMIN_PASSWORD = "123456"

CATEGORY = "technical"
POSITION_TAG = "python_backend"
DIFFICULTY = "medium"
SOURCE = "pdf-import"


def main():
    # ① 读文件 → 切题
    with open(FILE_PATH, "rb") as f:
        file_bytes = f.read()
    result = parse_question_file(os.path.basename(FILE_PATH), file_bytes)
    parsed = result["parsed"]
    print(f"[1/3] 读取文件：{len(file_bytes)} 字节，切题方式 = {result['strategy']}")
    print(f"[2/3] 切出 {len(parsed)} 道题")
    for i, p in enumerate(parsed[:3], 1):
        print(f"      样例 {i}: {p['question'][:60]}")
        print(f"        答案开头: {p['reference_answer'][:60]}...")

    # ② 登录管理端拿 token
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        resp = client.post(
            "/api/v1/backoffice/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        token = resp.json()["data"]["access_token"]

        # ③ 批量导入（走现成接口 → 校验/落库/异步向量化一条龙）
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

    print("\n完成。去管理端「题库管理」看题数变化，用「检索测试」搜一道新题的关键词验证。")


if __name__ == "__main__":
    main()
