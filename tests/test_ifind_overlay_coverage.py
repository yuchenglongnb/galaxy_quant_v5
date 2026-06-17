# -*- coding: utf-8 -*-

import json
from pathlib import Path
from unittest import mock

import pandas as pd

import scripts.evaluate_ifind_overlay_coverage as coverage_module


class _FakeProvider:
    def load_stock_pool(self):
        return pd.DataFrame(
            [
                {"code": "601138.SH", "name": "工业富联", "group": "消费电子零部件及组装"},
                {"code": "300476.SZ", "name": "胜宏科技", "group": "印制电路板"},
                {"code": "688256.SH", "name": "寒武纪", "group": "数字芯片设计"},
            ]
        )

    def load_overlay(self, path=None):
        return pd.DataFrame(
            [
                {
                    "code": "601138.SH",
                    "name": "工业富联",
                    "ifind_ths_industry": "电子",
                    "ifind_signal_concepts": "人工智能;东数西算(算力)",
                },
                {
                    "code": "300476.SZ",
                    "name": "胜宏科技",
                    "ifind_ths_industry": "电子",
                    "ifind_signal_concepts": "PCB概念;AI手机",
                },
            ]
        )


def test_overlay_coverage_script_generates_stable_json(tmp_path):
    root = Path(tmp_path)
    ifind_dir = root / "AmazingData_Store" / "20260616" / "ifind"
    ifind_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"concept": "AI手机", "avg_return_pct": 7.48, "amount_yuan": 123764700000.0, "member_count": 39},
            {"concept": "PCB概念", "avg_return_pct": 11.94, "amount_yuan": 437398860000.0, "member_count": 220},
        ]
    ).to_csv(ifind_dir / "sector_strength_snapshot.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"code": "601138.SH", "summary": "AI服务器"},
            {"code": "300476.SZ", "summary": "PCB扩产"},
        ]
    ).to_csv(ifind_dir / "catalyst_notice_digest.csv", index=False, encoding="utf-8-sig")

    with (
        mock.patch.object(coverage_module, "ROOT", root),
        mock.patch.object(coverage_module, "IFindThemeProvider", return_value=_FakeProvider()),
    ):
        payload = coverage_module.evaluate(20260616, top_missing=5)
        json_path, md_path = coverage_module.write_outputs(payload)

    assert payload["stock_pool_total"] == 3
    assert payload["ifind_overlay_count"] == 2
    assert payload["ifind_signal_concepts_count"] == 2
    assert payload["sector_strength_cluster_count"] >= 1
    assert payload["catalyst_digest_stock_count"] == 2
    assert payload["suggested_next_batch"][0]["code"] == "688256.SH"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["date"] == "20260616"
    assert md_path.exists()
