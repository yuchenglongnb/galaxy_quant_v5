# Reference 资料库

本目录保存历史设计、专题调研和迁移前的细分文档。日常阅读优先看 `docs/` 根目录下的主文档。

## 文件说明

| 文件 | 说明 |
|---|---|
| `ARCHITECTURE.md` | 旧版整体架构文档，内容已收敛进 `../TECHNICAL_DESIGN.md` |
| `INDICATOR_DESIGN.md` | 旧版指标设计细节，内容已收敛进 `../FACTOR_BACKTESTING.md` |
| `BACKTESTING_VALIDATION.md` | 旧版回测验证专题，内容已收敛进 `../FACTOR_BACKTESTING.md` |
| `DATA_API_GUIDE.md` | AmazingData 接口细节，主线说明已收敛进 `../DATA_LAYER.md` |
| `DATA_UNIVERSE_STRATEGY.md` | 数据范围与同步策略旧专题，主线说明已收敛进 `../DATA_LAYER.md` |
| `QSTOCK_RESEARCH.md` | qstock 调研记录，作为辅助数据源参考保留 |
| `AI_REPORTING_DESIGN.md` | AI 报告设计旧专题，主线说明已收敛进 `../AI_LAYER.md` |
| `AI_HARD_CODE_EVOLUTION.md` | AI 替代硬编码研判旧专题，主线说明已收敛进 `../AI_LAYER.md` |
| `INTRADAY_MONITORING.md` | 盘中监测旧专题，主线说明已收敛进 `../OPERATIONS.md` |

## 使用原则

- 主流程、架构和日常操作看根目录主文档。
- 需要追溯设计背景、接口细节或调研记录时再看本目录。
- 新增文档优先更新主文档；只有长篇调研或历史资料才放入 `reference/`。
