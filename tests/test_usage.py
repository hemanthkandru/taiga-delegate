from taiga_delegate.usage.tracking import UsageLog


def test_record_and_stats(tmp_path):
    log = UsageLog(str(tmp_path / "usage.jsonl"))
    log.record("alex", "taiga_list_epics", True)
    log.record("alex", "taiga_create_issue", True)
    log.record("alex", "taiga_create_issue", False)
    log.record("full", "mcp_usage_stats", True)

    stats = log.stats()
    assert stats["labels"]["alex"]["total_calls"] == 3
    assert stats["labels"]["alex"]["denied_or_failed"] == 1
    assert stats["labels"]["full"]["total_calls"] == 1
    top = {t["tool"]: t["calls"] for t in stats["labels"]["alex"]["top_tools"]}
    assert top["taiga_create_issue"] == 2


def test_stats_without_log_file(tmp_path):
    log = UsageLog(str(tmp_path / "missing.jsonl"))
    stats = log.stats()
    assert stats["labels"] == {}
    assert "note" in stats


def test_record_never_raises(tmp_path):
    log = UsageLog(str(tmp_path / "no-such-dir" / "usage.jsonl"))
    log.record("alex", "tool", True)  # directory missing — must not raise
    log.record("alex", "tool", True)  # warn-once path


def test_garbage_lines_skipped(tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text('not json\n{"ts":"2026-01-01T00:00:00Z","label":"a","tool":"t","ok":true}\n')
    stats = UsageLog(str(path)).stats()
    assert stats["labels"]["a"]["total_calls"] == 1


def test_unicode_labels_round_trip(tmp_path):
    log = UsageLog(str(tmp_path / "usage.jsonl"))
    log.record("José", "taiga_add_comment", True)
    assert UsageLog(log._path).stats()["labels"]["José"]["total_calls"] == 1


def test_days_window_filters(tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text(
        '{"ts":"2020-01-01T00:00:00Z","label":"a","tool":"t","ok":true}\n'
        '{"ts":"2099-01-01T00:00:00Z","label":"a","tool":"t","ok":true}\n'
    )
    stats = UsageLog(str(path)).stats(days=30)
    assert stats["labels"]["a"]["total_calls"] == 1
