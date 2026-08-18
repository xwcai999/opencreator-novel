from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "novel-studio-skill" / "skills" / "wawa-source" / "scripts" / "wawa_snapshot.py"
SPEC = importlib.util.spec_from_file_location("wawa_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WawaSourceTests(unittest.TestCase):
    def snapshot(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "wawa.stats.v1",
            "captured_at": "2026-08-18T12:00:00+08:00",
            "ttl_days": 7,
            "source": {"kind": "synthetic-fixture", "label": "合成测试"},
            "account": {"id": "account-secret", "nickname": "不应公开"},
            "works": [
                {
                    "work_id": "remote-work-001",
                    "title": "真实作品名不应进入公开视图",
                    "author": "真实作者不应进入公开视图",
                    "status": "连载",
                    "metrics": {
                        "chapters": 42,
                        "words": 123456,
                        "followers": 820,
                        "readers": 731,
                        "follow_delta": 18,
                        "total_revenue": 123.45,
                        "daily_revenue": 12.34,
                    },
                    "series": [
                        {"date": "2026-08-17", "followers": 802, "readers": 710, "revenue": 8.2},
                        {"date": "2026-08-18", "followers": 820, "readers": 731, "revenue": 12.34},
                    ],
                },
                {
                    "work_id": "remote-work-002",
                    "title": "第二个合成作品",
                    "status": "完结",
                    "metrics": {"chapters": 10, "words": 5000, "followers": 20, "readers": 15, "total_revenue": 2},
                    "series": [{"date": "2026-08-18", "followers": 20, "readers": 15, "revenue": 2}],
                },
            ],
        }
        value.update(updates)
        return value

    def test_validate_and_aggregate_fresh_snapshot(self) -> None:
        data = self.snapshot()
        report = MODULE.validate_snapshot(data, "2026-08-18T13:00:00+08:00")
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["status"], "fresh")
        aggregate = MODULE.aggregate_snapshot(MODULE.normalize_snapshot(data))
        self.assertEqual(aggregate["work_count"], 2)
        self.assertEqual(aggregate["totals"]["chapters"], 52)
        self.assertEqual(aggregate["totals"]["words"], 128456)
        self.assertEqual(aggregate["totals"]["total_revenue"], 125.45)
        self.assertEqual(aggregate["windows"]["7d"]["points"], 2)
        self.assertEqual(aggregate["windows"]["7d"]["followers_delta"], 38)

    def test_expired_snapshot_is_stale_without_being_invalid(self) -> None:
        expired = self.snapshot(captured_at="2026-08-01T12:00:00+08:00")
        works = expired["works"]
        assert isinstance(works, list)
        for work in works:
            assert isinstance(work, dict)
            work["series"] = []
        report = MODULE.validate_snapshot(
            expired,
            "2026-08-18T12:00:00+08:00",
        )
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["status"], "stale")
        self.assertTrue(report["warnings"])

    def test_invalid_schema_and_negative_metric_fail_closed(self) -> None:
        missing_version = self.snapshot()
        missing_version.pop("schema_version")
        report = MODULE.validate_snapshot(missing_version, "2026-08-18T12:00:00+08:00")
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "invalid")

        invalid_metric = self.snapshot()
        works = invalid_metric["works"]
        assert isinstance(works, list)
        metrics = works[0]["metrics"]
        assert isinstance(metrics, dict)
        metrics["words"] = -1
        report = MODULE.validate_snapshot(invalid_metric, "2026-08-18T12:00:00+08:00")
        self.assertFalse(report["ok"])
        self.assertIn("非负", report["errors"][0])

    def test_redaction_removes_identity_and_keeps_metrics(self) -> None:
        public = MODULE.redact_snapshot(self.snapshot())
        encoded = json.dumps(public, ensure_ascii=False)
        self.assertTrue(public["privacy"]["redacted"])
        self.assertEqual([work["label"] for work in public["works"]], ["作品 1", "作品 2"])
        self.assertNotIn("remote-work-001", encoded)
        self.assertNotIn("真实作品名", encoded)
        self.assertNotIn("account-secret", encoded)
        self.assertEqual(public["works"][0]["metrics"]["words"], 123456)

    def test_load_snapshot_defaults_to_redacted_local_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(self.snapshot(), ensure_ascii=False), encoding="utf-8")
            loaded = MODULE.load_snapshot(path, now="2026-08-18T12:00:00+08:00")
        encoded = json.dumps(loaded, ensure_ascii=False)
        self.assertNotIn("remote-work-001", encoded)
        self.assertEqual(loaded["schema_version"], "wawa.stats.v1")

    def test_missing_metrics_remain_unknown_and_dashboard_contract_matches(self) -> None:
        data = self.snapshot()
        works = data["works"]
        assert isinstance(works, list)
        for work in works:
            assert isinstance(work, dict)
            metrics = work["metrics"]
            assert isinstance(metrics, dict)
            metrics.pop("daily_revenue", None)
            series = work["series"]
            assert isinstance(series, list)
            for point in series:
                assert isinstance(point, dict)
                point.pop("revenue", None)
                point.pop("daily_revenue", None)
        normalised = MODULE.normalize_snapshot(data)
        aggregate = MODULE.aggregate_snapshot(normalised)
        self.assertIsNone(aggregate["totals"]["daily_revenue"])
        dashboard = MODULE.to_dashboard_snapshot(normalised, days=7, now="2026-08-18T13:00:00+08:00")
        self.assertEqual(dashboard["contractVersion"], "1.0.0")
        self.assertEqual(dashboard["status"], "success")
        self.assertIsNone(dashboard["totals"]["dailyRevenue"])
        self.assertNotIn("dailyRevenue", dashboard["availableMetrics"])
        encoded = json.dumps(dashboard, ensure_ascii=False)
        self.assertNotIn("remote-work-001", encoded)

    def test_snapshot_calendar_date_uses_declared_timezone(self) -> None:
        data = self.snapshot(captured_at="2026-08-18T00:30:00+08:00")
        works = data["works"]
        assert isinstance(works, list)
        for work in works:
            assert isinstance(work, dict)
            work["series"] = [{"date": "2026-08-18", "words": 10}]
        normalised = MODULE.normalize_snapshot(data)
        dashboard = MODULE.to_dashboard_snapshot(normalised, days=7, now="2026-08-18T00:45:00+08:00")
        self.assertEqual(dashboard["range"]["to"], "2026-08-18")
        self.assertEqual(dashboard["trend"][0]["date"], "2026-08-18")

    def test_subday_ttl_is_rejected_by_v1_contract(self) -> None:
        data = self.snapshot()
        data.pop("ttl_days")
        data["ttl_hours"] = 12
        report = MODULE.validate_snapshot(data, now="2026-08-18T13:00:00+08:00")
        self.assertFalse(report["ok"])
        self.assertIn("ttl_days", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
