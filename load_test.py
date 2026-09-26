"""接口压测 —— 取真实的 QPS 与延迟分布

用法（后端需已在 8000 端口跑起来，且库里有数据）：
    python load_test.py

    改压测目标：见下方的 TARGETS / CONCURRENCY / DURATION

为什么不用 hey / wrk：
    本机没装，而且它们压不了带 Bearer 鉴权的接口。httpx + asyncio 三十行就够，
    还能顺便按 HTTP 状态码分类错误（4xx 说明是鉴权/参数问题，5xx 才是服务端问题）。

压的是**只查库、不调 LLM**的接口：
    调 LLM 的接口（出题 / 评分 / 分诊）一次要好几百毫秒且要花钱，压它们既没意义也不合适——
    那测的是 DeepSeek 的 QPS，不是这套代码的 QPS。
"""
import asyncio
import statistics
import time

import httpx

BASE = 'http://localhost:8000/api/v1'
ADMIN = {'email': 'a@new.com', 'password': '123456'}

# 压测目标：只查库的读接口
TARGETS = [
    ('题库列表（分页+count）', '/backoffice/question-bank?page=1&size=20'),
    ('面试列表（用户+面试聚合）', '/backoffice/interviews?page=1&size=20'),
]

CONCURRENCY = [1, 10, 50]
DURATION = 6          # 每档压 6 秒


async def one_worker(client, url, headers, deadline, lat, errs):
    while time.monotonic() < deadline:
        t0 = time.perf_counter()
        try:
            r = await client.get(url, headers=headers)
            dt = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                lat.append(dt)
            else:
                errs.append(r.status_code)
        except Exception as exc:
            errs.append(type(exc).__name__)


async def run_level(url, headers, conc):
    lat, errs = [], []
    limits = httpx.Limits(max_connections=conc + 5, max_keepalive_connections=conc + 5)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await client.get(url, headers=headers)          # 预热：别把首连开销算进去
        deadline = time.monotonic() + DURATION
        t0 = time.monotonic()
        await asyncio.gather(*[
            one_worker(client, url, headers, deadline, lat, errs) for _ in range(conc)
        ])
        elapsed = time.monotonic() - t0

    if not lat:
        return None
    lat.sort()
    return {
        'conc': conc,
        'qps': len(lat) / elapsed,
        'p50': statistics.median(lat),
        'p95': lat[int(len(lat) * 0.95) - 1],
        'p99': lat[int(len(lat) * 0.99) - 1],
        'max': lat[-1],
        'n': len(lat),
        'err': len(errs),
    }


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        tok = (await c.post(f'{BASE}/backoffice/auth/login', json=ADMIN)).json()['data']['access_token']
    headers = {'Authorization': f'Bearer {tok}'}

    for name, path in TARGETS:
        url = BASE + path
        print(f'\n【{name}】  {path}')
        print(f"  {'并发':<6}{'QPS':<10}{'P50':<10}{'P95':<10}{'P99':<10}{'最慢':<10}{'样本':<8}{'错误'}")
        for conc in CONCURRENCY:
            r = await run_level(url, headers, conc)
            if r is None:
                print(f'  {conc:<6}--- 无成功样本 ---')
                continue
            print(f"  {r['conc']:<6}{r['qps']:<10.1f}{r['p50']:<10.0f}{r['p95']:<10.0f}"
                  f"{r['p99']:<10.0f}{r['max']:<10.0f}{r['n']:<8}{r['err']}")


if __name__ == '__main__':
    asyncio.run(main())
