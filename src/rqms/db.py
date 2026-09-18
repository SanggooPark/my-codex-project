"""SQLite 저장계층.

ISO 22163 7.5.3 (문서화된 정보의 관리)를 고려하여, 기록은 원칙적으로 추가(append)
되며 승인된 기록은 `seal` 해시로 봉인된다(7.5.3.2 "의도하지 않은 변경으로부터 보호").
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from .errors import ControlViolation, NotFound

SCHEMA_PATH = Path(__file__).parent / "data" / "schema.sql"


class Database:
    """RQMS 데이터베이스 핸들."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------ 라이프사이클
    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ----------------------------------------------------------------- 질의
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params))

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        cur = self.conn.execute(sql, params)
        return cur.fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.one(sql, params)
        return None if row is None else row[0]

    def count(self, sql: str, params: Sequence[Any] = ()) -> int:
        return int(self.scalar(sql, params) or 0)

    def fetch(self, table: str, row_id: int) -> sqlite3.Row:
        row = self.one(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
        if row is None:
            raise NotFound(f"{table} id={row_id} 레코드를 찾을 수 없습니다.")
        return row

    def find(self, table: str, **where: Any) -> sqlite3.Row | None:
        clause = " AND ".join(f"{k} = ?" for k in where)
        return self.one(f"SELECT * FROM {table} WHERE {clause}", tuple(where.values()))

    def require(self, table: str, **where: Any) -> sqlite3.Row:
        row = self.find(table, **where)
        if row is None:
            criteria = ", ".join(f"{k}={v!r}" for k, v in where.items())
            raise NotFound(f"{table}({criteria}) 레코드를 찾을 수 없습니다.")
        return row

    # ----------------------------------------------------------------- 변경
    def insert(self, table: str, **values: Any) -> int:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cur = self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, table: str, row_id: int, **values: Any) -> None:
        if not values:
            return
        assignments = ", ".join(f"{k} = ?" for k in values)
        self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            (*values.values(), row_id),
        )
        self.conn.commit()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    # ------------------------------------------------------- 통제 위반 기록
    def log_violation(self, violation: ControlViolation, context: str) -> None:
        """통제 위반을 로그로 남긴다(9.1.1.1.1 내·외부 실패 데이터 수집)."""
        self.insert(
            "control_violation_log",
            control_id=violation.control_id,
            clauses=",".join(violation.clauses),
            context=context,
            message=str(violation),
            occurred_at=today(),
        )


def today() -> str:
    return date.today().isoformat()


def seal_of(values: Iterable[Any]) -> str:
    """기록 무결성 봉인 해시 (7.5.3.2)."""
    payload = json.dumps([None if v is None else str(v) for v in values], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def open_database(path: str | Path, *, create: bool = False) -> Database:
    """데이터베이스를 연다. create=True 이면 스키마를 생성한다."""
    db = Database(path)
    if create or path == ":memory:" or not Path(str(path)).exists():
        db.init_schema()
    else:
        db.init_schema()  # CREATE TABLE IF NOT EXISTS — 멱등
    return db
