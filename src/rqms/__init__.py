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

import sys

#: 지원 최소 Python 버전. 하위 버전에서는 애매한 SyntaxError/TypeError 대신
#: 원인을 바로 알 수 있는 메시지를 낸다.
MINIMUM_PYTHON = (3, 9)

if sys.version_info < MINIMUM_PYTHON:  # pragma: no cover - 구버전에서만 실행
    _required = ".".join(str(part) for part in MINIMUM_PYTHON)
    _current = ".".join(str(part) for part in sys.version_info[:3])
    raise RuntimeError(
        f"RQMS 는 Python {_required} 이상이 필요합니다. "
        f"현재 실행 중인 버전: {_current} ({sys.executable})\n"
        f"  해결: python3.11 -m rqms ... 처럼 상위 버전 인터프리터로 실행하거나,\n"
        f"        conda create -n rqms python=3.11 && conda activate rqms"
    )

__version__ = "1.0.0"
__all__ = ["__version__", "MINIMUM_PYTHON"]
