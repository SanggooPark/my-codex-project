"""RQMS 로컬 운영 웹 UI.

품질담당자가 브라우저에서 등록부를 조회하고 업무를 입력하기 위한 화면이다.
외부 라이브러리 없이 표준 라이브러리(`http.server`)만 사용한다.

핵심 원칙
    화면은 DB 에 직접 쓰지 않는다. 모든 입력은 `rqms.services.*` 의 업무 함수를
    호출하므로, CLI·API·화면 어느 경로로 들어오든 동일한 통제(ISO 22163 요구사항)가
    강제된다. 통제 위반은 화면에 통제 ID·근거 조항과 함께 그대로 표시된다.

구성
    actions  서비스 함수 시그니처를 추론한 액션(입력 폼) 레지스트리
    views    서버사이드 HTML 렌더링
    server   라우팅 및 요청 처리 (python -m rqms serve)
"""

from __future__ import annotations

__all__ = ["actions", "server", "views"]
