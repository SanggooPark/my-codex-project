"""RQMS — ISO 22163:2023 기반 철도용 품질경영시스템(Railway Quality Management System).

이 패키지는 ISO 22163:2023의 요구사항을 운영 가능한 시스템으로 구현한다.

구성
    standard    표준 조항·프로세스·성과지표·통제 레지스트리 (src/rqms/data)
    db          SQLite 기반 저장계층 및 스키마
    services    Annex A 필수/권고 프로세스별 업무 로직 (통제 강제 지점)
    checks      상태 점검형 통제(kind=audit) 검증
    conformity  조항-통제-증거 추적 매트릭스 및 갭 분석
    cli         운영 진입점 (python -m rqms)
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
