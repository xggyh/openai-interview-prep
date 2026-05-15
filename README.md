# Interview Prep

面试题准备库 —— **118 道**真实候选人报告题（来源：hellointerview.com，OpenAI + Google），每题含：
- 原始英文题面 + 报告人数 + 最近问询时间 + 跨公司汇总
- 中文思路解析（System Design 的架构思路，Coding 题的详细分析）
- Python 解法（Coding 题）
- 易错点 & 延伸追问

## 在线浏览

➡️ https://xggyh.github.io/interview-prep/

## 题目分布

| 公司 | 题数 |
|---|---|
| **OpenAI** | 44 题（全岗位） |
| **Google** | 75 题（Coding 前 3 页） |
| 共有 | 1 题（Leetcode 253. Meeting Rooms II） |
| **总计** | 118 题 unique |

| 类型 | 题数 |
|---|---|
| Coding | 94 |
| System Design | 18 |
| People Management | 4 |
| Behavioral | 1 |
| Mobile System Design | 1 |

## 仓库结构

```
.
├── public/                          # 部署到 GitHub Pages 的静态文件
│   ├── index.html                   # 题目列表入口
│   ├── questions/<slug>.html        # 44 个题目详情页
│   └── assets/style.css
├── site/                            # 源文件
│   ├── analyses/<slug>.md           # 每题的中文分析 markdown
│   ├── data/raw/<slug>.json         # 爬取的题目页面数据
│   └── scripts/
│       ├── scrape.py                # 抓取脚本（用 Arc + AppleScript 驱动）
│       └── build.py                 # 静态站点生成
└── openai-interview-questions.json  # 题目元信息
```

## 重新生成

```bash
# 1. 抓取题目详情（需要登录 hellointerview，并用 Arc 浏览器）
python3 site/scripts/scrape.py

# 2. 编辑 site/analyses/*.md 写分析

# 3. 生成静态站点
python3 site/scripts/build.py

# 4. 推送，GitHub Actions 自动部署
git add -A && git commit -m "update" && git push
```

## 致谢

题面 + 时间线数据来自 [hellointerview.com](https://www.hellointerview.com/community/questions?company=OpenAI)。
