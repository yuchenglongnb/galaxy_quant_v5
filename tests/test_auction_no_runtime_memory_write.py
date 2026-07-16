import pandas as pd

from runners.auction import AuctionRunner


def test_analysis_review_can_skip_runtime_memory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    runner = AuctionRunner.__new__(AuctionRunner)
    runner._persist_runtime_memory = False
    monkeypatch.setattr(runner, "_build_validation_records", lambda result: [])
    monkeypatch.setattr(runner, "_build_validation_metrics", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(runner, "_build_analysis_payload", lambda *args: {"date": "20260706"})
    monkeypatch.setattr(runner, "_format_analysis_markdown_v2", lambda payload: "# review\n")
    called = []
    monkeypatch.setattr(runner, "_save_analysis_lessons_v2", lambda payload: called.append(payload))

    runner._save_analysis_review({"date": "20260706"})

    assert (tmp_path / "reports/analysis/daily/20260706/auction_review.json").exists()
    assert called == []
    assert not (tmp_path / "reports/analysis/lessons/auction_lessons.jsonl").exists()
    assert not (tmp_path / "reports/analysis/patterns/pattern_progress.json").exists()
