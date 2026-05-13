## 题目本质

**Monster Game** —— 设计实现一个怪兽游戏系统。题面相对开放，跟 `Monster Fight` 类似但要求**适当的数据结构和游戏机制**。OOP 设计题。

跟 `Monster Fight` 的区别：这一题更倾向"一个游戏的核心循环"（main loop + state + 简单 input handling），不限于战斗。

## 解题切入点

OOP 题面太开放时，**先澄清范围**：
- 单人 vs 多人？→ 假设单人 PvE
- 实时 vs 回合制？→ 假设回合制（简单）
- 战斗 / 探索 / 升级？→ 全要素简化版

然后画 4-5 个核心类 + 主循环。

## 核心实体设计

```ascii
              ┌──────────────┐
              │   Game       │   主循环 / 状态机
              │              │   - state: MENU / PLAYING / OVER
              │              │   - player: Player
              │              │   - world: World
              └──────┬───────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌────────┐  ┌──────────┐  ┌──────────┐
   │ Player │  │  World   │  │  Battle  │
   │  - hp  │  │  (grid)  │  │  Engine  │
   │  - lvl │  │  - rooms │  │ (turn-   │
   │  - inv │  │  - npcs  │  │  based)  │
   └────────┘  └──────────┘  └──────────┘
                     │
                     ▼
                ┌──────────┐
                │ Monster  │  - name, hp, atk, def
                │  (NPC)   │  - drop loot
                └──────────┘
```

## Python 实现

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Optional

class GameState(Enum):
    MENU = 'menu'
    PLAYING = 'playing'
    BATTLE = 'battle'
    OVER = 'over'

@dataclass
class Item:
    name: str
    effect: str        # 'heal' / 'weapon' / 'key'
    magnitude: int = 0

@dataclass
class Player:
    name: str
    hp: int = 100
    max_hp: int = 100
    atk: int = 15
    def_: int = 5
    level: int = 1
    xp: int = 0
    gold: int = 0
    inventory: list[Item] = field(default_factory=list)
    pos: tuple[int, int] = (0, 0)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def use_item(self, idx: int) -> str:
        if idx < 0 or idx >= len(self.inventory):
            return "no such item"
        item = self.inventory.pop(idx)
        if item.effect == 'heal':
            self.hp = min(self.max_hp, self.hp + item.magnitude)
            return f"used {item.name}, healed {item.magnitude}"
        return f"can't use {item.name} here"

    def gain_xp(self, amt: int) -> str:
        self.xp += amt
        msg = f"+{amt} XP"
        # 简单升级公式：xp >= 100 * level
        while self.xp >= 100 * self.level:
            self.xp -= 100 * self.level
            self.level += 1
            self.max_hp += 20
            self.hp = self.max_hp
            self.atk += 3
            self.def_ += 1
            msg += f" | LEVEL UP! → L{self.level}"
        return msg

@dataclass
class Monster:
    name: str
    hp: int
    max_hp: int
    atk: int
    def_: int
    xp_reward: int
    gold_reward: int
    drop: Optional[Item] = None

    @classmethod
    def random(cls, player_level: int) -> 'Monster':
        templates = [
            ('Slime',    20, 5, 2),
            ('Goblin',   35, 10, 4),
            ('Orc',      60, 18, 8),
            ('Dragon',  150, 30, 20),
        ]
        i = min(player_level - 1, len(templates) - 1)
        name, hp, atk, dfn = templates[i]
        return cls(name=name, hp=hp, max_hp=hp, atk=atk, def_=dfn,
                   xp_reward=10 * (i + 1) * player_level,
                   gold_reward=5 * (i + 1) * player_level)

@dataclass
class Room:
    description: str
    monster: Optional[Monster] = None
    item: Optional[Item] = None
    exits: dict[str, tuple[int, int]] = field(default_factory=dict)  # 'north' -> (x,y)

class World:
    def __init__(self):
        self.rooms: dict[tuple[int, int], Room] = {}
        self._build_starter()

    def _build_starter(self):
        # 3x3 网格 demo
        self.rooms[(0, 0)] = Room(description='village square',
                                  exits={'north': (0, 1), 'east': (1, 0)})
        self.rooms[(0, 1)] = Room(description='dark forest',
                                  monster=Monster(name='Goblin', hp=35, max_hp=35, atk=10, def_=4,
                                                  xp_reward=30, gold_reward=15),
                                  exits={'south': (0, 0)})
        self.rooms[(1, 0)] = Room(description='ancient ruins',
                                  item=Item(name='Health Potion', effect='heal', magnitude=30),
                                  exits={'west': (0, 0)})

    def get(self, pos: tuple[int, int]) -> Optional[Room]:
        return self.rooms.get(pos)


class BattleEngine:
    @staticmethod
    def fight(player: Player, monster: Monster) -> list[str]:
        log = [f"Battle: {player.name} vs {monster.name}"]
        while player.alive and monster.hp > 0:
            # 玩家先攻
            dmg = max(1, player.atk - monster.def_)
            monster.hp -= dmg
            log.append(f"You hit {monster.name} for {dmg} (mon hp: {max(0, monster.hp)})")
            if monster.hp <= 0:
                log.append(f"{monster.name} defeated!")
                log.append(player.gain_xp(monster.xp_reward))
                player.gold += monster.gold_reward
                log.append(f"+{monster.gold_reward} gold")
                if monster.drop:
                    player.inventory.append(monster.drop)
                    log.append(f"obtained {monster.drop.name}")
                return log
            # 怪反击
            dmg2 = max(1, monster.atk - player.def_)
            player.hp -= dmg2
            log.append(f"{monster.name} hits you for {dmg2} (your hp: {max(0, player.hp)})")
        if not player.alive:
            log.append("You died.")
        return log


class Game:
    def __init__(self, player_name: str):
        self.player = Player(name=player_name)
        self.world = World()
        self.state = GameState.PLAYING

    def move(self, direction: str) -> list[str]:
        room = self.world.get(self.player.pos)
        if not room or direction not in room.exits:
            return ["can't go there"]
        self.player.pos = room.exits[direction]
        return self.look()

    def look(self) -> list[str]:
        room = self.world.get(self.player.pos)
        log = [f"You are in: {room.description}"]
        if room.item:
            log.append(f"You see: {room.item.name}")
        if room.monster and room.monster.hp > 0:
            log.append(f"A wild {room.monster.name} blocks your path!")
            log.extend(BattleEngine.fight(self.player, room.monster))
            if not self.player.alive:
                self.state = GameState.OVER
        log.append(f"Exits: {list(room.exits.keys())}")
        return log

    def pick_up(self) -> list[str]:
        room = self.world.get(self.player.pos)
        if not room or not room.item:
            return ["nothing to pick up"]
        self.player.inventory.append(room.item)
        msg = f"picked up {room.item.name}"
        room.item = None
        return [msg]


# Demo
if __name__ == '__main__':
    g = Game(player_name='Hero')
    print('\n'.join(g.look()))
    print('\n'.join(g.move('north')))
    print(f"State: {g.state}, Player: HP={g.player.hp}/{g.player.max_hp}, LV={g.player.level}, GOLD={g.player.gold}")
```

## 设计亮点

1. **状态机**：`GameState` enum 控制主循环走向
2. **实体职责清晰**：Player（数据 + 操作）、Monster（被动数据）、World（地图）、BattleEngine（行为）
3. **扩展点**：
   - 新 monster 类型：加 template 即可
   - 新 item effect：在 `Player.use_item` 加分支或用策略模式
   - 多 player：World 持 `players: dict[id, Player]`，回合机制扩展

## 复杂度

- 单 turn / move / battle round 都是 O(1)
- 整局游戏 turn 数 N → 总 O(N)

## 易错点

> [!pitfall]
> ❌ 一个超大 God class 把所有逻辑塞进 Game —— 难扩展难测；
> ❌ Monster / Player 用相同 class（"都是 character"） —— 强行抽象，不如分开；
> ❌ 把战斗状态写在 Player 上（"is_in_battle"）—— 状态泄漏；引擎 method 接收 player 引用，battle 状态在 engine 局部；
> ❌ 没考虑 player.alive 为 false 后还在跑循环。

> [!key]
> OOP 题不要写完美游戏；要展示**清晰职责划分 + 可扩展接口 + 一个 demo main**。先把"创建 player → look → move → battle → game over"这一条主路径写跑通，再加 inventory / 升级 / 道具。

> [!followup]
> "怎么加保存/读档？" → 把整个 Game 状态序列化（dataclass → json / pickle）。"如何加 PvP？" → World 加 `players: dict`，turn order 调度。"如何加 ECS（Entity Component System）架构？" → 实体只有 id，行为 / 数据分开存 component table —— 适合大型游戏，面试不展开。
