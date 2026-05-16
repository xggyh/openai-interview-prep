## 题目本质

**Implement K-Means Clustering Algorithm** —— 实现 K-means 算法。给一组点 + K，把它们分成 K 个 cluster。**ML System Design 题**（虽然标题 implement 但 Google 通常想看算法 + 分布式 / scale 考虑）。

## 标准 K-means 算法

1. **Init**：随机选 K 个 centroid (or K-means++)
2. **Assign**：每个点分到最近 centroid
3. **Update**：每 cluster 计算 mean，set as new centroid
4. **Repeat** 直到 centroid 不变（converge）

## Python 实现

```python
import numpy as np
from typing import Tuple

def kmeans(X: np.ndarray, k: int, max_iter: int = 100, tol: float = 1e-4) -> Tuple[np.ndarray, np.ndarray]:
    """
    X: (N, D) data points
    k: number of clusters
    Returns: (centroids (k, D), labels (N,))
    """
    N, D = X.shape

    # K-means++ init for better starting centroids
    centroids = [X[np.random.randint(N)]]
    for _ in range(k - 1):
        # 选距离已有 centroid 最远的点
        dist_sq = np.min([np.sum((X - c) ** 2, axis=1) for c in centroids], axis=0)
        probs = dist_sq / dist_sq.sum()
        next_idx = np.random.choice(N, p=probs)
        centroids.append(X[next_idx])
    centroids = np.array(centroids)

    for it in range(max_iter):
        # Assign step
        distances = np.linalg.norm(X[:, None] - centroids[None, :], axis=2)  # (N, K)
        labels = np.argmin(distances, axis=1)

        # Update step
        new_centroids = np.array([
            X[labels == j].mean(axis=0) if (labels == j).sum() > 0 else centroids[j]
            for j in range(k)
        ])

        # Check convergence
        shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids
        if shift < tol:
            break

    return centroids, labels
```

## 复杂度

- 每次 iteration：**O(N × K × D)** 计算距离
- 总：**O(iter × N × K × D)**
- iter 通常 < 100

## 关键技术点

### 1. K-means++ initialization

随机 init 容易收敛到 local optimum。K-means++ 选距离已选 centroid 较远的点 → 减少 bad init。

### 2. Empty cluster

某 iteration 一个 cluster 没分到点（少见但会发生）。Handle：保留旧 centroid 或重选 random。

### 3. Distance metric

Standard 是欧氏距离。也可 cosine（normalize 后用 dot product 当 similarity）。

### 4. K 的选择

How many K? **Elbow method**: 跑多 K，画 inertia (within-cluster sum of distances) vs K，找 "elbow"。或 **silhouette score**。

### 5. Convergence detection

- Centroid shift < threshold
- Or label assignment 不变

## 分布式 K-means（at scale）

数据 1B 点 → single machine 不行。

**Distributed K-means** (Spark MLlib / TensorFlow):

```
1. Partition data across workers
2. Broadcast centroids to all workers
3. Each worker: local assign + local sum + count
4. Reduce: aggregate sums → new centroids
5. Repeat
```

每 iter network O(K × D) (centroid broadcast + sum reduce) → 几乎 free。

### Mini-batch K-means

不全数据每 iter，sample 一小批 update centroid。Faster convergence on large data。

## 易错点

> [!pitfall]
> ❌ 随机 init → bad convergence；用 K-means++；
> ❌ 不 detect empty cluster → centroid 不动；
> ❌ Distance loop 用 Python for → 慢；用 numpy broadcasting；
> ❌ 不 normalize features → 大 scale feature dominate；
> ❌ K 固定不试 elbow → K 错。

> [!key]
> K-means = **iterate (assign + update)** 直到 converge。算法简单，工程难点：(1) init (K-means++)；(2) distributed (partition + broadcast)；(3) K 选择。

> [!followup]
> "K 不知怎么办？" → elbow method 或 BIC；"非凸 cluster shape？" → DBSCAN / Spectral clustering；"流式数据？" → online K-means / mini-batch；"高维 D 大？" → PCA 降维 first。
