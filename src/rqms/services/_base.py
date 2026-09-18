"""서비스 공통 유틸 — 통제 강제 및 날짜 계산."""

from __future__ import annotations

from datetime import date, timedelta

from ..db import Database, today
from ..errors import ControlViolation
from ..standard import load_registry


def enforce(
    control_id: str,
    ok: bool,
    message: str,
    *,
    db: Database | None = None,
    context: str = "",
) -> None:
    """통제를 강제한다. 조건이 거짓이면 ControlViolation 을 발생시킨다.

    근거 조항은 통제 카탈로그에서 자동으로 부착되므로, 호출부는 업무 의미만 표현한다.
    """
    if ok:
        return
    clauses = load_registry().control(control_id).clauses
    violation = ControlViolation(control_id, message, clauses)
    if db is not None:
        db.log_violation(violation, context or control_id)
    raise violation


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def add_months(value: str, months: int) -> str:
    """ISO 날짜에 개월을 더한다(월말 보정 포함)."""
    base = parse_date(value)
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, _days_in_month(year, month))
    return date(year, month, day).isoformat()


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def is_past(deadline: str | None, *, as_of: str | None = None) -> bool:
    """기한이 기준일보다 이전인지(경과했는지) 판정한다."""
    if not deadline:
        return True
    return parse_date(deadline) < parse_date(as_of or today())


def months_between(start: str, end: str) -> int:
    a, b = parse_date(start), parse_date(end)
    return (b.year - a.year) * 12 + (b.month - a.month)
