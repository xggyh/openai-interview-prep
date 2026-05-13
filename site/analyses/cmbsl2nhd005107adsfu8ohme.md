## 题目本质

实现一个 **multi-threaded web crawler**：从给定 URL 开始 BFS 爬同域内可达 URL，多线程并发抓取，保证**线程安全**（共享 queue + visited set）。

OpenAI Staff 级 1 人报告。考点：**生产者-消费者模式 + 锁 / 并发集合 + 域过滤**。

## 题目语义

```python
crawler = WebCrawler(num_threads=8)
result = crawler.crawl("https://example.com/")
# result 包含同域所有可达 URL
```

`HtmlParser.getUrls(url)` 是 API 提供的（同步阻塞），返回 url 包含的子 URL。

## 解题切入点

BFS 加并发：
- **共享 queue**：待访问 URL（`queue.Queue` 线程安全）
- **共享 visited**：已访问 URL（用 set + `Lock` 或 `concurrent.futures.thread_safe_dict`）
- **worker thread**：循环 `q.get() → fetch → enqueue children`

经典 **producer-consumer** 模式。

## Python 实现（threading）

```python
from queue import Queue
from threading import Thread, Lock
from urllib.parse import urlparse

class HtmlParser:
    """题目提供的接口；阻塞调用"""
    def getUrls(self, url: str) -> list[str]: ...


class WebCrawler:
    """多线程爬虫，限定同域"""

    def __init__(self, num_threads: int = 8):
        self.num_threads = num_threads

    def crawl(self, startUrl: str, htmlParser: HtmlParser) -> list[str]:
        host = urlparse(startUrl).hostname
        visited: set[str] = {startUrl}
        visited_lock = Lock()
        q: Queue = Queue()
        q.put(startUrl)

        def worker():
            while True:
                url = q.get()
                if url is None:
                    q.task_done()
                    return
                try:
                    children = htmlParser.getUrls(url)
                    for child in children:
                        if urlparse(child).hostname != host:
                            continue
                        with visited_lock:
                            if child in visited:
                                continue
                            visited.add(child)
                        q.put(child)
                finally:
                    q.task_done()

        threads = [Thread(target=worker, daemon=True) for _ in range(self.num_threads)]
        for t in threads:
            t.start()

        q.join()   # 等所有 task done

        # 通知 workers 退出
        for _ in range(self.num_threads):
            q.put(None)
        for t in threads:
            t.join()

        return list(visited)
```

## 关键设计点

### 1. 线程安全的 visited

`set` 在 Python 不是线程安全（多线程 add 可能丢）。两种选项：

**A. Lock + 普通 set**（上面实现）：简单，加锁开销小（set add 微秒级）。

**B. concurrent.futures.ThreadSafeDict 或 dict(自带原子性)**：
```python
visited = {}   # dict 的单 key set/delete 在 CPython 是原子的（GIL）
# 用 setdefault 原子 add
if visited.setdefault(child, True) is True and child wasn't there:
    ...   # 但难判断 "刚加入"
```

实操：**A 更可控**。

### 2. 同域过滤

`urlparse(url).hostname` 抽出 host，等于 startUrl 的才入队。注意：
- `www.example.com` vs `example.com` 是不同 host —— 要不要 strip "www."？按题面
- 大小写：HTTP host 不敏感，建议 `.lower()`

### 3. q.join() vs Event signal

`Queue.join()` 等所有 `put` 都被 `task_done()`。这个是优雅终止的标准方式：

```
producer 入队 N 个 → 调 q.join() 等 N 次 task_done → 所有处理完
```

终止 worker：put N 个 None（sentinel），worker 看见 None 就 return。

### 4. 线程数选择

- IO-bound 任务 → 线程多比 CPU 数多没问题（GIL 在 IO 时释放）
- 一般 8-32 线程对 HTTP 抓取是合理的
- 过多 → host server 限速 / 自己 file descriptor 枯竭

## 使用 asyncio 的版本（更现代）

```python
import asyncio
import aiohttp
from urllib.parse import urlparse

async def crawl(start: str, max_concurrent: int = 8) -> set[str]:
    host = urlparse(start).hostname
    visited = {start}
    q = asyncio.Queue()
    await q.put(start)
    sem = asyncio.Semaphore(max_concurrent)

    async with aiohttp.ClientSession() as sess:
        async def fetch(url):
            async with sem:
                async with sess.get(url) as r:
                    return await r.text()

        async def worker():
            while True:
                url = await q.get()
                try:
                    html = await fetch(url)
                    for child in extract_urls(html):
                        if urlparse(child).hostname != host:
                            continue
                        if child not in visited:
                            visited.add(child)
                            await q.put(child)
                finally:
                    q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
        await q.join()
        for w in workers:
            w.cancel()
    return visited
```

异步版本 IO 更高效（单线程切换 coroutine，无 GIL 抢锁开销）。但 `aiohttp` 不是 stdlib，面试时看库可用性决定。

## 复杂度

- 时间：依赖网络 IO，跟 URL 数和单 fetch 延迟相关
- 空间：O(N) for visited set，N = 同域 URL 数
- 并发增益：N_threads × 单线程吞吐 / (1 + IO wait)

## 易错点

> [!pitfall]
> ❌ `visited.add` 不加锁 → 重复抓 / 漏抓；
> ❌ 用 `list` 作 frontier 不是 `Queue` → 不线程安全 + pop 慢；
> ❌ 没法判断"所有 worker 都空闲了" → 用 `Queue.join()`；
> ❌ Worker 抛异常没 `task_done` → q.join 永远 hang；用 try/finally；
> ❌ Same-domain 判断用 `url.startswith(prefix)` → URL `https://example.com.evil.com/` 通过检查；用 `urlparse(...).hostname`；
> ❌ 没限制并发请求数 → 一次性发 1000 个 request 把目标服务器打挂。

> [!key]
> 三大支柱：(1) **共享 Queue 做 BFS frontier**；(2) **共享 visited set + Lock**；(3) **`q.join()` 等结束 + sentinel 退出 workers**。注意 same-domain 用 hostname 比较，不是 prefix 匹配。

> [!followup]
> "如何 distributed crawler？" → frontier 用 Kafka / Redis；visited 用 Redis SET 或 Bloom filter；多机 workers；"如何 robots.txt？" → 每 host 启动前 fetch + 解析 + 缓存；"如何 polite crawling？" → per-host rate limit (1 req/sec)；"如何 dedup 内容（不同 URL 同内容）？" → simhash on body。
