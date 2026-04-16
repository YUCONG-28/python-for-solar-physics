好，我们从**Step 5 开始重做一遍，而且完全贴合你现在的输入方式**👇

```python
selected_bands: List[str] = field(
    default_factory=lambda: [
        "149MHz","164MHz","190MHz","223MHz",
        "238MHz","300MHz","309MHz","324MHz",
    ]
)
```

👉 目标：**不改你原结构，只在关键点插入升级代码**

---

# 🚀 Step 5（重做）：主循环怎么改（最关键）

## ❌ 你现在大概率是这样：

```python
for band in selected_bands:
    radio_data = ...
    ra_map = ...
    dec_map = ...

    result = reproject_radio_to_aia(...)
```

---

## ✅ 改成👇（逐行解释版）

```python
results = {}
heights = {}

for band in selected_bands:

    # ① 解析频率（字符串 → 数值）
    freq = float(band.replace("MHz", ""))

    # ② 计算高度
    height = freq_to_height(freq)

    if cfg.debug_mode:
        print(f"[{band}] → {height:.3f} Rsun")

    # ③ 读取你的原数据（保持你原逻辑）
    radio_data = radio_data_dict[band]
    ra_map = ra_map_dict[band]
    dec_map = dec_map_dict[band]

    # ④ 调用新投影（核心变化）
    proj = reproject_radio_with_height(
        radio_data,
        ra_map,
        dec_map,
        aia_map,
        cfg,
        height_rsun=height
    )

    # ⑤ 保存
    results[band] = proj
    heights[band] = height
```

---

# 🚀 Step 6（必须）：频率排序

👉 这一点**非常重要（不然颜色和物理顺序会乱）**

在 Step 5 前加👇

```python
selected_bands = sorted(
    selected_bands,
    key=lambda x: float(x.replace("MHz", "")),
    reverse=True   # 高频 → 低频
)
```

---

# 🚀 Step 7：绘图（改你的原绘图代码）

---

## ❌ 原来（示意）

```python
plt.imshow(radio_img)
```

---

## ✅ 改成多频叠加👇

```python
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.cm as cm

plt.figure(figsize=(6,6))

# ① AIA背景
plt.imshow(aia_map.data, origin="lower", cmap="gray")

# ② 构造颜色（按频率渐变）
freqs = np.array([float(b.replace("MHz","")) for b in selected_bands])

norm = (freqs - freqs.min()) / (freqs.max() - freqs.min())
colors = cm.jet(norm)

# ③ 逐频画等值线
for i, band in enumerate(selected_bands):

    img = results[band]
    if img is None:
        continue

    # ⚠️ 统一强度标准（关键）
    level = np.nanpercentile(img, 95)

    plt.contour(
        img,
        levels=[level],
        colors=[colors[i]],
        linewidths=1.5,
    )

plt.title("Radio sources with height projection")
plt.show()
```

---

# 🚀 Step 8：提取轨迹（新增）

👉 在绘图之后加👇

```python
def get_centroid(img):
    y, x = np.indices(img.shape)
    mask = np.isfinite(img)

    if np.sum(mask) == 0:
        return None

    w = img[mask]
    x_c = np.sum(x[mask] * w) / np.sum(w)
    y_c = np.sum(y[mask] * w) / np.sum(w)

    return x_c, y_c
```

---

## ✔ 提取轨迹点

```python
trajectory = []

for band in selected_bands:

    img = results[band]
    if img is None:
        continue

    c = get_centroid(img)
    if c is None:
        continue

    trajectory.append((band, c[0], c[1]))
```

---

# 🚀 Step 9：画轨迹线（强烈建议）

👉 在绘图中加👇

```python
xs = [t[1] for t in trajectory]
ys = [t[2] for t in trajectory]

plt.plot(xs, ys, "w--", linewidth=2)
```

---

# 🚀 Step 10（可选但很强）：标注频率

```python
for band, x, y in trajectory:
    plt.text(x, y, band, color="white", fontsize=8)
```

---

# 🎯 最终效果（你应该看到）

一张图：

* 灰色背景：AIA
* 彩色等值线：不同频率
* 白色虚线：射电源轨迹

---

# 🔥 你现在完成的升级

从：

```text
单频射电叠加
```

变成：

```text
多频率 → 高度 → 三维结构 → 空间轨迹
```

---

# ⚠️ 三个关键检查（很容易踩坑）

---

## ❗ 1. band key 必须一致

```python
radio_data_dict["149MHz"]   ✔
```

不能：

```python
radio_data_dict[149]        ❌
```

---

## ❗ 2. ra_map 范围

```python
print(np.nanmin(ra_map), np.nanmax(ra_map))
```

👉 必须：

```text
~ -1 到 1
```

---

## ❗ 3. AIA必须有WCS

```python
aia_map.wcs
```

不能为空

---

# 🌟 一句话总结

> 从 Step 5 开始你做的核心事情是：
> **把每个频段赋予一个“高度”，再统一投影到AIA上形成空间结构**

---

# 🚀 如果你下一步继续（推荐）

我可以带你直接升级到：

👉 **自动拟合射电传播方向 + 速度（论文核心结果）**

只需要在你现在这套基础上再加一层分析就行 👍
