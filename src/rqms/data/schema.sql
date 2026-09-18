-- RQMS 스키마 (ISO 22163:2023)
-- 각 테이블 주석은 근거 조항을 표기한다. 모든 날짜는 ISO-8601 문자열(YYYY-MM-DD)로 저장한다.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- 조직 / 인원
-- 7.1.2 인원, 7.2 역량
CREATE TABLE IF NOT EXISTS person (
    id          INTEGER PRIMARY KEY,
    emp_no      TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    department  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

-- 4.4.3 a) 프로세스 계층구조, 5.3.1 b) 프로세스 오너 임명, 5.3.2
CREATE TABLE IF NOT EXISTS process_instance (
    code             TEXT PRIMARY KEY,          -- Annex A 프로세스 코드
    owner_id         INTEGER REFERENCES person(id),
    description_doc  INTEGER REFERENCES document(id),
    inputs           TEXT NOT NULL DEFAULT '',  -- 4.4.1 a)
    outputs          TEXT NOT NULL DEFAULT '',  -- 4.4.1 a)
    sequence_note    TEXT NOT NULL DEFAULT '',  -- 4.4.1 b)
    criteria         TEXT NOT NULL DEFAULT '',  -- 4.4.1 c)
    resources        TEXT NOT NULL DEFAULT '',  -- 4.4.1 d)
    risk_criteria    TEXT NOT NULL DEFAULT '',  -- 4.4.3 f)
    applicable       INTEGER NOT NULL DEFAULT 1,
    exclusion_reason TEXT
);

-- 4.4.3 c) 프로세스 교육
CREATE TABLE IF NOT EXISTS process_training (
    id             INTEGER PRIMARY KEY,
    process_code   TEXT NOT NULL REFERENCES process_instance(code),
    person_id      INTEGER NOT NULL REFERENCES person(id),
    trained_on     TEXT NOT NULL,
    understanding_evidence TEXT NOT NULL       -- 7.2.1.1 d) 2)
);

-- 5.3.1 d) 공정·생산 정지 권한을 가진 독립 대표자
CREATE TABLE IF NOT EXISTS stop_authority (
    id             INTEGER PRIMARY KEY,
    person_id      INTEGER NOT NULL REFERENCES person(id),
    scope          TEXT NOT NULL,
    independent_of TEXT NOT NULL,
    appointed_on   TEXT NOT NULL
);

-- ------------------------------------------------- 거버넌스(사업계획/방침/범위/BCP)
-- 4.1.1.1 사업계획, 4.3 적용범위, 5.2 품질방침, 6.1.4 사업연속성
CREATE TABLE IF NOT EXISTS governance_record (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,   -- business_plan | rqms_scope | quality_policy | business_continuity_plan | social_responsibility
    ref_year     INTEGER,
    doc_id       INTEGER REFERENCES document(id),
    payload      TEXT NOT NULL DEFAULT '{}',  -- 항목별 세부 내용(JSON)
    verified_on  TEXT,
    reviewed_on  TEXT,
    UNIQUE (kind, ref_year)
);

-- 4.1 외부·내부 이슈, 4.2 이해관계자
CREATE TABLE IF NOT EXISTS context_entry (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,   -- issue | interested_party
    origin       TEXT NOT NULL,   -- external | internal
    name         TEXT NOT NULL,
    requirement  TEXT NOT NULL DEFAULT '',
    reviewed_on  TEXT
);

-- 6.2 품질목표
CREATE TABLE IF NOT EXISTS quality_objective (
    id                INTEGER PRIMARY KEY,
    code              TEXT NOT NULL UNIQUE,
    description       TEXT NOT NULL,
    level             TEXT NOT NULL,      -- organization | process | project
    target_value      REAL,
    unit              TEXT NOT NULL DEFAULT '',
    indicator_code    TEXT,               -- 연계 PI
    resources         TEXT NOT NULL DEFAULT '',  -- 6.2.2 b)
    responsible_id    INTEGER REFERENCES person(id),  -- 6.2.2 c)
    due_on            TEXT,               -- 6.2.2 d)
    evaluation_method TEXT NOT NULL DEFAULT '',  -- 6.2.2 e)
    achieved          INTEGER,
    safety_related    INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------- 7.5 문서화된 정보
CREATE TABLE IF NOT EXISTS document (
    id               INTEGER PRIMARY KEY,
    doc_no           TEXT NOT NULL,
    title            TEXT NOT NULL,
    doc_type         TEXT NOT NULL,   -- policy|manual|procedure|instruction|template|record|external
    hierarchy_level  INTEGER NOT NULL,-- 7.5.3.3 b) 문서 계층
    version          TEXT NOT NULL,
    status           TEXT NOT NULL,   -- draft|in_review|approved|obsolete
    author_id        INTEGER REFERENCES person(id),
    verifier_id      INTEGER REFERENCES person(id),
    approver_id      INTEGER REFERENCES person(id),
    approved_on      TEXT,
    effective_from   TEXT,
    record_type      TEXT,            -- 7.5.3.3 d) 기록 유형
    retention_months INTEGER,         -- 7.5.3.3 d) 보존기간
    confidentiality  TEXT NOT NULL DEFAULT 'internal',
    content          TEXT NOT NULL DEFAULT '',
    seal             TEXT,            -- 7.5.3.2 무결성 봉인(해시)
    superseded_by    INTEGER REFERENCES document(id),
    disposed_on      TEXT,
    UNIQUE (doc_no, version)
);

CREATE TABLE IF NOT EXISTS document_event (
    id         INTEGER PRIMARY KEY,
    doc_id     INTEGER NOT NULL REFERENCES document(id),
    event      TEXT NOT NULL,
    actor_id   INTEGER REFERENCES person(id),
    occurred_on TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT ''
);

-- ------------------------------------------------------- 7.1.5 모니터링·측정 자원
CREATE TABLE IF NOT EXISTS measuring_resource (
    id                 INTEGER PRIMARY KEY,
    ident              TEXT NOT NULL UNIQUE,   -- 7.1.5.3 고유식별
    resource_type      TEXT NOT NULL,          -- 7.1.5.3 유형
    location           TEXT NOT NULL,          -- 7.1.5.3 위치/담당자
    custodian_id       INTEGER REFERENCES person(id),
    interval_months    INTEGER NOT NULL,       -- 7.1.5.3 교정·검증 주기
    last_calibrated_on TEXT,
    next_due_on        TEXT,
    status             TEXT NOT NULL DEFAULT 'ok',  -- ok|overdue|unfit|withdrawn
    used_in_special_process INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS calibration_record (
    id                 INTEGER PRIMARY KEY,
    resource_id        INTEGER NOT NULL REFERENCES measuring_resource(id),
    performed_on       TEXT NOT NULL,          -- 7.1.5.3 f)
    result             TEXT NOT NULL,          -- pass|fail
    reference_standard TEXT NOT NULL,          -- 7.1.5.3 g)
    procedure_ref      TEXT NOT NULL,          -- 7.1.5.3 h)
    internal           INTEGER NOT NULL DEFAULT 0,
    acceptance_criteria TEXT NOT NULL DEFAULT '',  -- 7.1.5.3 c)
    ambient_suitable   INTEGER NOT NULL DEFAULT 1, -- 7.1.5.3 d)
    performed_by_id    INTEGER REFERENCES person(id),
    retrospective_impact_assessed INTEGER NOT NULL DEFAULT 0  -- 7.1.5.2
);

-- ------------------------------------------------------------- 7.2 역량
CREATE TABLE IF NOT EXISTS competence_requirement (
    id               INTEGER PRIMARY KEY,
    task_code        TEXT NOT NULL,
    competence_code  TEXT NOT NULL,
    min_level        INTEGER NOT NULL,   -- 1 learner ~ 4 coach
    quality_or_safety_relevant INTEGER NOT NULL DEFAULT 0,
    UNIQUE (task_code, competence_code)
);

CREATE TABLE IF NOT EXISTS competence (
    id               INTEGER PRIMARY KEY,
    person_id        INTEGER NOT NULL REFERENCES person(id),
    competence_code  TEXT NOT NULL,
    level            INTEGER NOT NULL,
    evidence         TEXT NOT NULL DEFAULT '',
    valid_until      TEXT,
    UNIQUE (person_id, competence_code)
);

CREATE TABLE IF NOT EXISTS task_assignment (
    id          INTEGER PRIMARY KEY,
    person_id   INTEGER NOT NULL REFERENCES person(id),
    task_code   TEXT NOT NULL,
    assigned_on TEXT NOT NULL,
    UNIQUE (person_id, task_code)
);

-- 7.2.1.1 b) 역량 갭
CREATE TABLE IF NOT EXISTS competence_gap (
    id              INTEGER PRIMARY KEY,
    person_id       INTEGER NOT NULL REFERENCES person(id),
    competence_code TEXT NOT NULL,
    required_level  INTEGER NOT NULL,
    actual_level    INTEGER NOT NULL,
    action          TEXT NOT NULL DEFAULT '',
    due_on          TEXT,
    closed_on       TEXT
);

-- ------------------------------------------------- 6.1 리스크 및 기회 / 7.1.6 지식
CREATE TABLE IF NOT EXISTS risk_entry (
    id                 INTEGER PRIMARY KEY,
    ref_no             TEXT NOT NULL UNIQUE,
    kind               TEXT NOT NULL,      -- risk | opportunity
    scope              TEXT NOT NULL,      -- organization|process|project|tender|supply_chain|design|production
    scope_ref          TEXT NOT NULL DEFAULT '',
    description        TEXT NOT NULL,
    method             TEXT NOT NULL DEFAULT '',  -- FMEA|FMECA|SWOT 등
    likelihood         INTEGER NOT NULL,
    impact             INTEGER NOT NULL,
    rating             INTEGER NOT NULL,
    cost_benefit       TEXT NOT NULL DEFAULT '',  -- 8.1.3.9.1 b)
    action             TEXT NOT NULL DEFAULT '',
    action_owner_id    INTEGER REFERENCES person(id),
    due_on             TEXT,
    status             TEXT NOT NULL DEFAULT 'open',
    reviewed_on        TEXT,                      -- 6.1.3.1 b)
    effectiveness_note TEXT NOT NULL DEFAULT ''   -- 6.1.3.1 e)
);

CREATE TABLE IF NOT EXISTS lesson_learned (
    id             INTEGER PRIMARY KEY,
    source_type    TEXT NOT NULL,   -- nonconformity|audit|project|rams|complaint|benchmark
    source_ref     TEXT NOT NULL,
    description    TEXT NOT NULL,
    is_good_practice INTEGER NOT NULL DEFAULT 0,
    communicated_to TEXT NOT NULL DEFAULT '',
    created_on     TEXT NOT NULL
);

-- --------------------------------------------------------------- 7.4 의사소통
CREATE TABLE IF NOT EXISTS communication_entry (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,   -- plan | record
    topic        TEXT NOT NULL,   -- 7.4 a)
    timing       TEXT NOT NULL,   -- 7.4 b)
    audience     TEXT NOT NULL,   -- 7.4 c)
    method       TEXT NOT NULL,   -- 7.4 d)
    communicator TEXT NOT NULL,   -- 7.4 e)
    project_code TEXT,
    occurred_on  TEXT
);

-- ------------------------------------------------------------ 8.1.2 입찰 관리
CREATE TABLE IF NOT EXISTS tender (
    id                   INTEGER PRIMARY KEY,
    tender_no            TEXT NOT NULL UNIQUE,
    customer             TEXT NOT NULL,
    title                TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'draft',  -- draft|reviewed|approved|submitted|won|lost
    risk_entry_ref       TEXT,          -- 8.1.2 c)
    monetary_risk_eval   TEXT NOT NULL DEFAULT '',
    deliverable_cost_plan TEXT NOT NULL DEFAULT '',      -- 8.1.2 e)
    resource_plan        TEXT NOT NULL DEFAULT '',       -- 8.1.2 f)
    knowledge_input      TEXT NOT NULL DEFAULT '',       -- 8.1.2 d)
    control_extent       TEXT NOT NULL DEFAULT '',       -- 8.1.2 b)
    approved_by_id       INTEGER REFERENCES person(id),  -- 8.1.2 g)
    approved_on          TEXT,
    submitted_on         TEXT
);

-- --------------------------------------------- 8.2 제품·서비스 요구사항 관리
CREATE TABLE IF NOT EXISTS requirement (
    id                  INTEGER PRIMARY KEY,
    req_no              TEXT NOT NULL UNIQUE,
    owner_scope         TEXT NOT NULL,     -- tender | project | product
    owner_ref           TEXT NOT NULL,
    req_type            TEXT NOT NULL,     -- functional|performance|integration|non_functional|non_technical|rams|lcc|obsolescence|critical_characteristic
    text                TEXT NOT NULL,
    source              TEXT NOT NULL,     -- customer|statutory|organization|market
    reviewed            INTEGER NOT NULL DEFAULT 0,   -- 8.2.5 e) 1) 조항별 검토
    review_result       TEXT NOT NULL DEFAULT '',
    risk_assessed       INTEGER NOT NULL DEFAULT 0,   -- 8.2.5 e) 3)
    cascaded            INTEGER NOT NULL DEFAULT 0,   -- 8.2.5 e) 4)
    verifiable          INTEGER NOT NULL DEFAULT 0,   -- 8.2.5 e) 5)
    spec_doc_id         INTEGER REFERENCES document(id), -- 8.2.5 e) 6)
    verification_method TEXT NOT NULL DEFAULT '',
    validation_method   TEXT NOT NULL DEFAULT '',
    verified_on         TEXT,
    validated_on        TEXT,
    operational_maturity TEXT NOT NULL DEFAULT 'not_existing',
    superseded_by_change TEXT
);

-- ----------------------------------------------------- 8.1.3 프로젝트 관리
CREATE TABLE IF NOT EXISTS project (
    id                 INTEGER PRIMARY KEY,
    code               TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    customer           TEXT NOT NULL,
    tender_no          TEXT,
    phase              TEXT NOT NULL DEFAULT 'tender',
    status             TEXT NOT NULL DEFAULT 'active',  -- active|closed|cancelled
    budget             REAL NOT NULL DEFAULT 0,
    planned_margin_pct REAL NOT NULL DEFAULT 0,
    actual_margin_pct  REAL,
    start_on           TEXT,
    finish_on          TEXT,
    customer_delivery_on TEXT,
    critical_path      TEXT NOT NULL DEFAULT '',   -- 8.1.3.4 e)
    warranty_end_on    TEXT,
    multi_site         INTEGER NOT NULL DEFAULT 0,
    safety_related     INTEGER NOT NULL DEFAULT 0
);

-- 8.1.3.2 / .6 / .7 / .8 프로젝트 계획서류
CREATE TABLE IF NOT EXISTS project_plan (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES project(id),
    plan_kind    TEXT NOT NULL,  -- management|quality|hr|communication|configuration
    doc_id       INTEGER NOT NULL REFERENCES document(id),
    covers       TEXT NOT NULL DEFAULT '',  -- 필수 포함 항목(JSON)
    UNIQUE (project_id, plan_kind)
);

-- 8.1.3.3 c) 작업분할구조
CREATE TABLE IF NOT EXISTS work_package (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES project(id),
    wbs_code     TEXT NOT NULL,
    name         TEXT NOT NULL,
    owner_id     INTEGER REFERENCES person(id),  -- 8.1.3.3 d)
    duration_days INTEGER,
    start_on     TEXT,
    finish_on    TEXT,
    predecessors TEXT NOT NULL DEFAULT '',
    on_critical_path INTEGER NOT NULL DEFAULT 0,
    external_provider TEXT,
    verified_on  TEXT,                            -- 8.1.3.3 e)
    UNIQUE (project_id, wbs_code)
);

-- 8.1.3.1.1 d),e) 게이트 방식 단계검토
CREATE TABLE IF NOT EXISTS phase_review (
    id                  INTEGER PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES project(id),
    phase               TEXT NOT NULL,
    wbs_level           INTEGER NOT NULL DEFAULT 1,
    planned_on          TEXT,
    held_on             TEXT,
    decision            TEXT,     -- accepted|conditional|rejected
    mandatory_participants TEXT NOT NULL DEFAULT '',
    actual_participants TEXT NOT NULL DEFAULT '',
    gate_checklist_doc  INTEGER REFERENCES document(id),
    top_management_override_by INTEGER REFERENCES person(id),
    escalated           INTEGER NOT NULL DEFAULT 0,
    UNIQUE (project_id, phase)
);

-- 8.1.3.1.1 g) 미결사항
CREATE TABLE IF NOT EXISTS open_issue (
    id             INTEGER PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES project(id),
    phase_review_id INTEGER REFERENCES phase_review(id),
    description    TEXT NOT NULL,
    owner_id       INTEGER REFERENCES person(id),
    resource_note  TEXT NOT NULL DEFAULT '',
    raised_on      TEXT NOT NULL,
    due_on         TEXT,
    closed_on      TEXT
);

-- 8.1.3.11 프로젝트 검토
CREATE TABLE IF NOT EXISTS project_review (
    id             INTEGER PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES project(id),
    held_on        TEXT NOT NULL,
    performance    TEXT NOT NULL DEFAULT '',   -- 8.1.3.11 a)
    forecast       TEXT NOT NULL DEFAULT '',   -- 8.1.3.11 b)
    risk_status    TEXT NOT NULL DEFAULT '',   -- 8.1.3.11 c)
    open_issue_followup TEXT NOT NULL DEFAULT '', -- 8.1.3.11 d)
    core_team_present INTEGER NOT NULL DEFAULT 1,
    countermeasures TEXT NOT NULL DEFAULT '',
    reported_to    TEXT NOT NULL DEFAULT ''
);

-- 8.1.3.5 프로젝트 원가
CREATE TABLE IF NOT EXISTS project_cost (
    id            INTEGER PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES project(id),
    cost_account  TEXT NOT NULL,
    period        TEXT NOT NULL,
    budget        REAL NOT NULL DEFAULT 0,
    actual        REAL NOT NULL DEFAULT 0,
    estimate_at_completion REAL NOT NULL DEFAULT 0,
    UNIQUE (project_id, cost_account, period)
);

-- --------------------------------------- 8.1.4.1 형상관리 / 8.1.4.2 변경관리
CREATE TABLE IF NOT EXISTS config_item (
    id                 INTEGER PRIMARY KEY,
    project_id         INTEGER REFERENCES project(id),
    part_no            TEXT NOT NULL,
    name               TEXT NOT NULL,
    parent_id          INTEGER REFERENCES config_item(id),
    pbs_level          INTEGER NOT NULL DEFAULT 1,   -- 8.1.4.1.1 b)
    is_llru            INTEGER NOT NULL DEFAULT 0,
    safety_related     INTEGER NOT NULL DEFAULT 0,   -- 8.1.4.1.1 c)
    traceability_method TEXT NOT NULL DEFAULT '',    -- 8.1.4.1.1 g)
    is_tool            INTEGER NOT NULL DEFAULT 0,
    revision           TEXT NOT NULL DEFAULT 'A',
    UNIQUE (project_id, part_no)
);

CREATE TABLE IF NOT EXISTS baseline (
    id            INTEGER PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES project(id),
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL,   -- as_designed|as_built|as_maintained|test
    established_on TEXT NOT NULL,
    frozen        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS baseline_item (
    id             INTEGER PRIMARY KEY,
    baseline_id    INTEGER NOT NULL REFERENCES baseline(id),
    config_item_id INTEGER NOT NULL REFERENCES config_item(id),
    revision       TEXT NOT NULL,
    UNIQUE (baseline_id, config_item_id)
);

-- 8.1.4.1.1 f) 형상상태 기록
CREATE TABLE IF NOT EXISTS config_status_record (
    id             INTEGER PRIMARY KEY,
    baseline_id    INTEGER NOT NULL REFERENCES baseline(id),
    config_item_id INTEGER NOT NULL REFERENCES config_item(id),
    from_revision  TEXT,
    to_revision    TEXT NOT NULL,
    change_no      TEXT,
    recorded_on    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS change_request (
    id                  INTEGER PRIMARY KEY,
    change_no           TEXT NOT NULL UNIQUE,
    scope               TEXT NOT NULL,  -- project_scope|project_schedule|project_budget|requirement|design|configuration|production|process_transfer|supplier
    target_ref          TEXT NOT NULL,
    description         TEXT NOT NULL,
    origin              TEXT NOT NULL DEFAULT 'internal',  -- internal|customer|external_provider
    technical           INTEGER NOT NULL DEFAULT 0,
    cause_analysis      TEXT NOT NULL DEFAULT '',   -- 8.1.4.2 c)
    impact_analysis     TEXT NOT NULL DEFAULT '',   -- 8.1.4.2 d)
    impact_on_delivered TEXT NOT NULL DEFAULT '',   -- 8.1.4.2 l) 1)
    proposal_verified   INTEGER NOT NULL DEFAULT 0, -- 8.1.4.2 e)
    customer_impact     INTEGER NOT NULL DEFAULT 0, -- 8.1.4.2 f)
    customer_notified_on TEXT,
    customer_agreed_on  TEXT,
    provider_notified_on TEXT,
    approver_id         INTEGER REFERENCES person(id),  -- 8.1.4.2 g)
    approved_on         TEXT,                       -- 8.1.4.2 h)
    implemented_on      TEXT,                       -- 8.1.4.2 i)
    implementation_verified_on TEXT,                -- 8.1.4.2 j)
    effectiveness_on    TEXT,
    revalidation_note   TEXT NOT NULL DEFAULT '',   -- 8.1.4.2 n)
    affected_serials    TEXT NOT NULL DEFAULT '',   -- 8.1.4.2 o)
    status              TEXT NOT NULL DEFAULT 'raised'
);

-- ------------------------------------------------------- 8.3 설계 및 개발
CREATE TABLE IF NOT EXISTS design (
    id                   INTEGER PRIMARY KEY,
    design_no            TEXT NOT NULL UNIQUE,
    project_id           INTEGER REFERENCES project(id),
    item                 TEXT NOT NULL,
    architecture_level   TEXT NOT NULL DEFAULT 'component',  -- component|subsystem|system
    stage                TEXT NOT NULL DEFAULT 'conceptual', -- conceptual|preliminary|final
    plan_doc_id          INTEGER REFERENCES document(id),
    inputs_complete      INTEGER NOT NULL DEFAULT 0,   -- 8.3.3
    input_conflicts_resolved INTEGER NOT NULL DEFAULT 0,
    new_technology       INTEGER NOT NULL DEFAULT 0,   -- 8.3.1.1
    safety_related       INTEGER NOT NULL DEFAULT 0,
    safety_standard      TEXT NOT NULL DEFAULT '',     -- 8.3.1.1 d) / 8.8.3
    safety_case_doc_id   INTEGER REFERENCES document(id),
    verified_on          TEXT,                         -- 8.3.4.3
    validated_on         TEXT,                         -- 8.3.4.4
    validation_waiver_agreed_on TEXT,                  -- 8.3.4.4 b) 고객 합의 관리계획
    output_approved_by_id INTEGER REFERENCES person(id),
    output_released_on   TEXT,                         -- 8.3.5.1.1 a)
    production_input_verified_on TEXT                  -- 8.3.5.1.1 b)
);

CREATE TABLE IF NOT EXISTS design_review (
    id                    INTEGER PRIMARY KEY,
    design_id             INTEGER NOT NULL REFERENCES design(id),
    level                 TEXT NOT NULL,
    held_on               TEXT NOT NULL,
    acceptance_criteria   TEXT NOT NULL,     -- 8.3.4.2 a)
    mandatory_participants TEXT NOT NULL,    -- 8.3.4.2 b)
    actual_participants   TEXT NOT NULL,
    decision_authority_present INTEGER NOT NULL DEFAULT 0,
    multidisciplinary     INTEGER NOT NULL DEFAULT 0,
    decision              TEXT NOT NULL      -- accepted|conditional|rejected
);

-- 8.3.4.5 검증·유효성확인 시험
CREATE TABLE IF NOT EXISTS design_test (
    id                  INTEGER PRIMARY KEY,
    design_id           INTEGER NOT NULL REFERENCES design(id),
    kind                TEXT NOT NULL,  -- verification|validation
    plan_doc_id         INTEGER REFERENCES document(id),
    objectives          TEXT NOT NULL DEFAULT '',
    conditions          TEXT NOT NULL DEFAULT '',
    product_under_test  TEXT NOT NULL DEFAULT '',
    resources           TEXT NOT NULL DEFAULT '',
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    recorded_parameters TEXT NOT NULL DEFAULT '',
    method              TEXT NOT NULL DEFAULT '',
    baseline_id         INTEGER REFERENCES baseline(id),  -- 8.3.4.5 b)
    performed_on        TEXT,
    result              TEXT,   -- pass|fail
    criteria_met        INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------- 8.4 외부공급 관리
CREATE TABLE IF NOT EXISTS supplier (
    id                    INTEGER PRIMARY KEY,
    code                  TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    classification        TEXT NOT NULL DEFAULT 'standard',  -- key|standard|commodity
    classification_reviewed_on TEXT,                          -- 8.4.1.1.2
    evaluated_on          TEXT,                               -- 8.4.1.1.3
    evaluation_note       TEXT NOT NULL DEFAULT '',
    certifications        TEXT NOT NULL DEFAULT '',           -- 8.4.1.1.3 b)
    targeted              INTEGER NOT NULL DEFAULT 0,         -- 8.4.1.1.3 c),d)
    approved              INTEGER NOT NULL DEFAULT 0,         -- 8.4.1.1.4
    approval_scope        TEXT NOT NULL DEFAULT '',
    approved_on           TEXT,
    approved_by_id        INTEGER REFERENCES person(id),
    rejected_on           TEXT,
    performance_reviewed_on TEXT,                              -- 8.4.2.3 a)
    performance_score     REAL,
    ranking               TEXT NOT NULL DEFAULT '',
    development_plan      TEXT NOT NULL DEFAULT ''             -- 8.4.2.3 h)
);

-- 8.4.2.2 검증활동 위임 등록부
CREATE TABLE IF NOT EXISTS verification_delegation (
    id                INTEGER PRIMARY KEY,
    supplier_id       INTEGER NOT NULL REFERENCES supplier(id),
    scope             TEXT NOT NULL,
    requirements      TEXT NOT NULL,
    supplier_acceptance_evidence TEXT NOT NULL,
    control_measure   TEXT NOT NULL DEFAULT '',
    granted_on        TEXT NOT NULL,
    reviewed_on       TEXT
);

CREATE TABLE IF NOT EXISTS purchase_order (
    id                 INTEGER PRIMARY KEY,
    po_no              TEXT NOT NULL UNIQUE,
    supplier_id        INTEGER NOT NULL REFERENCES supplier(id),
    project_id         INTEGER REFERENCES project(id),
    item               TEXT NOT NULL,
    config_item_id     INTEGER REFERENCES config_item(id),
    qty                REAL NOT NULL,
    required_on        TEXT,
    criticality        TEXT NOT NULL DEFAULT 'standard',  -- 8.4.3.1 h)
    requirements_communicated TEXT NOT NULL DEFAULT '',   -- 8.4.3 / 8.4.3.1
    special_process_approval TEXT NOT NULL DEFAULT '',
    acknowledged_on    TEXT,                              -- 8.4.4 a)
    status             TEXT NOT NULL DEFAULT 'issued',
    is_new_or_modified INTEGER NOT NULL DEFAULT 0
);

-- 8.4.2.1 EPPPS 출시 승인
CREATE TABLE IF NOT EXISTS eppps_release (
    id              INTEGER PRIMARY KEY,
    po_id           INTEGER NOT NULL REFERENCES purchase_order(id),
    approval_method TEXT NOT NULL,
    fai_id          INTEGER REFERENCES fai(id),
    validated_before_first_use INTEGER NOT NULL DEFAULT 0,
    baseline_id     INTEGER REFERENCES baseline(id),
    approved_on     TEXT,
    approved_by_id  INTEGER REFERENCES person(id)
);

-- 8.4.2.2 출시 후 검증(인수검사)
CREATE TABLE IF NOT EXISTS incoming_inspection (
    id             INTEGER PRIMARY KEY,
    po_id          INTEGER NOT NULL REFERENCES purchase_order(id),
    planned_extent TEXT NOT NULL DEFAULT '',
    performed_on   TEXT,
    result         TEXT,      -- pass|fail
    evidence       TEXT NOT NULL DEFAULT '',
    released_by_id INTEGER REFERENCES person(id),
    concession_id  INTEGER REFERENCES concession(id),
    delegated      INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------- 8.5 생산 및 서비스 제공
CREATE TABLE IF NOT EXISTS special_process (
    id                   INTEGER PRIMARY KEY,
    code                 TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    applicable_standard  TEXT NOT NULL DEFAULT '',   -- 8.5.1.3 b) 2)
    risk_assessment      TEXT NOT NULL DEFAULT '',   -- 8.5.1.3 b) 3)
    work_instruction_doc_id INTEGER REFERENCES document(id),
    owner_id             INTEGER REFERENCES person(id),
    qualified_on         TEXT,                        -- 8.5.1.3 b) 7)
    qualification_valid_until TEXT,
    revalidation_note    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS special_process_operator (
    id             INTEGER PRIMARY KEY,
    special_process_code TEXT NOT NULL REFERENCES special_process(code),
    person_id      INTEGER NOT NULL REFERENCES person(id),
    qualified_until TEXT NOT NULL,
    UNIQUE (special_process_code, person_id)
);

CREATE TABLE IF NOT EXISTS production_equipment (
    id                    INTEGER PRIMARY KEY,
    ident                 TEXT NOT NULL UNIQUE,   -- 8.5.1.4.1 b) 3)
    name                  TEXT NOT NULL,
    validated_before_first_use_on TEXT,           -- 8.5.1.4.1 b) 2)
    acceptance_criteria   TEXT NOT NULL DEFAULT '',
    verification_interval_months INTEGER NOT NULL DEFAULT 12,
    last_verified_on      TEXT,
    next_verification_on  TEXT,
    condition_checked_on  TEXT,                    -- 8.5.1.4.1 b) 5)
    preventive_plan       TEXT NOT NULL DEFAULT '',
    spare_parts_secured   INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS equipment_maintenance (
    id           INTEGER PRIMARY KEY,
    equipment_id INTEGER NOT NULL REFERENCES production_equipment(id),
    performed_on TEXT NOT NULL,
    kind         TEXT NOT NULL,   -- preventive|corrective|predictive|verification
    result       TEXT NOT NULL DEFAULT '',
    downtime_hours REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS production_order (
    id                 INTEGER PRIMARY KEY,
    order_no           TEXT NOT NULL UNIQUE,
    project_id         INTEGER REFERENCES project(id),
    config_item_id     INTEGER REFERENCES config_item(id),
    item               TEXT NOT NULL,
    qty                REAL NOT NULL,
    approved_data_doc_id INTEGER REFERENCES document(id),  -- 8.5.1.1.2 a)
    tool_program_list  TEXT NOT NULL DEFAULT '',           -- 8.5.1.1.2 a) 2)
    itp_doc_id         INTEGER REFERENCES document(id),     -- 8.6.1 a)
    risk_assessment    TEXT NOT NULL DEFAULT '',            -- 8.5.1.1.2 e)
    special_process_codes TEXT NOT NULL DEFAULT '',
    process_verified_on TEXT,                               -- 8.5.1.1.3
    process_validated_on TEXT,                              -- 8.5.1.1.4
    fai_id             INTEGER REFERENCES fai(id),
    is_first_run       INTEGER NOT NULL DEFAULT 0,
    serial_production_released_on TEXT,
    status             TEXT NOT NULL DEFAULT 'planned',     -- planned|released|in_progress|completed
    scheduled_start_on TEXT,
    scheduled_finish_on TEXT,
    shift              TEXT NOT NULL DEFAULT 'day'
);

-- 8.5.2 식별 및 추적성
CREATE TABLE IF NOT EXISTS traceable_item (
    id                  INTEGER PRIMARY KEY,
    serial_no           TEXT NOT NULL UNIQUE,
    config_item_id      INTEGER REFERENCES config_item(id),
    production_order_id INTEGER REFERENCES production_order(id),
    identification_method TEXT NOT NULL DEFAULT '',  -- 8.5.2.1
    traceability_required INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'in_process',
        -- in_process|inspected|released|delivered|nonconforming|unknown|scrapped
    warranty_end_on     TEXT,                        -- 8.5.2.1
    delivered_on        TEXT
);

-- 8.5.3 고객·외부공급자 소유물
CREATE TABLE IF NOT EXISTS external_property (
    id            INTEGER PRIMARY KEY,
    ref_no        TEXT NOT NULL UNIQUE,
    owner_kind    TEXT NOT NULL,   -- customer|external_provider
    owner_name    TEXT NOT NULL,
    description   TEXT NOT NULL,
    received_on   TEXT NOT NULL,
    verified_on   TEXT,
    protection_measure TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'held',   -- held|returned|delivered|lost|damaged
    reported_on   TEXT,
    cause_analysis TEXT NOT NULL DEFAULT '',
    returned_on   TEXT
);

-- 8.5.4.1 보존 규격
CREATE TABLE IF NOT EXISTS preservation_spec (
    id                INTEGER PRIMARY KEY,
    config_item_id    INTEGER REFERENCES config_item(id),
    scope             TEXT NOT NULL,
    marking           TEXT NOT NULL,        -- 8.5.4.1 a)
    special_handling  TEXT NOT NULL,        -- 8.5.4.1 b)
    cleaning          TEXT NOT NULL,        -- 8.5.4.1 c)
    shelf_life_control TEXT NOT NULL,       -- 8.5.4.1 d)
    environment       TEXT NOT NULL,        -- 8.5.4.1 e)
    doc_id            INTEGER REFERENCES document(id)
);

-- 8.6 출하 / 8.6.1 검사·시험
CREATE TABLE IF NOT EXISTS inspection (
    id                  INTEGER PRIMARY KEY,
    production_order_id INTEGER REFERENCES production_order(id),
    traceable_item_id   INTEGER REFERENCES traceable_item(id),
    itp_step            TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,          -- 8.6.1 d)
    planned             INTEGER NOT NULL DEFAULT 1,
    performed_on        TEXT,
    result              TEXT,                   -- pass|fail
    actual_data         TEXT NOT NULL DEFAULT '',  -- 8.6.1 e)
    inspector_id        INTEGER REFERENCES person(id),
    measuring_resource_id INTEGER REFERENCES measuring_resource(id)  -- 8.6.1 f)
);

CREATE TABLE IF NOT EXISTS release_record (
    id                INTEGER PRIMARY KEY,
    traceable_item_id INTEGER NOT NULL REFERENCES traceable_item(id),
    released_on       TEXT NOT NULL,
    authorized_by_id  INTEGER NOT NULL REFERENCES person(id),  -- 8.6 b) / 8.6.1 c)
    conformity_evidence TEXT NOT NULL,                          -- 8.6 a)
    concession_id     INTEGER REFERENCES concession(id)
);

-- ------------------------------------------- 8.7 부적합 / 10.2 시정조치
CREATE TABLE IF NOT EXISTS nonconformity (
    id                INTEGER PRIMARY KEY,
    nc_no             TEXT NOT NULL UNIQUE,
    source            TEXT NOT NULL,   -- internal|customer|external_provider|process|project|design
    detected_at_stage TEXT NOT NULL DEFAULT '',
    ref               TEXT NOT NULL DEFAULT '',
    traceable_item_id INTEGER REFERENCES traceable_item(id),
    supplier_id       INTEGER REFERENCES supplier(id),
    description       TEXT NOT NULL,
    detected_on       TEXT NOT NULL,
    qty               REAL NOT NULL DEFAULT 0,
    disposition       TEXT,   -- correction|rework|repair|scrap|segregate|return|concession
    disposition_authority_id INTEGER REFERENCES person(id),  -- 8.7.2 d)
    customer_informed_on TEXT,                                -- 8.7.1 c)
    corrected_verified_on TEXT,                               -- 8.7.1
    concession_id     INTEGER REFERENCES concession(id),
    capa_id           INTEGER REFERENCES capa(id),
    capa_needed       INTEGER,                                 -- 10.2.3 b)
    capa_decision_note TEXT NOT NULL DEFAULT '',
    cost              REAL NOT NULL DEFAULT 0,
    safety_impact     INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'open'
);

-- 8.7.3 d) 특채 등록부
CREATE TABLE IF NOT EXISTS concession (
    id                    INTEGER PRIMARY KEY,
    concession_no         TEXT NOT NULL UNIQUE,
    kind                  TEXT NOT NULL,   -- internal|customer|external_provider
    nonconformity_id      INTEGER REFERENCES nonconformity(id),
    description           TEXT NOT NULL,
    qty_authorized        REAL NOT NULL,
    qty_used              REAL NOT NULL DEFAULT 0,
    valid_until           TEXT NOT NULL,
    internally_approved_on TEXT,
    internally_approved_by_id INTEGER REFERENCES person(id),
    customer_approval_required INTEGER NOT NULL DEFAULT 0,
    customer_approved_on  TEXT,
    identification_agreed INTEGER NOT NULL DEFAULT 0,   -- 8.7.3 g) 3)
    recorded_on_doc       TEXT NOT NULL DEFAULT '',     -- 8.7.3 g) 4)
    status                TEXT NOT NULL DEFAULT 'open'  -- open|expired|closed
);

CREATE TABLE IF NOT EXISTS capa (
    id                 INTEGER PRIMARY KEY,
    capa_no            TEXT NOT NULL UNIQUE,
    source_type        TEXT NOT NULL,  -- nonconformity|complaint|audit|kpi|rams|process_review|management_review
    source_ref         TEXT NOT NULL,
    description        TEXT NOT NULL,
    criteria_applied   TEXT NOT NULL,           -- 10.2.3 b)
    method             TEXT NOT NULL,           -- 4D|8D|FRACAS
    root_cause         TEXT NOT NULL DEFAULT '',
    similar_checked    INTEGER NOT NULL DEFAULT 0,  -- 10.2.1 b) 3)
    actions            TEXT NOT NULL DEFAULT '',
    owner_id           INTEGER REFERENCES person(id),
    escalation_level   INTEGER NOT NULL DEFAULT 0,  -- 10.2.3 e)
    escalated_to       TEXT NOT NULL DEFAULT '',
    opened_on          TEXT NOT NULL,
    due_on             TEXT,
    closed_on          TEXT,
    effectiveness_reviewed_on TEXT,               -- 10.2.1 d)
    effective          INTEGER,
    risk_updated       INTEGER NOT NULL DEFAULT 0, -- 10.2.1 e)
    status             TEXT NOT NULL DEFAULT 'open'
);

-- --------------------------------------------- 8.8 RAMS / LCC, 8.9 FAI, 8.10 단산
CREATE TABLE IF NOT EXISTS rams_objective (
    id            INTEGER PRIMARY KEY,
    product       TEXT NOT NULL,
    metric        TEXT NOT NULL,   -- MTBF|MTTR|availability|SIL
    target        REAL NOT NULL,
    unit          TEXT NOT NULL DEFAULT '',
    direction     TEXT NOT NULL DEFAULT 'higher_is_better',
    calculated    REAL,
    calculated_at_stage TEXT NOT NULL DEFAULT 'tender',  -- 8.8.2 a)
    field_value   REAL,
    period        TEXT NOT NULL DEFAULT '',
    analysis      TEXT NOT NULL DEFAULT '',
    capa_id       INTEGER REFERENCES capa(id),
    feedback_to_design TEXT NOT NULL DEFAULT '',   -- 8.8.2 e)
    feedback_to_provider TEXT NOT NULL DEFAULT '', -- 8.8.2 f)
    applicable_standard TEXT NOT NULL DEFAULT '',
    UNIQUE (product, metric, period)
);

-- 8.8.2 c) 현장 데이터 수집
CREATE TABLE IF NOT EXISTS field_data (
    id              INTEGER PRIMARY KEY,
    product         TEXT NOT NULL,
    serial_no       TEXT,
    occurred_on     TEXT NOT NULL,
    failure_symptom TEXT NOT NULL,
    failure_category TEXT NOT NULL DEFAULT '',
    component       TEXT NOT NULL DEFAULT '',
    severity        TEXT NOT NULL DEFAULT '',
    mileage_km      REAL,
    operating_hours REAL,
    repair_cost     REAL NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'maintenance_contract'
);

CREATE TABLE IF NOT EXISTS lcc_record (
    id          INTEGER PRIMARY KEY,
    product     TEXT NOT NULL,
    period      TEXT NOT NULL,
    perspective TEXT NOT NULL DEFAULT 'manufacturer',
    calculated  REAL NOT NULL,
    actual      REAL,
    analysis    TEXT NOT NULL DEFAULT '',
    UNIQUE (product, period)
);

CREATE TABLE IF NOT EXISTS safety_record (
    id                 INTEGER PRIMARY KEY,
    product            TEXT NOT NULL,
    sil_level          TEXT NOT NULL DEFAULT '',
    applicable_standards TEXT NOT NULL,     -- 8.8.3 (IEC 62278/62425/62279 등)
    safety_case_doc_id INTEGER REFERENCES document(id),
    hazard_log         TEXT NOT NULL DEFAULT '',
    assessed_on        TEXT,
    UNIQUE (product)
);

CREATE TABLE IF NOT EXISTS fai (
    id                 INTEGER PRIMARY KEY,
    fai_no             TEXT NOT NULL UNIQUE,
    target_kind        TEXT NOT NULL,  -- internal_product|eppps|production_equipment|process_transfer
    target_ref         TEXT NOT NULL,
    trigger            TEXT NOT NULL,  -- new_product|significant_change|process_verification|invalidated_fai|transfer
    plan_doc_id        INTEGER REFERENCES document(id),
    preconditions_ok   INTEGER NOT NULL DEFAULT 0,  -- 8.9.2 a)
    participants       TEXT NOT NULL DEFAULT '',    -- 8.9.2 b)
    inspection_done_on TEXT,                        -- 8.9.1 c)
    process_review_done INTEGER NOT NULL DEFAULT 0, -- 8.9.1 c)
    representative_serial TEXT NOT NULL DEFAULT '', -- 8.9.3 b)
    decision           TEXT,   -- approved|conditional|rejected
    decided_on         TEXT,
    decided_by_id      INTEGER REFERENCES person(id),
    capa_id            INTEGER REFERENCES capa(id)  -- 8.9.1 e)
);

CREATE TABLE IF NOT EXISTS obsolescence_plan (
    id            INTEGER PRIMARY KEY,
    product       TEXT NOT NULL UNIQUE,
    version       TEXT NOT NULL,
    strategy      TEXT NOT NULL DEFAULT '',
    support_until TEXT NOT NULL,
    doc_id        INTEGER REFERENCES document(id),
    reviewed_on   TEXT,
    next_review_on TEXT
);

CREATE TABLE IF NOT EXISTS obsolescence_risk (
    id              INTEGER PRIMARY KEY,
    config_item_id  INTEGER REFERENCES config_item(id),
    part_no         TEXT NOT NULL,
    product         TEXT NOT NULL,
    risk_level      TEXT NOT NULL,   -- high|medium|low
    issue_kind      TEXT NOT NULL DEFAULT 'technical',  -- technical|functional|knowledge
    assessed_on     TEXT NOT NULL,
    mitigation      TEXT NOT NULL DEFAULT '',
    mitigated_on    TEXT,
    customer_communicated_on TEXT,
    status          TEXT NOT NULL DEFAULT 'open'
);

-- 8.1.1.2 프로세스 이전
CREATE TABLE IF NOT EXISTS process_transfer (
    id                    INTEGER PRIMARY KEY,
    transfer_no           TEXT NOT NULL UNIQUE,
    process_code          TEXT NOT NULL,
    from_site             TEXT NOT NULL,
    to_site               TEXT NOT NULL,
    external              INTEGER NOT NULL DEFAULT 0,
    feasibility_study     TEXT NOT NULL DEFAULT '',   -- 8.1.1.2 a)
    risk_entry_ref        TEXT NOT NULL DEFAULT '',   -- 8.1.1.2 b)
    action_plan           TEXT NOT NULL DEFAULT '',   -- 8.1.1.2 c)
    customer_communicated_on TEXT,                    -- 8.1.1.2 d)
    fai_id                INTEGER REFERENCES fai(id), -- 8.1.1.2 e)
    change_no             TEXT,
    approved_on           TEXT,
    status                TEXT NOT NULL DEFAULT 'planned'
);

-- 8.5.5 인도 후 활동
CREATE TABLE IF NOT EXISTS post_delivery_activity (
    id                 INTEGER PRIMARY KEY,
    ref_no             TEXT NOT NULL UNIQUE,
    product            TEXT NOT NULL,
    customer           TEXT NOT NULL,
    activity_kind      TEXT NOT NULL,  -- warranty|maintenance|training|spare_parts|disposal
    performed_on       TEXT,
    technical_doc_id   INTEGER REFERENCES document(id),  -- 8.5.5.1 b)
    repair_instruction_doc_id INTEGER REFERENCES document(id),  -- 8.5.5.1 d)
    problem_solving_method TEXT NOT NULL DEFAULT '',     -- 8.5.5.1 c)
    consignment_stock  TEXT NOT NULL DEFAULT '',         -- 8.5.5.1 e)
    feedback_to_rqms   TEXT NOT NULL DEFAULT ''          -- 8.5.5.1 f)
);

-- ---------------------------------------------- 9.1 성과지표 / 고객만족
CREATE TABLE IF NOT EXISTS indicator_measurement (
    id              INTEGER PRIMARY KEY,
    indicator_code  TEXT NOT NULL,
    period          TEXT NOT NULL,
    value           REAL NOT NULL,
    target          REAL NOT NULL,
    met             INTEGER NOT NULL,
    analysis        TEXT NOT NULL DEFAULT '',
    trend           TEXT NOT NULL DEFAULT '',
    shared_with     TEXT NOT NULL DEFAULT '',   -- 9.1.3.1
    capa_id         INTEGER REFERENCES capa(id),
    recorded_on     TEXT NOT NULL,
    UNIQUE (indicator_code, period)
);

CREATE TABLE IF NOT EXISTS complaint (
    id               INTEGER PRIMARY KEY,
    complaint_no     TEXT NOT NULL UNIQUE,
    customer         TEXT NOT NULL,
    description      TEXT NOT NULL,
    received_on      TEXT NOT NULL,
    acknowledged_on  TEXT,                       -- 9.1.2.1 b)
    capa_id          INTEGER REFERENCES capa(id),
    nonconformity_id INTEGER REFERENCES nonconformity(id),
    response_on      TEXT,
    resolved_on      TEXT,
    lesson_shared    INTEGER NOT NULL DEFAULT 0  -- 9.1.2.1 a)
);

CREATE TABLE IF NOT EXISTS customer_satisfaction (
    id        INTEGER PRIMARY KEY,
    customer  TEXT NOT NULL,
    period    TEXT NOT NULL,
    method    TEXT NOT NULL,
    score     REAL NOT NULL,
    note      TEXT NOT NULL DEFAULT '',
    UNIQUE (customer, period)
);

-- --------------------------------------------------------- 9.2 내부심사
CREATE TABLE IF NOT EXISTS audit_programme (
    id           INTEGER PRIMARY KEY,
    year         INTEGER NOT NULL UNIQUE,
    approved_on  TEXT,
    reviewed_on  TEXT,                     -- 9.2.3.2 3년 프로그램 연간 검토
    multidisciplinary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auditor (
    id                  INTEGER PRIMARY KEY,
    person_id           INTEGER NOT NULL UNIQUE REFERENCES person(id),
    knows_audit_principles INTEGER NOT NULL DEFAULT 0,  -- 9.2.3.3.1 a) 1)
    scope_knowledge     TEXT NOT NULL DEFAULT '',        -- 9.2.3.3.1 a) 2)
    clause_knowledge    TEXT NOT NULL DEFAULT '',        -- 9.2.3.3.1 a) 3)
    criteria_knowledge  TEXT NOT NULL DEFAULT '',        -- 9.2.3.3.1 a) 4)
    audits_performed    INTEGER NOT NULL DEFAULT 0,      -- 9.2.3.3.1 b)
    refresh_training_on TEXT,
    home_processes      TEXT NOT NULL DEFAULT ''         -- 9.2.3.2 d) 자기업무 판정용
);

CREATE TABLE IF NOT EXISTS internal_audit (
    id             INTEGER PRIMARY KEY,
    audit_no       TEXT NOT NULL UNIQUE,
    programme_id   INTEGER REFERENCES audit_programme(id),
    process_code   TEXT,
    project_code   TEXT,
    scope          TEXT NOT NULL,
    criteria       TEXT NOT NULL,          -- 9.2.2 b)
    planned_on     TEXT NOT NULL,
    performed_on   TEXT,
    lead_auditor_id INTEGER REFERENCES person(id),
    team           TEXT NOT NULL DEFAULT '',
    shifts_covered TEXT NOT NULL DEFAULT '',  -- 9.2.3.2 e)
    report_doc_id  INTEGER REFERENCES document(id),
    reported_to    TEXT NOT NULL DEFAULT '',  -- 9.2.2 d)
    status         TEXT NOT NULL DEFAULT 'planned'
);

CREATE TABLE IF NOT EXISTS audit_finding (
    id          INTEGER PRIMARY KEY,
    audit_id    INTEGER NOT NULL REFERENCES internal_audit(id),
    clause_id   TEXT NOT NULL,
    grade       TEXT NOT NULL,   -- major|minor|observation|opportunity
    description TEXT NOT NULL,
    capa_id     INTEGER REFERENCES capa(id)
);

-- ------------------------------------------ 9.3 경영검토 / 9.4 프로세스 검토
CREATE TABLE IF NOT EXISTS management_review (
    id          INTEGER PRIMARY KEY,
    ref_no      TEXT NOT NULL UNIQUE,
    review_kind TEXT NOT NULL DEFAULT 'annual',  -- annual|extraordinary
    trigger     TEXT NOT NULL DEFAULT '',
    held_on     TEXT NOT NULL,
    attendees   TEXT NOT NULL DEFAULT '',
    inputs      TEXT NOT NULL DEFAULT '{}',      -- 9.3.2 / 9.3.2.1 (JSON)
    outputs     TEXT NOT NULL DEFAULT '{}',      -- 9.3.3 / 9.3.3.1 (JSON)
    doc_id      INTEGER REFERENCES document(id)
);

CREATE TABLE IF NOT EXISTS process_review (
    id                INTEGER PRIMARY KEY,
    process_code      TEXT NOT NULL REFERENCES process_instance(code),
    held_on           TEXT NOT NULL,
    owner_id          INTEGER REFERENCES person(id),     -- 9.4 h)
    participants      TEXT NOT NULL DEFAULT '',
    conformity_note   TEXT NOT NULL DEFAULT '',          -- 9.4 a)
    previous_actions  TEXT NOT NULL DEFAULT '',          -- 9.4 b)
    nonconforming_outputs TEXT NOT NULL DEFAULT '',      -- 9.4 c)
    resources_note    TEXT NOT NULL DEFAULT '',          -- 9.4 d)
    pi_analysis       TEXT NOT NULL DEFAULT '',          -- 9.4 e)
    pi_relevance_note TEXT NOT NULL DEFAULT '',          -- 9.4 f)
    audit_capa_note   TEXT NOT NULL DEFAULT '',          -- 9.4 g)
    interested_party_input TEXT NOT NULL DEFAULT '',     -- 9.4 i)
    decisions         TEXT NOT NULL DEFAULT '',          -- 9.4 j)
    reported_to_top_management INTEGER NOT NULL DEFAULT 0,  -- 9.4 k)
    doc_id            INTEGER REFERENCES document(id)
);

-- --------------------------------------------------------- 10.1 개선 / 혁신
CREATE TABLE IF NOT EXISTS improvement (
    id           INTEGER PRIMARY KEY,
    ref_no       TEXT NOT NULL UNIQUE,
    kind         TEXT NOT NULL,   -- correction|corrective_action|continual|breakthrough|innovation|reorganization
    description  TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    owner_id     INTEGER REFERENCES person(id),
    opened_on    TEXT NOT NULL,
    closed_on    TEXT,
    benefit_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS innovation (
    id            INTEGER PRIMARY KEY,
    ref_no        TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    business_env_change TEXT NOT NULL DEFAULT '',  -- 8.1.1.1 a)
    priority      INTEGER NOT NULL DEFAULT 3,      -- 8.1.1.1 c)
    resources     TEXT NOT NULL DEFAULT '',
    stakeholders  TEXT NOT NULL DEFAULT '',        -- 8.1.1.1 d)
    status        TEXT NOT NULL DEFAULT 'proposed'
);

-- ------------------------------------------------------------- 통제 위반 로그
CREATE TABLE IF NOT EXISTS control_violation_log (
    id          INTEGER PRIMARY KEY,
    control_id  TEXT NOT NULL,
    clauses     TEXT NOT NULL,
    context     TEXT NOT NULL,
    message     TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nc_status ON nonconformity(status);
CREATE INDEX IF NOT EXISTS idx_capa_status ON capa(status);
CREATE INDEX IF NOT EXISTS idx_audit_process ON internal_audit(process_code);
CREATE INDEX IF NOT EXISTS idx_meas_indicator ON indicator_measurement(indicator_code);
CREATE INDEX IF NOT EXISTS idx_open_issue_project ON open_issue(project_id, closed_on);
CREATE INDEX IF NOT EXISTS idx_item_status ON traceable_item(status);
