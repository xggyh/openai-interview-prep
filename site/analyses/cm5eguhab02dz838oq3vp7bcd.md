## 题目本质

**LC 489 Robot Room Cleaner**：未知形状的房间，机器人通过 API 移动和清扫：`move()` (前进，被墙挡返回 False) / `turnLeft()` / `turnRight()` / `clean()`。请清扫整个房间。**机器人不知道自己在哪 / 房间布局**。

Google 经典 hard。考点：**DFS + 状态回退 + 相对坐标系跟踪**。

## 解题切入点

机器人 API 不返回位置 → 用**相对坐标系** + **方向 + DFS visited set**：

1. 起点视为 (0, 0)
2. 维护当前方向（0=up, 1=right, 2=down, 3=left）
3. DFS：每到一格，clean → 试 4 个方向 → 若能 move 就递归 → 回溯（**机器人需物理回退**）
4. visited set 记录已清扫的 (x, y)

**核心难点**：DFS 回溯时机器人不会自动回到上一格 —— 你必须**让它走回去**。

## Python 实现

```python
class Solution:
    def cleanRoom(self, robot):
        DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]   # up, right, down, left
        visited = set()

        def go_back():
            """让机器人物理回到调用 dfs 之前的位置 + 朝向"""
            robot.turnRight(); robot.turnRight()    # 180°
            robot.move()                             # 走回一格
            robot.turnRight(); robot.turnRight()    # 再 180° 朝向恢复

        def dfs(x: int, y: int, d: int):
            robot.clean()
            visited.add((x, y))
            for i in range(4):
                # 试这个方向：当前 direction 是 d，候选 = (d + i) % 4
                new_d = (d + i) % 4
                dx, dy = DIRS[new_d]
                nx, ny = x + dx, y + dy
                if (nx, ny) not in visited and robot.move():
                    dfs(nx, ny, new_d)
                    go_back()
                # 转向下个尝试方向
                robot.turnRight()
            # 转完 4 次回到 d 朝向（4 个 right = 一圈）

        dfs(0, 0, 0)
```

## 关键技术细节

### 1. 方向定义和 turnRight

`turnRight` 把朝向顺时针旋 90°：`d → (d+1) % 4`。每次试一个方向后 turnRight，下一轮试新方向。4 次 turnRight 后恢复原朝向。

### 2. go_back() —— 物理回退

DFS 递归回来时，机器人物理位置在递归路径的某个 cell。我们要让它回到调用前的位置 + 朝向：

- 180° 转身（两次 right）
- move 一格（这就回去了）
- 再 180° 回原朝向

**为什么这样？** 不能直接 "turnRight 4 次 + move" —— 那只能前进，不能后退。

### 3. visited 的判断时机

**先判断 (nx, ny) not in visited 再试 move**。这样：
- 已 visited 的格子不再 move 探索（节省）
- 但仍要 turnRight 走完 4 个方向（保持朝向逻辑）

### 4. 不需要全局坐标

视起点为 (0, 0)，所有移动相对。`visited` 跟踪我们已**访问过**的格子 —— 用相对坐标足够，不需要知道房间真实形状。

## 复杂度

- 时间：**O(N − M)**，N = 房间面积，M = 障碍物数。每个可达 cell 访问 1 次清扫 + 最多 4 次邻居检查
- 空间：**O(N − M)**，visited set + 递归栈

## 调试用 mock

```python
class Robot:
    def __init__(self, grid: list[list[int]], start_x: int, start_y: int):
        self.grid = grid
        self.x, self.y = start_x, start_y
        self.d = 0                        # 起始朝 up
        self.cleaned = set()
    def move(self) -> bool:
        DIRS = [(-1,0),(0,1),(1,0),(0,-1)]
        dx, dy = DIRS[self.d]
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < len(self.grid) and 0 <= ny < len(self.grid[0]) and self.grid[nx][ny] != 0:
            self.x, self.y = nx, ny
            return True
        return False
    def turnLeft(self): self.d = (self.d - 1) % 4
    def turnRight(self): self.d = (self.d + 1) % 4
    def clean(self): self.cleaned.add((self.x, self.y))
```

## 易错点

> [!pitfall]
> ❌ DFS 回溯不让机器人物理回退 —— 下次方向算错；
> ❌ go_back 只 180° 转身没走一格 —— 没回到位置；
> ❌ 没在 turnRight 4 次后保持原朝向 —— 一轮探索结束朝向乱；
> ❌ visited 在 DFS 时把所有方向尝试过的格子都加 —— 应该只加 clean 过的格子；
> ❌ 起点的坐标硬编码成 0,0 但代码里又用真实坐标 —— 必须用相对。

> [!key]
> 经典"隐藏状态 + 物理 agent" 模式：(1) 自己建相对坐标；(2) 记朝向；(3) DFS 后必须**物理回退**让 agent 状态匹配递归栈。这套思路也用于：盲走迷宫、IoT 设备远控、棋盘 AI 模拟未来位置后回退。

> [!followup]
> "如果地图是 8 方向？" → 不行，机器人 API 只支持 turn 90°；"如果有多个机器人？" → 协同需要共享 visited，注意死锁；"如果允许 teleport 回起点？" → DFS 结束不需要 go_back；"实战机器人怎么定位？" → SLAM (Simultaneous Localization and Mapping)，但 LC 简化为相对坐标。
