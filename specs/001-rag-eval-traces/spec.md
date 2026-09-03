# Feature Specification: RAG eval and local traces

**Feature Branch**: `001-rag-eval-traces`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Specify from `docs/` (vision, principles, learning path, module 13, ADR 0006 and ADR 0007): know whether the sourced chat hallucinates, refuses too often, or fails on hard questions; versioned eval set; deterministic scores; optional local traces; never send the press corpus off-machine by default."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repeatable RAG quality check without a second judge (Priority: P1)

An operator who maintains the sourced chat needs to know, after changing retrieve depth or the local model, whether answers still refuse when the lake has nothing relevant and still ground when the corpus has material. They run a named, versioned set of questions shipped with the product. Each case has an expected outcome (`grounded` or `refuse`) and a difficulty (`one_shot` or `hard`). Scoring is mechanical and repeatable: empty vs non-empty retrieve, explicit refuse, presence of inline citations. They can run retrieve-and-score without calling the language model, so continuous integration and empty-lake debugging still work.

**Why this priority**: Without this, regressions are invisible and the product cannot claim “evaluated RAG”. This slice is useful even if tracing is never turned on.

**Independent Test**: Load the versioned eval set, run scoring with language-model generation skipped, and obtain a pass/fail report that includes refuse cases (which must be scorable without a populated lake).

**Acceptance Scenarios**:

1. **Given** the versioned eval set is present, **When** the operator runs evaluation with generation skipped, **Then** every `refuse` case is scored and the report lists pass or fail per case.
2. **Given** the lake indexes are empty, **When** the operator runs evaluation with generation skipped, **Then** `refuse` cases can still pass and `grounded` cases fail in a way that names empty retrieve rather than crashing.
3. **Given** a case expects `grounded` and retrieve returns at least one passage, **When** scoring runs without generation, **Then** retrieve-non-empty is recorded as the mechanical retrieve check (citation checks wait until generation is enabled).
4. **Given** at least one case fails, **When** evaluation finishes, **Then** the process signals failure (non-success exit) so automation can gate on it.

---

### User Story 2 - See easy vs hard questions in the same report (Priority: P2)

The operator must not switch the chat to a multi-step “agentic” retrieve while the one-shot path still succeeds on easy questions. The eval set therefore contains both `one_shot` and `hard` cases. The report groups or labels them so the operator can see: one-shot still holds on easy items; hard items (compare two topics, need several sources) may fail without that meaning the default chat is broken.

**Why this priority**: ADR 0006: do not default to a slower retrieve loop until one-shot loses on easy cases. The distinction is the decision input; it is not required to ship the first scoring loop, but it is required before claiming “we know when to go agentic”.

**Independent Test**: Run the full eval set and confirm the report shows at least one `one_shot` case and at least one `hard` case with separate pass/fail.

**Acceptance Scenarios**:

1. **Given** the eval set includes both difficulties, **When** the operator reads the evaluation report, **Then** each case is labelled `one_shot` or `hard`.
2. **Given** one-shot easy `grounded` cases pass and a `hard` compare-two-topics case fails, **When** the operator interprets the report, **Then** they can treat that as “keep one-shot as default; hard cases are known gaps”, not as a reason to change the default chat path.

---

### User Story 3 - Inspect a chat turn locally, only when asked (Priority: P3)

When the operator wants to debug a turn, they enable tracing and start a **local** observation service that is not required for daily ingest, index, or chat. They then run evaluation or a normal sourced-chat question and inspect: question, retrieved passages, and answer. Tracing is off by default so the product never sends traces to a vendor cloud. Traces must not include lake credentials or catalogue secrets—only the conversational payload.

**Why this priority**: Traces explain *why* a score failed; they are optional RAM and ops cost. Scoring (P1) must work with tracing disabled.

**Independent Test**: With tracing disabled, run eval or chat and confirm no attempt to send traces to a public observation host. With tracing enabled and the local stack up, open the local UI and find at least one complete chat turn.

**Acceptance Scenarios**:

1. **Given** tracing is disabled (default), **When** the operator runs evaluation or a chat question, **Then** no trace is sent to a third-party hosted observation service.
2. **Given** tracing is enabled, the local observation stack is running, and the operator has set the local base URL plus local keys, **When** they run evaluation or chat, **Then** they can open the local UI and see question, passages, and answer for that turn.
3. **Given** the observation stack is not running and tracing is enabled, **When** they run evaluation, **Then** scoring still completes; missing traces do not hide eval pass/fail.
4. **Given** a trace is recorded, **When** the operator inspects it, **Then** they do not see MinIO, catalogue, or other lake secrets—only question, passages, and answer.

---

### Edge Cases

- Lake indexes empty: `grounded` cases fail on empty retrieve; `refuse` cases remain meaningful.
- Language model unavailable: evaluation with generation skipped still scores retrieve and refuse; citation/footer checks are omitted or marked skipped, not as false “grounded success”.
- Question uses tokens that never appear in the press corpus (nonce names): retrieve should be empty and the chat must refuse—not answer from nearest neighbours on unrelated news.
- Tracing enabled but local URL missing: must not fall back to a vendor cloud host.
- Observation stack uses its own store: the product catalogue database URL must not be reused for that stack.
- Host port already used by the chat UI: the observation UI uses a distinct local port so both can run.
- Object store bucket for traces missing after an older lake init: operator can re-run lake bootstrap for that bucket without wiping bronze.
- Hard case asks to compare two distinct corpus topics: one-shot retrieve may return an incomplete or single-topic context; score may fail without implying refuse-path bugs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST ship a named, versioned evaluation set of questions, each with a stable id, an expected behaviour (`grounded` or `refuse`), and a difficulty (`one_shot` or `hard`).
- **FR-002**: The operator MUST be able to run that set through the **same** sourced-chat path used for interactive chat (retrieve then optional generation), not a separate ad-hoc script that diverges from production answers.
- **FR-003**: The operator MUST be able to skip language-model generation so evaluation can run in CI and when the model is down.
- **FR-004**: Scoring MUST be deterministic and mechanical: retrieve empty vs non-empty; whether the answer is an explicit corpus refuse; whether generated answers include inline citation markers (e.g. `[1]`) and a sources footer when generation ran. Scoring MUST NOT use a second model as judge in this feature.
- **FR-005**: `refuse` cases MUST use questions whose tokens are absent from a typical press corpus so lexical and semantic neighbours do not count as “found in lake”.
- **FR-006**: Evaluation MUST exit unsuccessfully if any case fails, and MUST print a per-case report including id, difficulty, expected vs actual, and pass/fail.
- **FR-007**: Tracing of a chat turn (question, retrieved passages, answer) MUST be opt-in and MUST stay off by default.
- **FR-008**: When tracing is on, the product MUST send traces only to an operator-configured **local** observation endpoint, never to a vendor cloud by default.
- **FR-009**: The local observation stack MUST be optional relative to everyday lake services (it MUST NOT be required for ingest, index, chat, or eval scoring).
- **FR-010**: Traces MUST NOT include lake credentials or catalogue connection secrets.
- **FR-011**: Interactive sourced chat (command line and HTTP chat) MUST emit the same opt-in traces as evaluation when tracing is enabled.
- **FR-012**: This feature MUST NOT introduce crawl, paywall bypass, off-machine corpus upload, or a default agentic retrieve loop.

### Key Entities

- **Eval set**: A versioned collection of cases (name + version). Relationship: contains many eval cases.
- **Eval case**: id, question text, expected outcome (`grounded` | `refuse`), difficulty (`one_shot` | `hard`).
- **Eval result**: one case run: retrieve emptiness, refuse detected, citation/footer flags when generated, pass/fail, optional skip of generation-only checks.
- **Chat turn trace**: optional record of one question–retrieve–answer cycle, stored only when tracing is enabled, visible in the local observation UI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can run the full eval set with generation skipped and obtain a per-case pass/fail report in under 2 minutes on a warm local machine (excluding first-time index build).
- **SC-002**: 100% of `refuse` cases in the shipped set can be scored without a populated lake or a language model.
- **SC-003**: When indexes are empty, 100% of `grounded` cases fail for empty retrieve (no silent pass).
- **SC-004**: The report always shows both difficulty labels; a reader can count one-shot vs hard pass rates without re-reading questions.
- **SC-005**: With tracing left at default (off), running eval or chat does not contact a public observation host (operator can verify via local config: tracing flag off and no outbound observation URL required).
- **SC-006**: With tracing on and the local stack up, an operator finds a complete turn (question + passages + answer) in the local UI within 5 minutes of running one eval case or one chat question.
- **SC-007**: After a retrieve-depth or model change, the operator can re-run the same versioned set and compare pass/fail bit-for-bit on mechanical checks (same inputs → same scores).

## Assumptions

- Sourced chat from the learning-path chat module already exists: hybrid retrieve, citations, explicit refuse when nothing is in the corpus. This feature evaluates that path; it does not redefine ingest or bronze.
- Bronze remains source of truth; eval does not write lake objects and does not read raw bronze into the language model.
- Local-first: press text does not leave the machine unless the operator later chooses a hosted product (out of scope and rejected in docs).
- LLM-as-judge is deferred to a later quality/experiment module; this feature only uses mechanical scores.
- Agentic / MCP retrieve is out of scope; hard cases document one-shot limits, they do not implement a tool loop.
- Geo-markets event study, crawl, and paywall are out of scope.
- Everyday lake services stay up without the observation profile; operators who want traces accept extra memory for that optional stack.
- The project constitution file is still an unfilled template; product rules come from `docs/principles.md` and the cited ADRs until a constitution is ratified.
- Eval set v1 includes a small number of cases (nonce refuse, a few grounded one-shot questions on topics likely in a general RSS lake, one hard compare). Grounded pass rates depend on the operator actually having ingested and indexed matching articles.
