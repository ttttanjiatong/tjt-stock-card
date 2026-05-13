# 📊 A-Share Fundamental Card / A 股基本面速览卡片

> **5 分钟看懂一只票的基本面；多只票横向对比；LLM 生成可审计的多空观点。**
> 5-minute fundamental snapshot for A-share stocks · multi-stock side-by-side comparison · LLM-generated bull/bear views with data-backed evidence.

<p align="center">
  <a href="#中文">🇨🇳 中文</a> ·
  <a href="#english">🇬🇧 English</a>
</p>

---

## 中文

### ✨ 项目特色

- **双模式 UI** — 单股精读（7 模块卡片）+ 多股仪表盘对比（最多 4 只票）
- **规则提取异常 + AI 做归纳** — 5 条投研规则先识别财务异常，LLM 仅在异常上归纳，降低自由发挥
- **数据证据表** — 每条 AI 观点强制绑定 `{indicator, value, period, source}` 结构化证据，可审计可校验
- **双 Agent LLM-as-a-Judge 评估** — Executor (Kimi K2.6) ✕ Evaluator (GLM-5.1) 异厂模型，避开自评偏置
- **双层缓存** — `st.cache_data` (内存) + `joblib.Memory` (磁盘)，热接口 200× 加速
- **不输出投资建议** — 合规边界刻意收窄

### 🎯 评估硬指标

10 只行业代表性样本上的 LLM 输出质量评分（v2 prompt）：

| 维度 | 分数 |
|---|---|
| 数据引用准确率 | **89.6** |
| 关键逻辑覆盖率 | **81.6** |
| 无效观点比例（高分=空话少） | **91.2** |

通过一轮 prompt 迭代，数据引用准确率从 **78.3 → 95.0**（同 3 样本严格对比）。

### 🚀 快速开始

```bash
git clone https://github.com/ttttanjiatong/tjt-stock-card.git
cd tjt-stock-card

python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                       # macOS / Linux

pip install -r requirements.txt
cp .env.example .env                              # 填入方舟 API Key
streamlit run app.py
```

浏览器打开 http://localhost:8501，左侧 sidebar 切换单股 / 多股模式。

### 🧰 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Streamlit + Plotly |
| 数据 | [akshare](https://github.com/akfamily/akshare)（新浪 / 交易所 / 申万 / 巨潮 / 同花顺） |
| LLM | [火山方舟 Coding Plan](https://www.volcengine.com/product/ark)（Anthropic SDK 兼容） |
| 评估 | LLM-as-a-Judge 双 Agent pipeline |
| 缓存 | `st.cache_data` + `joblib.Memory` 双层 |

### 📐 单股 7 模块

① 基本面快照 · ② 主营业务 · ③ 近 1 年股价 · ④ 5 年财务趋势 · ⑤ 同业分位 · ⑥ 财务排雷信号 · ⑦ AI 多空观点

### 🔬 多股对比 5 区块

① 关键指标对比表（热力色编码）· ② 财务趋势叠加 · ③ 股价归一化叠加 · ④ 排雷信号并排 · ⑤ AI 综合横评

### 📂 主要目录

```
modules/        9 个业务模块（单股 + 多股 + 数据层）
prompts/        Executor & Evaluator system prompts
evaluation/     双 Agent 评估 pipeline + 10 只样本集 + CLI 对比工具
scripts/        缓存清理 / 性能 bench
```

### ⚖️ 免责声明

本工具仅用于投研信息聚合与学习研究，**不提供任何投资建议**。所有投资决策应基于个人独立判断。

---

## English

### ✨ Highlights

- **Dual-mode UI** — Single-stock deep dive (7 module cards) + multi-stock comparison dashboard (up to 4 tickers)
- **Rule-based anomaly detection + LLM induction** — 5 forensic accounting rules identify red flags first, then the LLM synthesizes findings only on detected anomalies, minimizing hallucination
- **Data evidence binding** — Every LLM-generated view must cite `{indicator, value, period, source}`, making "data reference accuracy" a machine-verifiable metric
- **Cross-vendor LLM-as-a-Judge evaluation** — Executor (Kimi K2.6) ✕ Evaluator (GLM-5.1) avoid same-family self-evaluation bias
- **Two-layer cache** — `st.cache_data` (in-memory) + `joblib.Memory` (disk-persisted) for 200× speedup on hot reads
- **No investment advice** — Deliberate compliance boundary

### 🎯 Evaluation Metrics

LLM output quality on 10 industry-representative samples (v2 prompt):

| Metric | Score |
|---|---|
| Data Reference Accuracy | **89.6** |
| Logic Coverage | **81.6** |
| Invalid-Claim Score (higher = less fluff) | **91.2** |

A single prompt iteration lifted **Data Reference Accuracy from 78.3 → 95.0** on the strict 3-sample baseline.

### 🚀 Quick Start

```bash
git clone https://github.com/ttttanjiatong/tjt-stock-card.git
cd tjt-stock-card

python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                       # macOS / Linux

pip install -r requirements.txt
cp .env.example .env                              # Fill in your Ark API key
streamlit run app.py
```

Open http://localhost:8501. Toggle between **Single-stock** and **Multi-stock compare** modes in the sidebar.

### 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + Plotly |
| Data | [akshare](https://github.com/akfamily/akshare) (Sina / Exchanges / Shenwan / Cninfo / 10jqka) |
| LLM | [Volcengine Ark Coding Plan](https://www.volcengine.com/product/ark) (Anthropic SDK compatible) |
| Evaluation | Dual-Agent LLM-as-a-Judge pipeline |
| Caching | `st.cache_data` + `joblib.Memory` two-layer |

### 📐 Single-Stock — 7 Modules

① Snapshot · ② Business Intro · ③ 1-Year Price · ④ 5-Year Trends · ⑤ Peer Percentiles · ⑥ Red Flags · ⑦ AI Bull/Bear

### 🔬 Multi-Stock Compare — 5 Sections

① Key-metrics table (heatmap-colored) · ② Trend overlay · ③ Normalized price overlay · ④ Red-flag side-by-side · ⑤ AI comparative view

### 📂 Project Structure

```
modules/        9 business modules (single + compare + data layer)
prompts/        Executor & Evaluator system prompts
evaluation/     Dual-agent evaluation pipeline + 10-sample set + CLI diff tool
scripts/        Cache utilities, perf benchmarks
```

### ⚖️ Disclaimer

This tool is for research and educational use only. **No investment advice is provided.** All decisions should be made based on independent judgment.
