"""Annex A 프로세스별 업무 서비스.

각 모듈은 ISO 22163:2023 의 해당 프로세스를 구현하며, 통제(control) 강제 지점이다.
모듈-조항 매핑은 `src/rqms/data/clauses` 레지스트리의 `modules` 항목에 선언되어 있고,
`rqms.conformity` 가 이를 검증한다.
"""

from __future__ import annotations

#: 레지스트리에서 참조하는 서비스 모듈 목록
MODULES = (
    "audit",
    "calibration",
    "capa",
    "change",
    "competence",
    "configuration",
    "customer",
    "design",
    "documents",
    "fai",
    "governance",
    "indicators",
    "nonconformity",
    "obsolescence",
    "post_delivery",
    "production",
    "projects",
    "rams",
    "release",
    "requirements",
    "review",
    "risk",
    "special_processes",
    "suppliers",
    "support",
    "tender",
    "transfer",
)

__all__ = ["MODULES"]
