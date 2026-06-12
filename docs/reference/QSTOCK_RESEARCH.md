# qstock 调研与接入建议

调研日期：2026-05-26

## 结论

qstock 可以加入 GalaxyQuant，但更适合作为“辅助数据源”和“概念/热点补充源”，不建议替代当前 AmazingData 主链路。

推荐接入顺序：

1. 概念板块与热点观察：用于补足传统行业指数和 ETF 覆盖不到的题材表达。
2. 实时行情降级源：AmazingData 分钟接口慢或失败时，用 qstock 获取股票池、ETF、指数的实时快照。
3. 问财/技术选股：用于生成候选股票池，再写入 `watchlists/stock_pool.csv`。
4. 历史 K 线交叉校验：用于少量标的的数据校验，不作为全量同步主源。

## 能力范围

根据官方 GitHub README 和 PyPI 页面，qstock 包括：

- 数据获取模块：公开数据源包括东方财富、同花顺、新浪财经等。
- 可视化模块：基于 Plotly Express 和 pyecharts。
- 选股模块：同花顺技术选股、RPS、MM 趋势、财务指标、资金流模型等。
- 回测模块：pandas 向量化和事件驱动框架。

PyPI 当前显示最新版本为 `1.3.8`，发布时间为 `2025-03-16`。

## 对当前项目最有价值的接口

### 1. `realtime_data`

用途：

- 获取指定市场的实时行情。
- 支持股票、ETF、指数、行业板块、概念板块等市场入口。
- 支持单个或多个 `code` 查询。

适合接入：

- `qstock.realtime_data(code=[...])` 作为股票池/ETF/指数快照补充。
- `qstock.realtime_data('ETF')` 用于发现可替换或新增的主题 ETF。
- `qstock.realtime_data('概念板块')` 用于热点题材排序。

不适合：

- 作为竞价成交额的唯一口径。实时快照字段和 AmazingData 的 auction/minute 口径需要对齐验证。

### 2. `intraday_data`

用途：

- 获取股票、基金等最新交易日的日内成交数据。

适合接入：

- 对少量股票池标的做盘中成交明细补充。
- 当 AmazingData 分钟 K 卡住时，作为单标的排查工具。

不适合：

- 全市场分钟数据同步。

### 3. `stock_snapshot`

用途：

- 获取沪深市场股票最新行情快照。

适合接入：

- 对单只核心标的做快速诊断。
- 作为实时监控中“单标的详情”的备用数据。

### 4. `realtime_change`

用途：

- 获取盘口异动，例如火箭发射、快速反弹、竞价上涨、竞价下跌、高开 5 日线、低开 5 日线等。

适合接入：

- 盘中 monitor 增加“异动事件流”。
- 作为 AI 报告的事件证据输入。

### 5. `get_data` / `get_price`

用途：

- 获取股票、基金、债券、期货、指数的历史 K 线或价格矩阵。
- 频率支持日、周、月和 1/5/15/30/60 分钟；官方 README 说明 1 分钟数据只能获取最近 5 个交易日。

适合接入：

- 小范围校验 ETF/指数/股票池历史数据。
- 在 AmazingData 某日缺失时临时补洞。

不适合：

- 长期维护全市场 1 分钟数据库。

### 6. `wencai`

用途：

- 通过自然语言条件调用问财选股。

接入注意：

- README 提到需要升级 `pywencai`，并安装 Node.js 与 `jsdom`。
- 依赖更重，稳定性受网页侧变化影响。

适合接入：

- 离线或手动刷新股票池，例如“近 20 日创新高且成交额放大”等。
- 不建议放到每日核心同步链路。

## 接入架构建议

新增适配器：

```text
providers/
  qstock_provider.py
```

保持和现有 `DataManager` 解耦：

```text
DataManager / AmazingData 主链路
  -> 日线、竞价、分钟、指数 ETF 缓存

QStockProvider 辅助链路
  -> 概念板块
  -> 实时行情降级
  -> 异动事件
  -> 问财股票池候选
```

推荐输出到单独目录：

```text
AmazingData_Store/YYYYMMDD/qstock/
  concept_realtime.csv
  realtime_snapshot.csv
  realtime_change.csv
  wencai_candidates.csv
```

这样可以避免 qstock 字段口径污染现有 `stocks.csv`、`indices.csv`。

## 和当前项目的对应关系

| 当前需求 | qstock 价值 | 建议 |
| --- | --- | --- |
| 板块表达不贴近热点 | 概念板块、资金流、问财 | 高优先级接入 |
| 分钟接口慢 | 实时快照、日内成交 | 作为降级源 |
| 股票池维护 | 问财选股、技术选股 | 生成候选，人工确认后入池 |
| AI 报告证据 | 概念强弱、异动事件 | 作为 RAG/feature 输入 |
| 全量历史数据库 | 有历史 K 线接口 | 不建议替代 AmazingData |

## 风险

- qstock 依赖公开网页数据源，字段和接口可能随网页变化。
- 问财能力依赖 `pywencai`、Node.js、`jsdom`，部署复杂度高于普通 Python 包。
- 部分策略选股和回测功能官方说明只向知识星球会员提供离线包，不应作为开源主链路依赖。
- 历史分钟数据范围有限，不适合承担全量分钟数据库角色。

## 2026-05-26 本地诊断记录

qstock 已在 `amazing` 环境安装成功，但第一次拉取概念行情失败。排查结论：

- `HTTP_PROXY/HTTPS_PROXY` 指向 `127.0.0.1:7897`，qstock/requests 默认会继承该代理。
- Windows 用户代理也开启了 `127.0.0.1:7897`。
- `push2.eastmoney.com:443` 端口在沙箱外可连通。
- `curl --noproxy "*" -4` 访问东方财富 API 成功。
- `curl --noproxy "*" -6` 访问同一 API 会被远端断开。
- Python `requests` 清空代理后访问同一 API 仍被远端断开，表现为 `RemoteDisconnected`。
- qstock 导入阶段会调用 `latest_trade_date()`，进而访问东方财富 `push2.eastmoney.com`，因此在 import 阶段就失败。

因此当前失败不是“qstock 未安装”，也不是项目适配器入口错误，而是 qstock 依赖的公开网页接口在当前网络/TLS/Python requests 组合下不可用。已在 `providers/qstock_provider.py` 中增加：

- qstock 任务默认绕过代理环境变量。
- 尝试限制 qstock 任务走 IPv4。
- 对 qstock 初始化失败给出更准确提示。

如果后续仍需要稳定接入，可以考虑两条路线：

1. 继续使用 qstock，但在本机网络层解决东方财富 API 对 Python requests 的断开问题。
2. 不依赖 qstock import，单独实现轻量 Provider，用可工作的 HTTP 栈或离线 CSV 导入同花顺/东方财富概念数据。

当前已实现第 2 条路线：`providers/ths_concept_provider.py` 会直接访问同花顺概念接口，不再 `import qstock`，因此不会触发 qstock 导入阶段的东方财富请求。

可用命令：

```powershell
python main.py qstock concept
python main.py qstock map --limit=50
python main.py qstock money --n=5
python main.py qstock concept-index --top=10 --start-year=2026
python main.py qstock concept-index --concept=AI应用 --start-year=2026
```

落盘目录：

```text
AmazingData_Store/YYYYMMDD/ths/
  concept_list.csv
  concept_money_5d.csv
  stock_concept_map.csv
  stock_concept_exposure.csv
  concept_index_exposed.csv
  concept_index_<概念名>.csv
```

2026-05-26 试跑结果：

- `concept_list.csv`: 50 条同花顺概念。
- `concept_money_5d.csv`: 387 条概念资金流。
- `stock_concept_map.csv`: 55 条股票池-概念映射。
- `stock_concept_exposure.csv`: 31 条股票池概念暴露。
- `concept_index_exposed.csv`: 暴露度前 10 概念的 2026 年指数日线，共 852 条。

已观察到的股票池暴露示例：

| 概念 | 覆盖股票数 | 覆盖股票 |
| --- | ---: | --- |
| 中国AI 50 | 5 | 中国移动, 中际旭创, 海光信息, 瑞芯微, 科大讯飞 |
| 同花顺新质50 | 5 | 三花智控, 中际旭创, 天孚通信, 寒武纪, 通富微电 |
| 同花顺出海50 | 4 | 沪电股份, 洛阳钼业, 紫金矿业, 胜宏科技 |

AmazingData TGW 失败也做了复核：

- 在默认沙箱内运行 `main.py auction 20260526` 会 TGW 登录超时。
- 沙箱外测试 `101.230.159.234:8600` 和 `140.206.44.234:8600` 均可连通。
- 沙箱外运行 `main.py auction 20260526` 登录成功并完成回测。

因此 TGW 超时主要来自 Codex 沙箱网络限制，不是 AmazingData 账号或服务不可用。

## 建议的第一版接入

第一版只做“只读辅助源”。当前已经按这个方向新增：

```text
providers/
  qstock_provider.py      # qstock 适配器，只写 side cache
runners/
  qstock.py               # CLI 运行器
```

命令入口：

```powershell
python main.py qstock concept              # 概念板块实时行情
python main.py qstock money --n=5          # 同花顺概念资金流
python main.py qstock map --limit=50       # 股票池映射到同花顺概念，limit 用于试跑
python main.py qstock realtime             # 股票池实时快照
python main.py qstock change --flag=竞价上涨
python main.py qstock all
```

输出目录：

```text
AmazingData_Store/YYYYMMDD/qstock/
  concept_realtime.csv
  concept_money_5d.csv
  stock_pool_realtime.csv
  realtime_change_*.csv
  stock_concept_map.csv
  stock_concept_exposure.csv
```

### 自选股归类到同花顺概念

qstock 的公开接口是“概念 -> 成分股”，不是“个股 -> 概念”。因此当前实现采用反向扫描：

1. 读取 `watchlists/stock_pool.csv`。
2. 调用 `ths_index_name('概念')` 获取同花顺概念列表。
3. 逐个概念调用 `ths_index_member(concept)` 获取成分。
4. 和股票池代码取交集。
5. 输出：
   - `stock_concept_map.csv`: 每只股票属于哪些概念。
   - `stock_concept_exposure.csv`: 每个概念覆盖股票池多少只股票。

第一次全量扫描可能较慢，也可能受同花顺网页接口稳定性影响。建议先试跑：

```powershell
python main.py qstock map --limit=50
```

确认字段稳定后，再去掉 `--limit` 全量生成。

### ETF/指数/概念行情的合并方式

不建议把同花顺概念行情直接写入 `indices.csv`，原因是：

- `indices.csv` 当前是 AmazingData 主指数 + ETF 日线口径。
- qstock 概念行情来自同花顺/东方财富网页源，字段、更新时间、复权和成交额口径都不同。
- 直接混写会让回测和复盘难以追溯。

推荐在报告层合并展示：

```text
指数环境：indices.csv
ETF主题：indices.csv 中的 THEME_ETFS
同花顺概念：qstock/concept_realtime.csv + concept_money_5d.csv
股票池概念暴露：qstock/stock_concept_exposure.csv
```

最终报告可以新增：

```text
【同花顺概念热点】
概念名称 | 涨幅 | 资金流 | 股票池覆盖数 | 覆盖个股

【股票池概念暴露】
概念名称 | 覆盖数量 | 涨幅 | 资金流 | 代表个股
```

这样 ETF、指数、概念都能参与“市场方向/题材方向”的判断，但底层来源清楚、可复盘。

### 预期效果

- 股票池从单纯的自定义分组，升级为“自定义分组 + 同花顺概念标签”。
- 报告可以识别“股票池集中暴露在哪些热点概念”。
- ETF 表达较粗时，概念板块可以提供更细粒度题材温度。
- qstock 实时快照和异动事件可作为 AmazingData 分钟接口慢时的旁路证据。
- AI/RAG 报告可以把概念行情、资金流、异动事件作为证据输入，减少硬编码结论。

### 依赖安装

qstock 是可选依赖，未安装时主链路不受影响。需要启用时再安装：

```powershell
pip install qstock
```

如果使用问财相关能力，还需要根据 qstock README 安装/升级 `pywencai`，并准备 Node.js 与 `jsdom`。建议问财单独做离线股票池候选，不放入日常核心同步。

后续增强：

- 把 `stock_concept_exposure.csv` 接入竞价报告。
- 将 `concept_realtime.csv` 和 `concept_money_5d.csv` 合并成概念热点评分。
- 用 `realtime_change` 生成盘中事件流，接入 `monitor`。
- 增加 `wencai_candidates.csv`，作为股票池候选，不自动覆盖正式股票池。

这个方式风险较低，也最符合当前项目“可复盘、可缓存、可降级”的方向。

## 参考来源

- GitHub: https://github.com/tkfy920/qstock
- PyPI: https://pypi.org/project/qstock/
