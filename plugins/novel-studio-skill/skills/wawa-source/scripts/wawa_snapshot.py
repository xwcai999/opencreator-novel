#!/usr/bin/env python3
"""蛙蛙统计快照的离线校验、TTL、聚合与脱敏工具。

这里故意只依赖 Python 标准库并读取本地 JSON。任何网络访问、账号态或平台
页面操作都不属于本模块的职责。输入快照可以保留本地原始标识，公开输出则
必须经过 :func:`redact_snapshot`。
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "wawa.stats.v1"
DEFAULT_TTL_DAYS = 7
MAX_TTL_DAYS = 31
INTEGER_METRICS = ("chapters", "words", "followers", "readers", "follow_delta")
MONEY_METRICS = ("total_revenue", "daily_revenue")
SERIES_METRICS = ("chapters", "words", "total_revenue", "daily_revenue", "followers", "readers", "follow_delta")
METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "chapters": ("chapters", "chapter_count", "chapterCount", "章节数", "章节"),
    "words": ("words", "word_count", "wordCount", "字数", "总字数"),
    "followers": ("followers", "follower_count", "followerCount", "追读人数", "粉丝数", "关注人数"),
    "readers": ("readers", "reader_count", "readerCount", "read_count", "readCount", "阅读人数"),
    "follow_delta": ("follow_delta", "followDelta", "followers_delta", "followersDelta", "追读增量", "关注增量"),
    "total_revenue": ("total_revenue", "totalRevenue", "revenue_total", "revenueTotal", "累计收益", "总收益"),
    "daily_revenue": ("daily_revenue", "dailyRevenue", "today_revenue", "todayRevenue", "日收益"),
}
SERIES_ALIASES: dict[str, tuple[str, ...]] = {
    "chapters": METRIC_ALIASES["chapters"],
    "words": METRIC_ALIASES["words"],
    "total_revenue": METRIC_ALIASES["total_revenue"],
    "daily_revenue": ("daily_revenue", "dailyRevenue", "revenue", "收益", "日收益"),
    "followers": METRIC_ALIASES["followers"],
    "readers": METRIC_ALIASES["readers"],
    "follow_delta": METRIC_ALIASES["follow_delta"],
}


class SnapshotError(ValueError):
    """快照不是可安全消费的 ``wawa.stats.v1`` 数据。"""


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _lookup(mapping: Mapping[str, Any], aliases: Sequence[str]) -> Any:
    for key in aliases:
        if key in mapping:
            return mapping[key]
    return None


def _parse_datetime(value: Any, *, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotError(f"{field} 必须是带时区的 RFC 3339 时间字符串")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise SnapshotError(f"{field} 时间格式无效") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotError(f"{field} 必须包含时区")
    return parsed


def _parse_now(value: dt.datetime | str | None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(dt.timezone.utc)
    if isinstance(value, dt.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise SnapshotError("now 必须包含时区")
        return value
    return _parse_datetime(value, field="now")


def _format_datetime(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_date(value: Any, *, field: str) -> dt.date:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotError(f"{field} 必须是 YYYY-MM-DD 日期")
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError as exc:
        raise SnapshotError(f"{field} 日期格式无效") from exc


def _decimal(value: Any, *, field: str, allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise SnapshotError(f"{field} 必须是有限数字")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SnapshotError(f"{field} 必须是有限数字") from exc
    if not number.is_finite() or (not allow_negative and number < 0):
        raise SnapshotError(f"{field} 必须是有限{'' if allow_negative else '非负'}数字")
    return number


def _integer(value: Any, *, field: str, allow_negative: bool = False) -> int:
    number = _decimal(value, field=field, allow_negative=allow_negative)
    if number != number.to_integral_value():
        raise SnapshotError(f"{field} 必须是整数")
    return int(number)


def _json_number(value: Decimal | int) -> int | float:
    if isinstance(value, int):
        return value
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _ttl_seconds(data: Mapping[str, Any]) -> tuple[int, int]:
    """返回 (秒数, 公开展示的整天数)。"""

    if "ttl_hours" in data or "ttl_seconds" in data:
        raise SnapshotError("wawa.stats.v1 只支持正整数 ttl_days")
    if "ttl_days" in data:
        days = _integer(data["ttl_days"], field="ttl_days")
        if days < 1 or days > MAX_TTL_DAYS:
            raise SnapshotError(f"ttl_days 必须在 1—{MAX_TTL_DAYS} 之间")
        return days * 86400, days
    return DEFAULT_TTL_DAYS * 86400, DEFAULT_TTL_DAYS


def _normalise_metrics(value: Any, *, field: str) -> dict[str, int | float]:
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise SnapshotError(f"{field} 必须是对象")
    result: dict[str, int | float] = {}
    for name in INTEGER_METRICS:
        raw = _lookup(value, METRIC_ALIASES[name])
        if raw is not None:
            result[name] = _integer(raw, field=f"{field}.{name}", allow_negative=name == "follow_delta")
    for name in MONEY_METRICS:
        raw = _lookup(value, METRIC_ALIASES[name])
        if raw is not None:
            result[name] = _json_number(_decimal(raw, field=f"{field}.{name}"))
    return result


def _normalise_series(value: Any, *, field: str, captured_date: dt.date) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise SnapshotError(f"{field} 必须是数组")
    result: list[dict[str, Any]] = []
    seen: set[dt.date] = set()
    for index, item in enumerate(value, start=1):
        item_field = f"{field}[{index}]"
        if not isinstance(item, Mapping):
            raise SnapshotError(f"{item_field} 必须是对象")
        date = _parse_date(_lookup(item, ("date", "day", "日期")), field=f"{item_field}.date")
        if date > captured_date:
            raise SnapshotError(f"{item_field}.date 不能晚于 captured_at")
        if date in seen:
            raise SnapshotError(f"{field} 不能包含重复日期: {date.isoformat()}")
        seen.add(date)
        point: dict[str, Any] = {"date": date.isoformat()}
        for name in SERIES_METRICS:
            raw = _lookup(item, SERIES_ALIASES[name])
            if raw is None:
                continue
            point[name] = (
                _json_number(_decimal(raw, field=f"{item_field}.{name}"))
                if name in MONEY_METRICS
                else _integer(raw, field=f"{item_field}.{name}", allow_negative=name == "follow_delta")
            )
        result.append(point)
    return sorted(result, key=lambda item: item["date"])


def _normalise_work(value: Any, *, index: int, captured_date: dt.date) -> dict[str, Any]:
    field = f"works[{index}]"
    if not isinstance(value, Mapping):
        raise SnapshotError(f"{field} 必须是对象")
    result: dict[str, Any] = {}
    # 这些字段只在未脱敏的本地中间结果中保留，公开视图会全部移除。
    for key in ("work_id", "workId", "id", "title", "name", "author", "pen_name", "status", "channel"):
        if key in value and isinstance(value[key], (str, int)) and not isinstance(value[key], bool):
            result[key] = value[key]
    result["metrics"] = _normalise_metrics(value.get("metrics", value.get("指标")), field=f"{field}.metrics")
    result["series"] = _normalise_series(value.get("series", value.get("trend", value.get("趋势"))), field=f"{field}.series", captured_date=captured_date)
    return result


def normalize_snapshot(data: Mapping[str, Any]) -> dict[str, Any]:
    """校验并转换快照为规范化结构；失败时抛出 :class:`SnapshotError`。"""

    if not isinstance(data, Mapping):
        raise SnapshotError("快照根节点必须是对象")
    version = data.get("schema_version")
    if version not in {SCHEMA_VERSION, "1", "1.0"}:
        raise SnapshotError(f"不支持的 schema_version: {version!r}")
    captured = _parse_datetime(data.get("captured_at"), field="captured_at")
    ttl_seconds, ttl_days = _ttl_seconds(data)
    expected_expires = captured + dt.timedelta(seconds=ttl_seconds)
    declared_expires = data.get("expires_at", data.get("stale_after"))
    if declared_expires is not None:
        parsed_expires = _parse_datetime(declared_expires, field="expires_at")
        if parsed_expires != expected_expires:
            raise SnapshotError("expires_at 必须与 captured_at 和 TTL 一致")
    source = data.get("source")
    if not isinstance(source, Mapping):
        raise SnapshotError("source 必须是对象")
    kind = _clean_text(source.get("kind"))
    if not kind or len(kind) > 80:
        raise SnapshotError("source.kind 不能为空且长度不能超过 80")
    label = _clean_text(source.get("label"))
    if len(label) > 120:
        raise SnapshotError("source.label 长度不能超过 120")
    works = data.get("works")
    if not isinstance(works, list):
        raise SnapshotError("works 必须是数组")
    # 趋势日期属于快照声明的本地日历。先换算 UTC 会让 +08:00 午夜附近
    # 的当天记录落到前一天，并被误判为“未来日期”。
    captured_date = captured.date()
    normalised: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": _format_datetime(captured),
        "ttl_days": ttl_days,
        "expires_at": _format_datetime(expected_expires),
        "source": {"kind": kind, "label": label or "本地快照"},
        "works": [_normalise_work(item, index=index, captured_date=captured_date) for index, item in enumerate(works, start=1)],
    }
    account = data.get("account")
    if isinstance(account, Mapping):
        normalised["account"] = copy.deepcopy(dict(account))
    return normalised


def freshness(snapshot: Mapping[str, Any], now: dt.datetime | str | None = None) -> str:
    """返回 ``fresh`` 或 ``stale``；调用方应先完成结构校验。"""

    current = _parse_now(now)
    expires = _parse_datetime(snapshot.get("expires_at"), field="expires_at")
    return "fresh" if current <= expires else "stale"


def redact_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """返回不含账号、作品身份和本机路径的公开视图。"""

    normalised = normalize_snapshot(snapshot)
    public: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": normalised["captured_at"],
        "ttl_days": normalised["ttl_days"],
        "expires_at": normalised["expires_at"],
        "source": {"kind": normalised["source"]["kind"], "label": "本地脱敏快照"},
        "privacy": {
            "redacted": True,
            "identifiers_removed": ["account", "work_id", "title", "author", "path", "url", "secret"],
        },
        "works": [],
    }
    for index, work in enumerate(normalised.get("works", []), start=1):
        safe_work: dict[str, Any] = {"label": f"作品 {index}", "metrics": copy.deepcopy(work.get("metrics", {})), "series": copy.deepcopy(work.get("series", []))}
        if work.get("status") in {"连载", "完结"}:
            safe_work["status"] = work["status"]
        public["works"].append(safe_work)
    return public


def _normalised_for_aggregate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """聚合入口始终重验结构，不能用形似规范化的数据绕过门禁。"""

    return normalize_snapshot(snapshot)


def aggregate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """计算 Dashboard 使用的聚合指标和时间窗口。"""

    normalised = _normalised_for_aggregate(snapshot)
    totals: dict[str, Decimal] = {name: Decimal(0) for name in (*INTEGER_METRICS, *MONEY_METRICS)}
    seen_totals: set[str] = set()
    series_by_date: dict[str, dict[str, Decimal]] = {}
    for work in normalised.get("works", []):
        metrics = work.get("metrics", {})
        for name in totals:
            if name in metrics:
                totals[name] += Decimal(str(metrics[name]))
                seen_totals.add(name)
        for point in work.get("series", []):
            date = point["date"]
            bucket = series_by_date.setdefault(date, {})
            for name in SERIES_METRICS:
                if name in point:
                    bucket[name] = bucket.get(name, Decimal(0)) + Decimal(str(point[name]))
    series: list[dict[str, Any]] = []
    for date in sorted(series_by_date):
        point: dict[str, Any] = {"date": date}
        for name, value in series_by_date[date].items():
            point[name] = _json_number(value)
        series.append(point)

    end_date = _parse_datetime(normalised["captured_at"], field="captured_at").date()
    windows: dict[str, Any] = {}
    for days in (7, 30, 90):
        start_date = end_date - dt.timedelta(days=days - 1)
        points = [point for point in series if start_date.isoformat() <= point["date"] <= end_date.isoformat()]
        window: dict[str, Any] = {"days": days, "start": start_date.isoformat(), "end": end_date.isoformat(), "points": len(points)}
        if points:
            for name in ("followers", "readers"):
                metric_points = [point for point in points if name in point]
                window[f"{name}_delta"] = metric_points[-1][name] - metric_points[0][name] if len(metric_points) >= 2 else None
            revenue_values = [Decimal(str(point["daily_revenue"])) for point in points if "daily_revenue" in point]
            window["revenue"] = _json_number(sum(revenue_values, Decimal(0))) if revenue_values else None
        else:
            window["revenue"] = None
            window["followers_delta"] = None
            window["readers_delta"] = None
        windows[f"{days}d"] = window

    totals_json = {name: _json_number(value) if name in seen_totals else None for name, value in totals.items()}
    return {"work_count": len(normalised.get("works", [])), "totals": totals_json, "series": series, "windows": windows}


def to_dashboard_snapshot(
    snapshot: Mapping[str, Any],
    *,
    days: int = 7,
    now: dt.datetime | str | None = None,
) -> dict[str, Any]:
    """生成 OpenCreator Dashboard 的脱敏只读 ``1.0.0`` 契约。"""

    if days not in {7, 30, 90}:
        raise SnapshotError("Dashboard days 只支持 7、30 或 90")
    normalised = _normalised_for_aggregate(snapshot)
    state = freshness(normalised, now)
    aggregate = aggregate_snapshot(normalised)
    end = _parse_datetime(normalised["captured_at"], field="captured_at").date()
    start = end - dt.timedelta(days=days - 1)
    points = [point for point in aggregate["series"] if start.isoformat() <= point["date"] <= end.isoformat()]
    totals = aggregate["totals"]
    metric_map = {
        "chapterCount": "chapters",
        "wordCount": "words",
        "revenue": "total_revenue",
        "dailyRevenue": "daily_revenue",
        "followers": "followers",
        "followDelta": "follow_delta",
    }
    dashboard_totals: dict[str, Any] = {"bookCount": aggregate["work_count"]}
    for public_name, internal_name in metric_map.items():
        dashboard_totals[public_name] = totals.get(internal_name)
    dashboard_trend = []
    for point in points:
        public_point: dict[str, Any] = {"date": point["date"]}
        for public_name, internal_name in metric_map.items():
            if internal_name in point:
                public_point[public_name] = point[internal_name]
        dashboard_trend.append(public_point)
    available = ["bookCount"] + [name for name in metric_map if dashboard_totals[name] is not None or any(name in point for point in dashboard_trend)]
    return {
        "contractVersion": "1.0.0",
        "status": "success" if state == "fresh" else "stale",
        "generatedAt": normalised["captured_at"],
        "range": {"days": days, "from": start.isoformat(), "to": end.isoformat()},
        "totals": dashboard_totals,
        "trend": dashboard_trend,
        "availableMetrics": available,
        "message": "离线脱敏聚合快照" if state == "fresh" else "快照已过期，仅供历史参考",
    }


def validate_snapshot(data: Mapping[str, Any], now: dt.datetime | str | None = None) -> dict[str, Any]:
    """返回结构校验报告；过期是可诊断状态，不是结构错误。"""

    try:
        normalised = normalize_snapshot(data)
    except SnapshotError as exc:
        return {"ok": False, "status": "invalid", "freshness": "invalid", "errors": [str(exc)], "warnings": []}
    state = freshness(normalised, now)
    warnings = [] if state == "fresh" else ["快照已超过 TTL，只能作为历史诊断，不能声称实时数据"]
    return {
        "ok": True,
        "status": state,
        "freshness": state,
        "errors": [],
        "warnings": warnings,
        "schema_version": SCHEMA_VERSION,
        "captured_at": normalised["captured_at"],
        "expires_at": normalised["expires_at"],
        "ttl_days": normalised["ttl_days"],
        "source": normalised["source"],
        "work_count": len(normalised["works"]),
    }


check_snapshot = validate_snapshot


def load_snapshot(path: str | Path, *, now: dt.datetime | str | None = None, redact: bool = True) -> dict[str, Any]:
    """从本地 JSON 文件读取并校验快照；无效输入抛出 ``SnapshotError``。"""

    candidate = Path(path).expanduser()
    try:
        with candidate.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"无法读取快照: {exc}") from exc
    normalised = normalize_snapshot(data)
    # 解析 now 是为了让调用者在传入坏时间时得到一致的错误；TTL 状态由报告单独给出。
    if now is not None:
        _parse_now(now)
    return redact_snapshot(normalised) if redact else normalised


def _result_for_file(path: str | Path, *, now: str | None, redact: bool) -> dict[str, Any]:
    candidate = Path(path).expanduser()
    try:
        with candidate.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        report = validate_snapshot(data, now)
        if not report["ok"]:
            return report
        normalised = normalize_snapshot(data)
        result: dict[str, Any] = dict(report)
        result["snapshot"] = redact_snapshot(normalised) if redact else normalised
        return result
    except (OSError, UnicodeError, json.JSONDecodeError, SnapshotError) as exc:
        return {"ok": False, "status": "invalid", "freshness": "invalid", "errors": [f"无法读取快照: {exc}"], "warnings": []}


def _human(report: Mapping[str, Any]) -> str:
    status = report.get("status", "invalid")
    lines = [f"快照状态: {status}"]
    if report.get("captured_at"):
        lines.append(f"采集时间: {report['captured_at']}")
    if report.get("expires_at"):
        lines.append(f"有效至: {report['expires_at']}")
    for label in ("errors", "warnings"):
        values = report.get(label) or []
        if values:
            lines.append(f"{label}:\n" + "\n".join(f"- {item}" for item in values))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="蛙蛙统计快照离线校验与聚合")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "aggregate", "dashboard"):
        sub = subparsers.add_parser(name, help="校验或聚合一个本地 JSON 快照")
        sub.add_argument("snapshot", help="本地快照 JSON 路径")
        sub.add_argument("--now", help="用于 TTL 判断的带时区时间，默认当前时间")
        sub.add_argument("--json", action="store_true", help="输出 JSON")
        sub.add_argument("--no-redact", action="store_true", help="仅限本地诊断，保留输入身份字段")
        if name == "dashboard":
            sub.add_argument("--days", type=int, choices=(7, 30, 90), default=7, help="Dashboard 趋势窗口")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    redact = not args.no_redact
    report = _result_for_file(args.snapshot, now=args.now, redact=redact)
    if report.get("ok") and args.command in {"aggregate", "dashboard"}:
        try:
            raw = load_snapshot(args.snapshot, now=args.now, redact=False)
            if args.command == "aggregate":
                report["aggregate"] = aggregate_snapshot(raw)
            else:
                report = to_dashboard_snapshot(raw, days=args.days, now=args.now)
        except SnapshotError as exc:
            report = {"ok": False, "status": "invalid", "freshness": "invalid", "errors": [str(exc)], "warnings": []}
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else _human(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
