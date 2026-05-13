## 题目本质

设计一个云端 devbox（开发容器）平台：开发者按需创建隔离的开发环境（含预装工具 + 依赖 + IDE），用完即销毁。代表产品：Gitpod、Codespaces、Coder、Replit、OpenAI 内部的 devbox。

这题考的是**容器编排 + 文件系统持久化 + 网络隔离 + 冷启动优化** —— Container-as-a-Service 的核心问题。

## 需求拆解

**功能性：**
- 用户从模板 / 自定义 Dockerfile 创建 workspace
- 5 秒内启动可用（含 VS Code in browser 或 SSH）
- 文件系统持久化（关机不丢代码）
- 端口转发（用户 dev server 通过 HTTPS 域名访问）
- 团队共享 workspace
- 资源配额（CPU / 内存 / 磁盘）

**非功能性：**
- 100k 并发 workspace
- 冷启动 < 5 秒（暖启动 < 1 秒）
- 安全：每个 workspace 强隔离（不能逃逸到宿主或邻居）

## 整体架构

```ascii
       Browser / VSCode
              │
              ▼
       ┌────────────┐
       │   Edge     │  HTTPS + WebSocket
       │   (Envoy)  │   *.devbox.example.com
       └─────┬──────┘
             │  routes by workspace-id (cookie / subdomain)
             ▼
       ┌─────────────────┐
       │  Workspace      │  ◀── starts / stops based on ws activity
       │  Router         │
       └──────┬──────────┘
              │
   ┌──────────┼───────────────────────────────┐
   ▼          ▼                               ▼
┌────────┐ ┌────────┐                  ┌──────────────┐
│ Hot    │ │ Cold   │                  │  Builder     │
│ Pool   │ │ Pool   │                  │  Service     │
│ (idle  │ │ (paused│                  │ (build       │
│  warm) │ │  +     │                  │  image from  │
│        │ │  EBS)  │                  │  Dockerfile) │
└───┬────┘ └───┬────┘                  └──────┬───────┘
    │          │                              │
    ▼          ▼                              ▼
┌──────────────────────────────┐       ┌──────────────┐
│  Kubernetes Cluster          │       │ Container    │
│  (firecracker MicroVM /      │       │ Registry     │
│   gVisor / Kata)             │       │ (ECR)        │
└────────────┬─────────────────┘       └──────────────┘
             │
             ▼
    ┌────────────────┐
    │  Persistent    │  per-user EBS / EFS volume
    │  Workspace FS  │
    └────────────────┘
```

## 核心组件设计

### 1. 冷启动 < 5s 的关键

**Hot pool pre-warming**：预热 N 个空闲容器（最常用的几个模板）放着等命中。用户来了，pool 弹出一个，挂载该用户的 persistent volume，refresh `git pull` 后立即可用。

**Snapshot + restore**：用户停用 workspace 时，**不删除**，做 process snapshot（criu）+ filesystem snapshot（EBS），下次启动 restore 直接进入上次进程状态（编辑器开着、终端历史在），冷启动 < 1 秒。

**Lazy image pull**：用 `Stargz` / `eStargz` 镜像格式，按需 pull layers，不必等整个 Docker image 拉完。

### 2. 文件系统持久化

- 每用户一个 **EBS volume**（10-100 GB），挂载到容器 `/workspace`
- 容器销毁时 detach EBS，下次 attach 到新容器
- 备份：EBS snapshot 每天一次到 S3
- 跨 region 同步：选择性（用户付费功能）

### 3. 网络与端口转发

```
用户 dev server: localhost:3000 (容器内)
    ↓ proxy
edge: https://3000-<workspace-id>.devbox.example.com
```

- Edge proxy 按子域名解析 `{port}-{workspace-id}` → 路由到对应容器
- 默认 private（需登录），可切换为 public（生成 share link）
- WebSocket 透传（编辑器 LSP、HMR）

### 4. 容器隔离

**Firecracker MicroVM**（AWS Lambda / Fly.io 同款）：每个 workspace 是一个轻量虚拟机，启动 < 100 ms，与宿主内核完全隔离。比 Docker 安全得多 —— 容器逃逸不影响其他 workspace。

替代：gVisor（Google）—— 用户态 syscall 拦截，性能稍弱但隔离强。

### 5. 资源管理

- K8s ResourceQuota + LimitRange：CPU/RAM 上限
- 磁盘配额：EBS 直接限定容量
- 网络配额：Linux tc / cilium bandwidth manager
- 闲置检测：30 分钟无 TCP 流量 → 自动 hibernate，释放 RAM/CPU，但保留 EBS

## 数据模型

```python
class Workspace:
    id: UUID
    user_id: UUID
    template_id: str          # 'python', 'node', 'rust', 'custom:dockerfile-sha'
    status: Literal['running','hibernated','starting','failed']
    container_id: str | None
    volume_id: str            # EBS volume
    last_active_at: datetime
    cpu_quota: int
    mem_quota_mb: int
    ports_exposed: list[int]

class Template:
    id: UUID
    name: str
    image: str                # 'gcr.io/devbox/python:3.12'
    pre_installed_tools: list[str]
```

## 取舍 / 权衡

| 决策 | 选择 | 替代 |
|---|---|---|
| 隔离 | Firecracker MicroVM | Docker（够快但不够安全） / 虚拟机（太重） |
| FS | EBS per user | NFS / EFS：高延迟，编辑器卡；S3：不支持 POSIX |
| 编排 | K8s + custom controller | Nomad / 自研：K8s 生态最成熟 |
| 启动延迟 | Hot pool + snapshot restore | 每次冷启动：用户跑不了 |
| Image distribution | Stargz lazy pull | Full pull：1GB 镜像得拉 30 秒 |

> [!key]
> OpenAI 内部其实就有 devbox，所以这题问得很贴 OpenAI infra。重点是冷启动 5s 怎么达到 —— 答：(1) hot pool 预热；(2) image lazy pull；(3) snapshot restore；(4) MicroVM 启动毫秒级。

> [!pitfall]
> ❌ 用普通 Docker 直接给所有用户（容器逃逸风险）；
> ❌ 文件系统用 NFS（编辑器会因为 fsync 卡死）；
> ❌ 不做 idle 回收（24h 闲置 workspace 烧钱）；
> ❌ 把所有 workspace 调度到同一个 K8s namespace（quota 失效）。

> [!followup]
> "如何支持团队共享 workspace？" → branch-and-fork 模型，base workspace + per-user 增量 overlay。"GPU workspace？" → 拆 GPU pool，scheduler 按 affinity 调度。"网络拓扑要不要 service mesh？" → 不需要，devbox 之间不互通；只需 user → workspace 单向。
