## 题目本质

**Monster Fight**：实现一个回合制怪兽战斗系统，怪兽有不同属性（HP / ATK / DEF / SPD）和**技能（不同效果）**。

不是算法题，是 **LLD（低级设计 / OOP）** 题。考点：**类设计 + 策略模式 + 状态管理 + 扩展性**。OpenAI 真实报告 Senior-Staff 级。

## 解题思路

OOP 题面试通用框架：
1. 列**核心实体**（Monster, Skill, Battle, Effect）
2. 列**核心交互**（攻击、技能释放、状态变化）
3. 用**多态 / 策略模式**让"技能"和"效果"可扩展
4. 写一个能跑的 main demo

## Python 实现

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
import random

# ---------- 基础数据 ----------
class StatusEffect(Enum):
    POISON = 'poison'       # 每回合受伤
    STUN = 'stun'           # 本回合无法行动
    BURN = 'burn'           # 每回合受伤 + ATK 降低
    SHIELD = 'shield'       # 减伤

@dataclass
class Status:
    effect: StatusEffect
    remaining_turns: int
    magnitude: int = 0      # 伤害量或减伤量

# ---------- 技能（策略模式）----------
class Skill(ABC):
    def __init__(self, name: str, cost: int = 0):
        self.name = name
        self.cost = cost   # 法力/CD

    @abstractmethod
    def apply(self, caster: 'Monster', target: 'Monster', log: list[str]):
        ...

class BasicAttack(Skill):
    def apply(self, caster, target, log):
        dmg = max(1, caster.atk - target.def_)
        target.take_damage(dmg)
        log.append(f"{caster.name} attacks {target.name} for {dmg}")

class FireBlast(Skill):
    def __init__(self):
        super().__init__(name='Fire Blast', cost=10)
    def apply(self, caster, target, log):
        dmg = caster.atk * 2 - target.def_
        target.take_damage(max(1, dmg))
        target.statuses.append(Status(StatusEffect.BURN, 3, magnitude=5))
        log.append(f"{caster.name} casts Fire Blast: {dmg} dmg + 3-turn burn")

class StunStrike(Skill):
    def __init__(self):
        super().__init__(name='Stun Strike', cost=8)
    def apply(self, caster, target, log):
        target.take_damage(caster.atk // 2)
        target.statuses.append(Status(StatusEffect.STUN, 1))
        log.append(f"{caster.name} uses Stun Strike: stuns {target.name}")

class HealSelf(Skill):
    def __init__(self):
        super().__init__(name='Heal', cost=12)
    def apply(self, caster, target, log):  # target ignored
        amt = caster.max_hp // 4
        caster.hp = min(caster.max_hp, caster.hp + amt)
        log.append(f"{caster.name} heals {amt}")

# ---------- Monster ----------
@dataclass
class Monster:
    name: str
    max_hp: int
    atk: int
    def_: int
    spd: int
    mana: int = 100
    hp: int = field(init=False)
    statuses: list[Status] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)

    def __post_init__(self):
        self.hp = self.max_hp
        # 默认每只都有 basic attack
        self.skills = [BasicAttack('Basic')] + (self.skills or [])

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int):
        # 检查 shield
        shield = next((s for s in self.statuses if s.effect == StatusEffect.SHIELD), None)
        if shield:
            dmg = max(0, dmg - shield.magnitude)
        self.hp = max(0, self.hp - dmg)

    def is_stunned(self) -> bool:
        return any(s.effect == StatusEffect.STUN and s.remaining_turns > 0 for s in self.statuses)

    def tick_statuses(self, log: list[str]):
        """每回合开始：处理 dot（damage over time）+ 倒计时"""
        for s in self.statuses:
            if s.effect == StatusEffect.POISON:
                self.take_damage(s.magnitude)
                log.append(f"{self.name} suffers {s.magnitude} poison damage")
            elif s.effect == StatusEffect.BURN:
                self.take_damage(s.magnitude)
                log.append(f"{self.name} burns for {s.magnitude}")
            s.remaining_turns -= 1
        self.statuses = [s for s in self.statuses if s.remaining_turns > 0]

# ---------- Battle 引擎 ----------
class Battle:
    def __init__(self, a: Monster, b: Monster):
        self.a, self.b = a, b
        self.log: list[str] = []
        self.turn = 0

    def _order(self) -> tuple[Monster, Monster]:
        # spd 高先动；并列时 a 先动
        if self.a.spd >= self.b.spd:
            return self.a, self.b
        return self.b, self.a

    def _choose_skill(self, m: Monster) -> Skill:
        # 简单 AI：能用强技就用；否则 basic
        usable = [s for s in m.skills if s.cost <= m.mana]
        non_basic = [s for s in usable if not isinstance(s, BasicAttack)]
        if non_basic:
            return random.choice(non_basic)
        return m.skills[0]   # basic

    def run(self, max_turns: int = 100) -> str:
        while self.a.is_alive() and self.b.is_alive() and self.turn < max_turns:
            self.turn += 1
            self.log.append(f"--- Turn {self.turn} ---")
            first, second = self._order()
            for actor, foe in [(first, second), (second, first)]:
                if not actor.is_alive() or not foe.is_alive():
                    break
                actor.tick_statuses(self.log)
                if not actor.is_alive():
                    break
                if actor.is_stunned():
                    self.log.append(f"{actor.name} is stunned, skips turn")
                    continue
                skill = self._choose_skill(actor)
                actor.mana -= skill.cost
                skill.apply(actor, foe, self.log)
        if self.a.is_alive() and not self.b.is_alive():
            return self.a.name
        if self.b.is_alive() and not self.a.is_alive():
            return self.b.name
        return 'draw'

# ---------- 示例 ----------
if __name__ == '__main__':
    fireball = FireBlast()
    stun = StunStrike()
    heal = HealSelf()

    ifrit = Monster(name='Ifrit',  max_hp=120, atk=22, def_=10, spd=15, skills=[fireball, heal])
    golem = Monster(name='Golem',  max_hp=180, atk=18, def_=20, spd=8,  skills=[stun])

    b = Battle(ifrit, golem)
    winner = b.run()
    print('\n'.join(b.log))
    print('Winner:', winner)
```

## 设计亮点

1. **Skill 是策略模式（Strategy Pattern）**：新加技能只要写新 class + 实现 `apply()`，引擎不变。
2. **Status / 状态机解耦伤害逻辑**：dot（poison/burn）、stun、shield 都用同一 Status 数据结构，`tick_statuses` 每回合统一处理。
3. **Battle 引擎决定行动顺序 + AI**：分离了 Monster 数据、技能行为、战斗流程。
4. **可扩展点**：装备（equip slot）、被动技能（passive，注册到 hook 如 `on_hit`）、buff/debuff、群体技能（multi-target）。

## 取舍

| 选择 | 理由 |
|---|---|
| Python dataclass + Enum | 简洁，面试 30 分钟内能写完 |
| 简单 random AI | 不是 AI 题，过得去就行 |
| 同步逐回合 | 不引入 async / event loop，简化 |

## 易错点

> [!pitfall]
> ❌ 把所有技能塞在 Monster 类里用 if/elif —— 不可扩展；
> ❌ 状态效果直接改 ATK / DEF —— 难恢复；用 Status 列表 + 计算时减；
> ❌ 没有 max_turns 兜底 —— 死循环（互砍 1 dmg）；
> ❌ tick_statuses 在 take_damage 之前还是之后？答：之前，模拟"回合开始结算"。

> [!key]
> OOP 题不写完美代码，要展示**清晰的边界**：实体 / 行为 / 引擎三层；策略模式让技能可扩展。先写最简单 `BasicAttack` 跑通整个 Battle，再加 status / mana / AI。

> [!followup]
> "如何支持多对多战斗？" → Battle 接受 list[Monster]，行动顺序按 spd 排序，target selection 加一层。"如何 replay 战斗？" → 把每回合 (turn, actor, skill, target, dmg) 记录到 event log，replay 时重放。"如何写单测？" → mock random，断言伤害数值；mock skill，断言调用顺序。
