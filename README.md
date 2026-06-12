# galaxy_quant_v5

A local A-share auction, intraday tracking, post-market validation, and strategy replay research project.

## What is included

- Auction analysis and signal generation
- Intraday confirmation and monitoring utilities
- Post-market validation and replay tools
- Methodology, pattern registry, and lesson accumulation
- Local Codex skills for auction-review workflows

## What is not included

Runtime market data, logs, local validation outputs, API keys, and personal raw imports are intentionally ignored by git.

Copy `.env.example` to `.env` or set the corresponding environment variables before running local data sync.

## Main entry

```powershell
python main.py auction
python main.py review
python main.py sync 5
```
