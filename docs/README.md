# GalaxyQuant 文档目录

文档已经收敛成“主文档 + reference + legacy”三层。

## 主文档

建议按这个顺序阅读：

1. [技术设计总览](TECHNICAL_DESIGN.md)  
   项目目标、总体架构、核心链路、数据落盘和配置入口。

2. [数据层](DATA_LAYER.md)  
   AmazingData 主链路、自选股池、ETF/指数、同花顺概念、qstock 定位和同步策略。

3. [因子设计与验证框架](FACTOR_BACKTESTING.md)  
   CP风险、反核机会、趋势机会、验证口径、每日因子快照和调参方法。

4. [AI 优化层](AI_LAYER.md)  
   AI 报告、硬编码替代、本地兜底、RAG/Skill 和模型调用边界。

5. [操作手册](OPERATIONS.md)  
   常用命令、日志目录、盘中监测、验证输出和常见排障。

6. [T+1 交易回测层](T1_BACKTESTING.md)
   A股 T+1 可实现收益、入场代理、分钟快照确认和输出字段。

## 资料库

`reference/` 保存历史设计、专题调研和更细的实现说明，日常不需要优先阅读。

已归档内容：

- 原指标设计
- 原数据接口指南
- 原 AI 设计文档
- qstock 调研
- 盘中监测旧专题
- 回测验证旧专题

## 旧资料

`legacy/` 保存更早版本的文档和 AmazingData 原始开发手册，主要用于追溯。

## 当前工程约定

- 日常同步优先使用：`python main.py sync 5`
- 竞价复盘使用：`python main.py auction`
- 盘后复盘使用：`python main.py review`
- 盘中监测使用：`python main.py monitor --summary`
- T+1 回测使用：`python main.py t1backtest 20260310 20260529`
- 分钟数据只在明确需要时拉取：`python main.py sync 5 --minute=auction`
- CP/SA 阈值在 `config/settings.py` 的 `AuctionConfig` 中配置。
- 日志写入 `logs/`。
- 验证和因子快照写入 `reports/validation/`。
