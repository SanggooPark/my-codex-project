"""CFG — 형상 관리 프로세스 (8.1.4.1).

강제 통제
    CTL-006  형상 기준선 변경은 승인된 변경요청에 의해서만 (8.1.4.1.1 e)
    CTL-007  안전관련 형상항목의 식별 (8.1.4.1.1 c)
"""

from __future__ import annotations

from sqlite3 import Row

from ..db import Database, today
from . import change
from ._base import enforce

#: 8.1.4.1.1 d) 형상 기준선 종류
BASELINE_KINDS = ("as_designed", "as_built", "as_maintained", "test")


def add_item(
    db: Database,
    *,
    project_code: str | None,
    part_no: str,
    name: str,
    parent_part_no: str | None = None,
    safety_related: bool = False,
    traceability_method: str = "",
    is_llru: bool = False,
    is_tool: bool = False,
    revision: str = "A",
) -> int:
    """형상항목을 제품분할구조(PBS)에 등록한다 (8.1.4.1.1 b, c, g).

    안전관련 항목은 추적성 식별 기준(예: 시리얼, 로트번호)이 반드시 정의되어야 한다.
    """
    project_id = None
    if project_code:
        project_id = int(db.require("project", code=project_code)["id"])

    parent_id = None
    pbs_level = 1
    if parent_part_no:
        parent = db.require("config_item", project_id=project_id, part_no=parent_part_no)
        parent_id = int(parent["id"])
        pbs_level = int(parent["pbs_level"]) + 1

    if safety_related:
        enforce(
            "CTL-007",
            bool(traceability_method.strip()),
            f"형상항목 {part_no}: 안전관련 항목은 추적성 식별 기준을 정의해야 합니다"
            " (8.1.4.1.1 c, g).",
            db=db,
            context=f"config_item:{part_no}",
        )
    return db.insert(
        "config_item",
        project_id=project_id,
        part_no=part_no,
        name=name,
        parent_id=parent_id,
        pbs_level=pbs_level,
        is_llru=int(is_llru),
        safety_related=int(safety_related),
        traceability_method=traceability_method,
        is_tool=int(is_tool),
        revision=revision,
    )


def establish_baseline(
    db: Database,
    *,
    project_code: str,
    name: str,
    kind: str,
    part_numbers: list[str],
) -> int:
    """형상 기준선을 설정하고 동결한다 (8.1.4.1.1 d)."""
    if kind not in BASELINE_KINDS:
        raise ValueError(f"알 수 없는 기준선 종류: {kind}")
    project = db.require("project", code=project_code)
    enforce(
        "CTL-006",
        bool(part_numbers),
        f"{project_code}/{name}: 형상 기준선은 최소 1개 형상항목을 포함해야 합니다.",
        db=db,
        context=f"baseline:{name}",
    )
    baseline_id = db.insert(
        "baseline",
        project_id=project["id"],
        name=name,
        kind=kind,
        established_on=today(),
        frozen=1,
    )
    for part_no in part_numbers:
        item = db.require("config_item", project_id=project["id"], part_no=part_no)
        db.insert(
            "baseline_item",
            baseline_id=baseline_id,
            config_item_id=item["id"],
            revision=item["revision"],
        )
    return baseline_id


def revise_item_in_baseline(
    db: Database,
    *,
    project_code: str,
    baseline_name: str,
    part_no: str,
    new_revision: str,
) -> Row:
    """기준선에 포함된 형상항목의 개정을 반영한다 (8.1.4.1.1 e, f).

    동결된 기준선은 승인된 변경요청 없이 변경할 수 없으며(CTL-006),
    변경 내역은 형상상태 기록으로 남는다.
    """
    project = db.require("project", code=project_code)
    baseline = db.require("baseline", project_id=project["id"], name=baseline_name)
    item = db.require("config_item", project_id=project["id"], part_no=part_no)
    entry = db.find("baseline_item", baseline_id=baseline["id"], config_item_id=item["id"])
    enforce(
        "CTL-006",
        entry is not None,
        f"{baseline_name}: 형상항목 {part_no} 는 이 기준선에 포함되지 않았습니다.",
        db=db,
        context=f"baseline:{baseline_name}",
    )
    assert entry is not None

    change_request = None
    if baseline["frozen"]:
        change_request = change.assert_approved_change(
            db,
            scope="configuration",
            target_ref=part_no,
            control_id="CTL-006",
            purpose=f"형상 기준선 {baseline_name} 의 {part_no} 개정",
        )

    db.insert(
        "config_status_record",
        baseline_id=baseline["id"],
        config_item_id=item["id"],
        from_revision=entry["revision"],
        to_revision=new_revision,
        change_no=change_request["change_no"] if change_request else None,
        recorded_on=today(),
    )
    db.update("baseline_item", entry["id"], revision=new_revision)
    db.update("config_item", item["id"], revision=new_revision)
    return db.fetch("config_item", item["id"])


def status_accounting(db: Database, project_code: str) -> list[dict[str, object]]:
    """형상 상태 기록(configuration status accounting) (8.1.4.1.1 f)."""
    project = db.require("project", code=project_code)
    rows = db.query(
        "SELECT b.name AS baseline, b.kind, ci.part_no, csr.from_revision, "
        "       csr.to_revision, csr.change_no, csr.recorded_on "
        "FROM config_status_record csr "
        "JOIN baseline b ON b.id = csr.baseline_id "
        "JOIN config_item ci ON ci.id = csr.config_item_id "
        "WHERE b.project_id = ? ORDER BY csr.recorded_on, ci.part_no",
        (project["id"],),
    )
    return [dict(r) for r in rows]


def safety_items_without_traceability(db: Database) -> list[Row]:
    """추적성 기준이 없는 안전관련 형상항목 (CTL-007)."""
    return db.query(
        "SELECT * FROM config_item "
        "WHERE safety_related = 1 AND TRIM(traceability_method) = ''"
    )


def breakdown(db: Database, project_code: str) -> list[dict[str, object]]:
    """제품분할구조를 LLRU 까지 반환한다 (8.1.4.1.1 b)."""
    project = db.require("project", code=project_code)
    rows = db.query(
        "SELECT * FROM config_item WHERE project_id = ? ORDER BY pbs_level, part_no",
        (project["id"],),
    )
    return [
        {
            "part_no": r["part_no"],
            "name": r["name"],
            "level": r["pbs_level"],
            "llru": bool(r["is_llru"]),
            "safety_related": bool(r["safety_related"]),
            "revision": r["revision"],
        }
        for r in rows
    ]
