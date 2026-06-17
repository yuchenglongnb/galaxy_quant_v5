# iFinD MCP Integration

## 目标

把 iFinD MCP 作为 GalaxyQuant 的题材/板块补充层，而不是主行情链路。

当前定位：

- AmazingData 主链路
  - 日线、竞价、分钟、收盘态复盘
- iFinD MCP 补充链路
  - 股票池所属题材更新
  - 概念板块强度快照
  - 公告/新闻催化补证

这样做的原因很简单：

- MCP 调用有配额和上下文限制
- 题材映射和催化补证更适合 MCP
- 全量历史行情同步仍应留在 AmazingData

## 本地落地结构

```text
watchlists/
  stock_pool.csv
  stock_pool_ifind_overlay.csv

AmazingData_Store/YYYYMMDD/ifind/
  stock_theme_snapshot.csv
  stock_theme_exposure.csv
  sector_strength_snapshot.csv
  catalyst_notice_digest.csv
```

说明：

- `stock_pool.csv` 是原始股票池
- `stock_pool_ifind_overlay.csv` 是 iFinD 叠加层，不直接覆盖原始股票池
- `AmazingData_Store/YYYYMMDD/ifind/` 保存按日期归档的 iFinD snapshot

## 三步接入法

### 1. 板块映射层

目标：更新股票池的所属题材、概念和更细粒度行业表达。

当前字段：

- `ifind_ths_industry`
- `ifind_sw_industry`
- `ifind_concepts`
- `ifind_signal_concepts`

其中：

- `ifind_concepts` 保留原始概念
- `ifind_signal_concepts` 过滤掉宽泛、指数化、事件化、一次性噪声概念

过滤逻辑复用：

- `ConceptConfig.THS_EXCLUDE_EXACT`
- `ConceptConfig.THS_EXCLUDE_KEYWORDS`
- `ConceptConfig.THS_EXCLUDE_REGEX`

### 2. 主线簇强度层

目标：不要只知道“股票属于什么题材”，还要知道“题材最近是不是主线”。

当前落地文件：

- `sector_strength_snapshot.csv`

建议核心字段：

- `concept`
- `sector_code`
- `latest_date`
- `amount_yuan`
- `member_count`
- `avg_return_pct`

后续可直接用于：

- leading cluster 识别
- CP leading_cluster 豁免
- 趋势三重过滤的第三层

### 3. 催化验证层

目标：把“板块强”与“为什么强”连接起来，但不把新闻当事实替代行情。

当前落地文件：

- `catalyst_notice_digest.csv`

建议用途：

- 给盘中/盘后报告补一层催化解释
- 给 `lesson` / `pattern` 提供佐证
- 不能直接替代量价和强弱判断

## 代码入口

### Provider

- [providers/ifind_theme_provider.py](/C:/Users/40857/Desktop/galaxy_quant_v5/providers/ifind_theme_provider.py)

职责：

- 标准化 iFinD snapshot
- 生成 overlay
- 生成题材暴露表
- 生成 merge preview

### Runner

- [runners/ifind.py](/C:/Users/40857/Desktop/galaxy_quant_v5/runners/ifind.py)

### CLI

```powershell
python main.py ifind template
python main.py ifind apply-snapshot --input=PATH --date=YYYYMMDD
python main.py ifind exposure --input=PATH --date=YYYYMMDD
python main.py ifind merge-preview
```

注意：

- `ifind` 命令不直接调用 MCP
- MCP 查询发生在 Codex 会话中
- 仓库只消费落盘后的 snapshot CSV

## 现在这版的边界

当前已经完成：

1. iFinD overlay 本地结构
2. 股票池题材补充字段
3. 概念暴露汇总
4. 板块强度 snapshot 样本
5. 催化公告 digest 样本

当前还没做：

1. 自动批量把全股票池都更新完
2. 把 `ifind_signal_concepts` 正式接进 shortlist 排序
3. 把 `sector_strength_snapshot.csv` 反哺到 `leading_cluster` 评分
4. 把催化摘要接进竞价/复盘正文

## 下一步建议

优先顺序：

1. 用 MCP 分批补全 `stock_pool_ifind_overlay.csv`
2. 把 `ifind_signal_concepts` 接到趋势候选和 CP 豁免
3. 把 `sector_strength_snapshot.csv` 接到 `leading_cluster_strength`
4. 让 `catalyst_notice_digest.csv` 进入盘后 explanation 层

## Overlay Governance

- 原始 iFinD snapshot 和 merge preview 默认视为本地生成物，不直接提交 Git。
- 题材字段先走统一适配层，再进入策略逻辑。

```text
iFinD overlay
-> leading_cluster_evidence
-> CP / trend / reversal 共享使用
```

- shortlist 规则不要直接依赖原始 `ifind_signal_concepts`。
