"""ISO 22163:2023 표준 레지스트리 로더.

`src/rqms/data` 의 JSON 레지스트리를 읽어 조항(Clause), 프로세스(Process),
성과지표(Indicator), 통제(Control) 객체로 제공한다. 레지스트리는 QMS 담당자가
직접 편집하는 문서화된 정보이며, 코드는 이를 단일 진실원천으로 사용한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# ISO 22163:2023 3.2 약어
ABBREVIATIONS: dict[str, str] = {
    "ATE": "automated test equipment",
    "EPPPS": "externally provided processes, products and services",
    "FAI": "first article inspection",
    "FMEA": "failure mode and effects analysis",
    "FMECA": "failure mode, effects and criticality analysis",
    "FRACAS": "failure reporting analysis and corrective action system",
    "KPI": "key performance indicator",
    "LCC": "life cycle cost",
    "LLRU": "lowest line replaceable unit",
    "OTD": "on time delivery index",
    "PI": "performance indicator",
    "RAM": "reliability, availability, maintainability",
    "RAMS": "reliability, availability, maintainability, safety",
    "RFT": "right first time",
    "RQMS": "railway quality management system",
    "SIL": "safety integrity level",
    "SMART": "specific, measurable, achievable, relevant, time framed",
    "SWOT": "strengths weaknesses opportunities threats",
    "8D": "eight disciplines (of problem solving)",
}


@dataclass(frozen=True)
class Clause:
    """표준 조항 단위 요구사항."""

    id: str
    title_ko: str
    title_en: str
    obligation: str  # shall | should | shall_conditional
    source: str  # iso9001 | iso22163
    processes: tuple[str, ...] = ()
    documented_info: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    applicability_condition: str | None = None

    @property
    def is_mandatory(self) -> bool:
        return self.obligation in ("shall", "shall_conditional")

    @property
    def sort_key(self) -> tuple[int, ...]:
        return tuple(int(p) for p in self.id.split("."))


@dataclass(frozen=True)
class Process:
    """Annex A 프로세스."""

    code: str
    name_ko: str
    name_en: str
    clause: str
    obligation: str  # mandatory | mandatory_conditional | recommended
    level: int
    parent: str | None
    owner_role: str
    module: str
    review_cycle_months: int
    applicability_condition: str | None = None

    @property
    def is_mandatory(self) -> bool:
        return self.obligation.startswith("mandatory")


@dataclass(frozen=True)
class Indicator:
    """성과지표(PI/KPI) 정의 — 9.1.1.1.1 a)~g) 및 Table C.1."""

    code: str
    title_ko: str
    title_en: str
    mandate: str  # required | recommended | process_pi
    mandate_clause: str
    is_kpi: bool
    purpose: str
    processes: tuple[str, ...]
    owner_role: str
    formula: str
    unit: str
    target: float
    target_direction: str  # higher_is_better | lower_is_better
    period: str
    data_source: str
    measured_by_role: str
    reported_to: tuple[str, ...]
    reporting_frequency: str
    action_owner_role: str

    #: 9.1.1.1.1 a)~g) 에 대응하는 정의 필수 항목
    DEFINITION_FIELDS = (
        "processes",
        "formula",
        "target",
        "measured_by_role",
        "reported_to",
        "action_owner_role",
        "data_source",
    )

    def missing_definition_fields(self) -> list[str]:
        """9.1.1.1.1 a)~g) 중 비어 있는 항목을 돌려준다."""
        missing = []
        for name in self.DEFINITION_FIELDS:
            value = getattr(self, name)
            if value is None or (isinstance(value, (str, tuple, list)) and len(value) == 0):
                missing.append(name)
        if not self.period or not self.reporting_frequency:
            missing.append("period")
        return missing

    def is_met(self, value: float) -> bool:
        """측정값이 목표를 달성했는지 판정한다."""
        if self.target_direction == "lower_is_better":
            return value <= self.target
        return value >= self.target


@dataclass(frozen=True)
class Control:
    """RQMS 통제."""

    id: str
    kind: str  # invariant | audit
    severity: str  # major | minor
    title: str
    clauses: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    """표준 레지스트리 전체."""

    clauses: tuple[Clause, ...]
    processes: tuple[Process, ...]
    indicators: tuple[Indicator, ...]
    controls: tuple[Control, ...]
    _by_clause: dict[str, Clause] = field(default_factory=dict, repr=False)
    _by_process: dict[str, Process] = field(default_factory=dict, repr=False)
    _by_indicator: dict[str, Indicator] = field(default_factory=dict, repr=False)
    _by_control: dict[str, Control] = field(default_factory=dict, repr=False)

    def clause(self, clause_id: str) -> Clause:
        return self._by_clause[clause_id]

    def process(self, code: str) -> Process:
        return self._by_process[code]

    def indicator(self, code: str) -> Indicator:
        return self._by_indicator[code]

    def control(self, control_id: str) -> Control:
        return self._by_control[control_id]

    def mandatory_processes(self) -> tuple[Process, ...]:
        return tuple(p for p in self.processes if p.is_mandatory)

    def recommended_processes(self) -> tuple[Process, ...]:
        return tuple(p for p in self.processes if p.obligation == "recommended")

    def kpis(self) -> tuple[Indicator, ...]:
        return tuple(i for i in self.indicators if i.is_kpi)

    def clauses_for_control(self, control_id: str) -> tuple[Clause, ...]:
        return tuple(c for c in self.clauses if control_id in c.controls)

    def clauses_for_process(self, code: str) -> tuple[Clause, ...]:
        return tuple(c for c in self.clauses if code in c.processes)

    def indicators_for_process(self, code: str) -> tuple[Indicator, ...]:
        return tuple(i for i in self.indicators if code in i.processes)

    def controls_by_kind(self, kind: str) -> tuple[Control, ...]:
        return tuple(c for c in self.controls if c.kind == kind)


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_clauses(data_dir: Path) -> tuple[Clause, ...]:
    clauses: list[Clause] = []
    clause_dir = data_dir / "clauses"
    for path in sorted(clause_dir.glob("*.json")):
        for raw in _load_json(path)["clauses"]:
            clauses.append(
                Clause(
                    id=raw["id"],
                    title_ko=raw["title_ko"],
                    title_en=raw["title_en"],
                    obligation=raw["obligation"],
                    source=raw["source"],
                    processes=tuple(raw.get("processes", ())),
                    documented_info=tuple(raw.get("documented_info", ())),
                    modules=tuple(raw.get("modules", ())),
                    controls=tuple(raw.get("controls", ())),
                    applicability_condition=raw.get("applicability_condition"),
                )
            )
    return tuple(sorted(clauses, key=lambda c: c.sort_key))


def _load_processes(data_dir: Path) -> tuple[Process, ...]:
    return tuple(
        Process(
            code=raw["code"],
            name_ko=raw["name_ko"],
            name_en=raw["name_en"],
            clause=raw["clause"],
            obligation=raw["obligation"],
            level=raw["level"],
            parent=raw.get("parent"),
            owner_role=raw["owner_role"],
            module=raw["module"],
            review_cycle_months=raw["review_cycle_months"],
            applicability_condition=raw.get("applicability_condition"),
        )
        for raw in _load_json(data_dir / "processes.json")["processes"]
    )


def _load_indicators(data_dir: Path) -> tuple[Indicator, ...]:
    return tuple(
        Indicator(
            code=raw["code"],
            title_ko=raw["title_ko"],
            title_en=raw["title_en"],
            mandate=raw["mandate"],
            mandate_clause=raw["mandate_clause"],
            is_kpi=raw["is_kpi"],
            purpose=raw["purpose"],
            processes=tuple(raw["processes"]),
            owner_role=raw["owner_role"],
            formula=raw["formula"],
            unit=raw["unit"],
            target=float(raw["target"]),
            target_direction=raw["target_direction"],
            period=raw["period"],
            data_source=raw["data_source"],
            measured_by_role=raw["measured_by_role"],
            reported_to=tuple(raw["reported_to"]),
            reporting_frequency=raw["reporting_frequency"],
            action_owner_role=raw["action_owner_role"],
        )
        for raw in _load_json(data_dir / "indicators.json")["indicators"]
    )


def _load_controls(data_dir: Path) -> tuple[Control, ...]:
    return tuple(
        Control(
            id=raw["id"],
            kind=raw["kind"],
            severity=raw["severity"],
            title=raw["title"],
            clauses=tuple(raw["clauses"]),
        )
        for raw in _load_json(data_dir / "controls.json")["controls"]
    )


@lru_cache(maxsize=1)
def load_registry(data_dir: Path | None = None) -> Registry:
    """레지스트리를 읽어 정합성을 검증한 뒤 반환한다."""
    base = data_dir or DATA_DIR
    clauses = _load_clauses(base)
    processes = _load_processes(base)
    indicators = _load_indicators(base)
    controls = _load_controls(base)

    registry = Registry(
        clauses=clauses,
        processes=processes,
        indicators=indicators,
        controls=controls,
        _by_clause={c.id: c for c in clauses},
        _by_process={p.code: p for p in processes},
        _by_indicator={i.code: i for i in indicators},
        _by_control={c.id: c for c in controls},
    )
    validate_registry(registry)
    return registry


def validate_registry(registry: Registry) -> None:
    """레지스트리 상호 참조 정합성을 검증한다.

    레지스트리가 깨지면 적합성 보고 전체가 무효가 되므로 로드 시점에 검증한다.
    """
    errors: list[str] = []

    known_processes = {p.code for p in registry.processes}
    known_controls = {c.id for c in registry.controls}
    known_clauses = {c.id for c in registry.clauses}

    if len(known_clauses) != len(registry.clauses):
        errors.append("조항 ID 중복이 있습니다.")

    for clause in registry.clauses:
        for code in clause.processes:
            if code not in known_processes:
                errors.append(f"조항 {clause.id}: 미정의 프로세스 코드 {code}")
        for control_id in clause.controls:
            if control_id not in known_controls:
                errors.append(f"조항 {clause.id}: 미정의 통제 {control_id}")
        if clause.obligation not in ("shall", "should", "shall_conditional"):
            errors.append(f"조항 {clause.id}: 잘못된 obligation {clause.obligation}")

    for process in registry.processes:
        if process.clause not in known_clauses:
            errors.append(f"프로세스 {process.code}: 미정의 근거 조항 {process.clause}")
        if process.parent and process.parent not in known_processes:
            errors.append(f"프로세스 {process.code}: 미정의 상위 프로세스 {process.parent}")

    for indicator in registry.indicators:
        for code in indicator.processes:
            if code not in known_processes:
                errors.append(f"지표 {indicator.code}: 미정의 프로세스 코드 {code}")

    for control in registry.controls:
        for clause_id in control.clauses:
            if clause_id not in known_clauses:
                errors.append(f"통제 {control.id}: 미정의 조항 {clause_id}")
        if not registry.clauses_for_control(control.id):
            errors.append(f"통제 {control.id}: 어떤 조항에서도 참조되지 않음")

    # 4.4.1 c) — 구현된 모든 프로세스는 최소 1개의 PI 를 가져야 한다.
    for process in registry.processes:
        if not registry.indicators_for_process(process.code):
            errors.append(f"프로세스 {process.code}: 성과지표 미정의 (4.4.1 c)")

    if errors:
        raise ValueError("레지스트리 정합성 오류:\n  - " + "\n  - ".join(errors))
