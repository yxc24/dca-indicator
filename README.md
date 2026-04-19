# DCA Indicator

美股定投择时预警器。开盘到收盘后 1 小时每小时监测一次，通过 Feishu 机器人推送买点信号。

## 监测指标

| 指标 | 触发条件 | 权重 |
|---|---|---|
| VIX | > 25 | 2 |
| SPY 当日跌幅 | < -2% | 2 |
| SPY 相对当日最高价 | < -1.5% | 1 |
| SPY RSI-14 (前日收盘) | < 30 | 1 |
| SPY MTD 回撤 (前日收盘) | < -3% | 1 |
| SPY 52 周高点距离 | < -10% | 1 |
| CNN Fear & Greed | < 25 | 1 |

**盘中阈值**：总分 ≥ 3 发送信号  
**收盘后 (美东 17:05)**：总分 ≥ 3 = 关注 / ≥ 4 = 强买点

## 部署

### 1. 注册免费 API key

- **Finnhub**：https://finnhub.io（实时报价 + 历史 K 线）
- **FRED**：https://fred.stlouisfed.org/docs/api/api_key.html（VIX 备份）
- **Feishu 自定义机器人**：群聊 → 设置 → 群机器人 → 添加自定义机器人 → 开启签名校验 → 拿到 webhook URL 和 sign secret

### 2. 创建 GitHub repo 并 push 代码

```bash
cd /Users/yx/Documents/project/dca-indicator
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/dca-indicator.git
git push -u origin main
```

### 3. 配置 GitHub Secrets

在 repo → Settings → Secrets and variables → Actions → New repository secret，添加：

| Secret name | Value |
|---|---|
| `FEISHU_WEBHOOK` | Feishu 机器人 webhook URL |
| `FEISHU_SIGN_SECRET` | Feishu 机器人签名 secret |
| `FINNHUB_API_KEY` | Finnhub API key |
| `FRED_API_KEY` | FRED API key |

### 4. 启用 Actions

repo → Actions → 启用。Workflow 自动在美东 10:05、11:05...17:05（每小时）触发。

### 5. 手动测试

在 Actions 页面选择 `Hourly Stock Alert` → `Run workflow` 即可立即触发一次。

## 本地运行

```bash
# 设置环境变量（可以用 .env 文件）
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FEISHU_SIGN_SECRET="xxx"
export FINNHUB_API_KEY="xxx"
export FRED_API_KEY="xxx"
export RUN_MODE="intraday"   # 或 daily_final

# 安装依赖
pip install -r requirements.txt

# 运行
python -m src.main

# 跑回测
python -m src.backtest --start 2025-01-01 --end 2026-04-01
```

## 目录结构

```
dca-indicator/
├── .github/workflows/
│   ├── hourly-alert.yml       # 每小时触发（主 workflow）
│   └── backtest.yml           # 手动触发回测
├── src/
│   ├── config.py              # 读取 rules.yaml 和环境变量
│   ├── main.py                # 入口：编排流程
│   ├── backtest.py            # 历史回测
│   ├── sources/
│   │   ├── finnhub_src.py     # 实时报价 + K 线
│   │   ├── yfinance_src.py    # VIX 主源
│   │   ├── fred_src.py        # VIX 备份
│   │   └── fgi_src.py         # CNN Fear & Greed
│   ├── indicators/
│   │   ├── rsi.py
│   │   ├── ma.py
│   │   ├── drawdown.py
│   │   └── intraday.py
│   ├── engine/
│   │   ├── scorer.py          # 打分引擎
│   │   ├── cooldown.py        # 冷却去重
│   │   └── market_hours.py    # 市场开闭判断
│   └── notify/
│       ├── feishu.py          # Feishu 卡片发送
│       └── templates.py       # 卡片模板
├── tests/
│   └── test_indicators.py
├── rules.yaml                 # 规则与阈值配置
├── state.json                 # 运行状态（自动 commit）
├── requirements.txt
└── README.md
```

## 常见问题

**Q: 我想调整阈值怎么办？**  
直接改 `rules.yaml`，无需改代码。

**Q: 我想加新标的（如 QQQ、TSLA）？**  
在 `rules.yaml` 的 `targets` 下加一行，会自动为每个标的独立打分。

**Q: 通知被刷屏了怎么办？**  
`rules.yaml` 的 `cooldown.same_score_hours` 调大（默认 4 小时）。

**Q: GitHub Actions 跑失败怎么办？**  
Actions 页面查看日志。Secrets 配错是最常见原因。

**Q: 免费额度会用完吗？**  
每日 8 次 × 30 秒 ≈ 4 分钟；每月约 88 分钟。私有 repo 免费额度 2000 分钟/月，公开 repo 无限。
