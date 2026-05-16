## 题目本质

设计 **Music Player Shuffle Algorithm** (LLD)：playlist shuffle，每首歌恰好播一次，random order。变种：smart shuffle (artist diversity / no repeat artist back-to-back)。

参考 [[cm6jwvh80005vui4b4epro213]] (Song Shuffler) - 系统设计版。这里 LLD focus on data structure + class design。

## 核心：Fisher-Yates Shuffle

```python
import random

class Playlist:
    def __init__(self, songs: list['Song']):
        self.songs = list(songs)
        self._shuffled: list[int] = []      # indices into self.songs
        self._cursor: int = 0
        self.shuffled_mode: bool = False
        self.repeat_mode: 'none' | 'one' | 'all' = 'none'

    def _fisher_yates(self):
        self._shuffled = list(range(len(self.songs)))
        for i in range(len(self._shuffled) - 1, 0, -1):
            j = random.randint(0, i)
            self._shuffled[i], self._shuffled[j] = self._shuffled[j], self._shuffled[i]
        self._cursor = 0

    def shuffle(self):
        self.shuffled_mode = True
        self._fisher_yates()

    def unshuffle(self):
        self.shuffled_mode = False
        self._shuffled = list(range(len(self.songs)))
        self._cursor = 0

    def next_song(self) -> 'Song' | None:
        if not self.songs: return None
        if self.repeat_mode == 'one':
            return self.songs[self._shuffled[self._cursor] if self.shuffled_mode else self._cursor]
        self._cursor += 1
        if self._cursor >= len(self.songs):
            if self.repeat_mode == 'all':
                if self.shuffled_mode:
                    self._fisher_yates()   # 新一轮 shuffle
                else:
                    self._cursor = 0
            else:
                return None
        idx = self._shuffled[self._cursor] if self.shuffled_mode else self._cursor
        return self.songs[idx]

    def prev_song(self) -> 'Song' | None:
        if self._cursor == 0:
            return None
        self._cursor -= 1
        idx = self._shuffled[self._cursor] if self.shuffled_mode else self._cursor
        return self.songs[idx]

    def jump_to(self, song_idx: int):
        """User selects specific song. 切回非 shuffled or adjust cursor."""
        if self.shuffled_mode:
            # 找 song_idx 在 _shuffled 中的 position
            new_cursor = self._shuffled.index(song_idx)
            self._cursor = new_cursor
        else:
            self._cursor = song_idx
```

## 进阶: Smart Shuffle (Artist Diversity)

普通 Fisher-Yates 可能让同 artist 歌曲连播。**Constraint shuffle**:

```python
def smart_shuffle(self):
    """Avoid same artist back-to-back"""
    import random
    songs = list(self.songs)
    random.shuffle(songs)
    result = []
    while songs:
        candidate = None
        for i, s in enumerate(songs):
            if not result or s.artist != result[-1].artist:
                candidate = (i, s); break
        if candidate is None:
            # 没有 different-artist 选项，prefer 最早的
            candidate = (0, songs[0])
        result.append(candidate[1])
        songs.pop(candidate[0])
    self._shuffled = [self.songs.index(s) for s in result]
```

更高级：avoid same album / same genre back-to-back。Constraint satisfaction problem。

## 进阶: Spotify-style Pseudo-random Shuffle

Pure random 让用户 perceived "not random enough"（cluster effect）。Spotify 用 **interleave by artist** —— 把同 artist 歌均分散开。

```python
def spotify_shuffle(songs):
    # 1. Group by artist
    by_artist = defaultdict(list)
    for s in songs:
        by_artist[s.artist].append(s)
    # 2. Shuffle within each group
    for group in by_artist.values():
        random.shuffle(group)
    # 3. Distribute: 总 length N，每 artist 之间 spacing ~= N / len(group)
    # ...
```

## 易错点

> [!pitfall]
> ❌ Naive shuffle 在 next 时每次随机抽 song —— 同 song 可能重复；
> ❌ Repeat mode 不重 shuffle → 第二轮顺序同；
> ❌ Jump 后 shuffle 顺序乱 → 需要 sync cursor；
> ❌ Smart shuffle 完全 deterministic → user 觉得不 random；加点随机；
> ❌ Stateful （cursor 在 playlist object）→ 切 playlist 不重置。

> [!key]
> Music shuffle 看似简单实有讲究：(1) **Fisher-Yates** unbiased base；(2) **State (cursor + shuffled order)** for prev/next；(3) **Constraint-based smart shuffle** for UX。

> [!followup]
> "如何 sync shuffle order across devices？" → server-side seed + 每 user playlist version；"如何加 personalization (listening history)？" → shuffle weight by user preference；"实时 add song 到 shuffled queue？" → insert at random valid position；"如何 undo shuffle？" → 保存 shuffle 前 cursor + 原顺序。
