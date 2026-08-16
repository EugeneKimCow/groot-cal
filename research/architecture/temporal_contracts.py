"""E-007 prototype: typed temporal slices and grain alignment."""
from dataclasses import dataclass
from datetime import date, timedelta


class TemporalError(ValueError):
    pass


class MissingTemporalData(TemporalError):
    pass


@dataclass(frozen=True)
class TimeWindow:
    start: date
    end: date
    calendar_ref: str = "gregorian"


@dataclass(frozen=True)
class TemporalMetric:
    metric_ref: str
    observation_grain: str
    spatial_aggregate: str
    allowed_time_reducers: tuple


def _dates(window):
    count = (window.end - window.start).days + 1
    return [window.start + timedelta(days=offset) for offset in range(count)]


def evaluate_snapshots(metric, rows, window, time_reducer):
    if time_reducer not in metric.allowed_time_reducers:
        raise TemporalError(f"time reducer not allowed: {time_reducer}")
    by_day = {}
    for row in rows:
        observed = date.fromisoformat(row["date"])
        if window.start <= observed <= window.end:
            by_day[observed] = by_day.get(observed, 0) + row["value"]

    if time_reducer == "period_end":
        if window.end not in by_day:
            raise MissingTemporalData(f"missing period-end snapshot {window.end}")
        return {"status": "result", "value": by_day[window.end],
                "time_reducer": time_reducer, "observations": 1}

    if time_reducer == "average_daily_snapshot":
        if metric.observation_grain != "daily_snapshot":
            raise MissingTemporalData("daily snapshot grain is unavailable")
        expected = _dates(window)
        missing = [str(day) for day in expected if day not in by_day]
        if missing:
            raise MissingTemporalData(f"missing daily snapshots: {missing}")
        return {"status": "result",
                "value": sum(by_day[day] for day in expected) / len(expected),
                "time_reducer": time_reducer, "observations": len(expected)}
    raise TemporalError(f"unsupported time reducer: {time_reducer}")


def align_daily_actual_to_weekly_plan(actual_rows, plan, window, rollup):
    """Compiler/type-checker alignment, not an analytical diagnosis operator."""
    if rollup != "sum":
        raise TemporalError("weekly plan alignment requires explicit additive sum")
    expected = _dates(window)
    actual_by_day = {date.fromisoformat(row["date"]): row["value"] for row in actual_rows
                     if window.start <= date.fromisoformat(row["date"]) <= window.end}
    missing = [str(day) for day in expected if day not in actual_by_day]
    if missing:
        raise MissingTemporalData(f"incomplete daily actual grain: {missing}")
    actual = sum(actual_by_day[day] for day in expected)
    return {"status": "result", "window": [str(window.start), str(window.end)],
            "calendar_ref": window.calendar_ref, "rollup": rollup,
            "plan": plan, "actual": actual, "gap": actual - plan,
            "checks": [{"check": "calendar_alignment", "passed": True},
                       {"check": "grain_complete", "passed": True}]}


def resolve_named_period(calendar, period_id):
    matches = sorted(day for day, name in calendar.items() if name == period_id)
    if not matches:
        raise TemporalError(f"unknown period: {period_id}")
    expected = _dates(TimeWindow(matches[0], matches[-1]))
    if matches != expected:
        raise TemporalError(f"calendar period is not contiguous: {period_id}")
    return TimeWindow(matches[0], matches[-1], calendar_ref="registered_calendar")

