import json

from scripts import amazing_0935_query_worker as worker


def test_worker_emits_json_marker(capsys):
    worker.emit({"status": "ok", "rows": []})
    out = capsys.readouterr().out
    assert worker.JSON_BEGIN in out
    assert worker.JSON_END in out
    payload = out.split(worker.JSON_BEGIN, 1)[1].split(worker.JSON_END, 1)[0]
    assert json.loads(payload)["status"] == "ok"


def test_worker_request_does_not_echo_credentials(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_query_snapshot",
        lambda request: [{"code": "000001.SZ", "trade_time": "2026-07-03 09:35:00", "last": 10.0}],
    )
    payload = worker.run({
        "date": "20260703",
        "codes": ["000001.SZ"],
        "mode": "historical-snapshot-query",
        "amazing_local_config": "local_config_path",
    })
    combined = json.dumps(payload, ensure_ascii=False)
    assert payload["status"] == "ok"
    assert "local_config_path" not in combined


def test_worker_structured_error(monkeypatch):
    def boom(_request):
        raise RuntimeError("connection failed")

    monkeypatch.setattr(worker, "_query_min1", boom)
    payload = worker.run({
        "date": "20260703",
        "codes": ["000001.SZ"],
        "mode": "historical-min1-kline",
    })
    assert payload["status"] == "query_failed"
    assert payload["row_count"] == 0
    assert "rows" in payload
