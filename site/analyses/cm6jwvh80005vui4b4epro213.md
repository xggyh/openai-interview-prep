## 题目本质

**Song Shuffler**：实现播放列表 shuffle，每首歌恰好播一次，**uniform random**（每个排列等概率）。也有变种：add/remove songs；多人偏好的拓扑序合并。

## 主要解法：Fisher-Yates Shuffle

经典 unbiased shuffle，O(N) 时间。

## Python 实现

```python
import random

class Playlist:
    def __init__(self, songs: list[str]):
        self.songs = list(songs)
        self.order: list[int] = []   # 待播 idx
        self.shuffle()

    def add(self, song: str):
        self.songs.append(song)
        # 简化：加入后重新 shuffle 剩余
        self.order = list(range(len(self.songs)))
        self._fisher_yates(self.order)

    def remove(self, song: str):
        idx = self.songs.index(song)
        self.songs.pop(idx)
        self.order = list(range(len(self.songs)))
        self._fisher_yates(self.order)

    def shuffle(self):
        self.order = list(range(len(self.songs)))
        self._fisher_yates(self.order)

    def next_song(self) -> str | None:
        if not self.order:
            return None
        idx = self.order.pop()
        return self.songs[idx]

    @staticmethod
    def _fisher_yates(arr: list):
        for i in range(len(arr) - 1, 0, -1):
            j = random.randint(0, i)
            arr[i], arr[j] = arr[j], arr[i]
```

## Fisher-Yates 证明 uniform

每个排列概率 = 1/n × 1/(n-1) × ... × 1/1 = 1/n!。

错误版本（Naive Shuffle）：每位置随机选另一位置 swap，**结果有偏**（不是 uniform）。

```python
# WRONG (biased)
def naive_shuffle(arr):
    for i in range(len(arr)):
        j = random.randint(0, len(arr) - 1)  # 错：应是 i..n-1
        arr[i], arr[j] = arr[j], arr[i]
```

## 多人偏好合并（拓扑序题）

如果 N 人每人给一个偏好顺序（partial order），找一个 valid total order 满足所有：**拓扑排序**。

```python
def merge_preferences(prefs: list[list[str]]) -> list[str] | None:
    """每个 pref 是该用户给出的歌曲偏好序"""
    from collections import defaultdict, deque
    in_deg = defaultdict(int)
    adj = defaultdict(set)
    songs = set()
    for p in prefs:
        for s in p:
            songs.add(s)
        for i in range(len(p) - 1):
            if p[i+1] not in adj[p[i]]:
                adj[p[i]].add(p[i+1])
                in_deg[p[i+1]] += 1
    q = deque(s for s in songs if in_deg[s] == 0)
    order = []
    while q:
        s = q.popleft()
        order.append(s)
        for nxt in adj[s]:
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                q.append(nxt)
    return order if len(order) == len(songs) else None
```

## 复杂度

- Shuffle: **O(N)**
- 拓扑序合并: O(V + E)

## 关键技术点

### 1. Fisher-Yates 的正确性

第 i 步从 [0, i] 选 j（不是 [0, n-1]），保证已 fix 的部分不被打乱。这是 unbiased 的关键。

### 2. random.shuffle 即是 Fisher-Yates

Python `random.shuffle(list)` 内部就是 Fisher-Yates。生产代码直接用，面试要会自己写。

### 3. 不要在 shuffle 后再"调整一下" 

任何二次操作（如"避免连续两首同 artist"）会破坏 uniform。需要其他算法（rejection sampling 或加权采样）。

## 易错点

> [!pitfall]
> ❌ Naive shuffle 用 `randint(0, n-1)` 在每个位置 → 有偏 (n^n 选法 / n! 排列 → 不均匀)；
> ❌ 用 `sorted(arr, key=lambda x: random.random())` shuffle —— 部分语言/版本有偏；
> ❌ 多线程同时 shuffle —— 需锁；
> ❌ 偏好合并有环 → 无 valid order，必须 detect 并返回 None。

> [!key]
> Fisher-Yates 是 uniform shuffle 的金标准。同思路：reservoir sampling (k 个元素从 stream 等概率)、weighted random selection。

> [!followup]
> "shuffle 后避免连续重复 artist？" → swap 相邻重复元素到非相邻位置（如果可能）；"多用户的偏好同时考虑？" → 拓扑序合并（如上）；"流式 add song 同时 shuffle？" → reservoir sampling 维护当前 random pick。
