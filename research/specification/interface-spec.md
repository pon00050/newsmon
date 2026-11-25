# Interface specification: MVP surfaces and monitoring profiles (Workstream I output, S1, 2026-11-25)

> **Status: Design proposal (not built).** Interface proposal. Only the local review queue is built.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Basis:**

- Desk practice: [`business/desk-practices.md`](../business/desk-practices.md) (persistent registration + separate notice; draft-for-review digest).
- Delivery decision: ADR-008. Licence display rules: DR-3 and DR-8 via `DisplayPolicy` (ADR-002, ADR-010). AI labelling
  and plain-text rendering: [`technology/ai-threat-model.md`](../technology/ai-threat-model.md) M7.
- Vendor patterns: AISURFER Brief group rules, draft review and delivery receipts (`02_COMMERCIAL…` F-B-03, §4).

**Design rules:**

- Functional over visual; Korean UI text.
- Times are shown in KST, with UTC kept underneath.
- Every item shows source, link, time and licence display level.
- AI text always carries **[AI 생성]** and the model name on hover.
- No model output is rendered as HTML or markdown, and links in model output are stripped.

## 1. Surface list

| ID | Surface | Users | FR |
|---|---|---|---|
| UI-1 | Editorial queue (home) | monitor, editor | FR-17, FR-18 |
| UI-2 | Event detail | monitor, reporter | FR-10, FR-19 |
| UI-3 | Item detail | monitor, reporter | FR-12, FR-19, FR-25 |
| UI-4 | Search | all | FR-20 |
| UI-5 | Alerts and approval tray | monitor | FR-21, FR-04 |
| UI-6 | Digest editor (draft → review → approve → send) | editor | FR-22 |
| UI-7 | Profile editor | admin, editor | FR-16 |
| UI-8 | Sources and feed health | admin, monitor | FR-01, FR-04, FR-28 |
| UI-9 | Review queue (AI validation failures, ⚠ injection, quarantined files) | editor | FR-13, FR-14, FR-28 |

## 2. UI-1 Editorial queue

```
┌ newsmon · 외신 데스크 ──────────────────────────── 2026-11-25 23:41 KST ─ 프로필: [외신데스크 ▾] ─ ● 피드 27/28 정상 ─ AI: 정상 ($1.12/5.00) ┐
│ 필터: 등급[flash report review ▾]  언어[EN KO ZH]  출처[전체 ▾]  기간[최근 6시간 ▾]  ☐ 내가 처리 안 한 것만     🔔 2  ⚠ 1               │
├────┬──────┬────────────────────────────────────────────────────────┬──────┬────────┬────────┬──────────────┤
│등급│ 최초 │ 사건 (대표 제목 · [AI 생성] 한국어 요약 한 줄)              │독립출처│ 언어   │ 최신   │ 처리         │
├────┼──────┼────────────────────────────────────────────────────────┼──────┼────────┼────────┼──────────────┤
│FLASH│23:12│ US announces new export curbs on chips                  │  5   │EN KO ZH│ 23:39  │[보고][확인][무시]│
│    │      │ [AI 생성] 미 상무부, 대중 반도체 수출 통제 추가 발표…     │      │        │        │              │
│    │      │ 근거: 감시어 'export controls' · 출처 5개 ≥ 기준 3 · wire │      │        │        │              │
├────┼──────┼────────────────────────────────────────────────────────┼──────┼────────┼────────┼──────────────┤
│REPORT│22:58│ (mock wire) MOCK-AP: Earthquake off Hokkaido M6.1      │  2   │EN      │ 23:05  │ ✔ 보고됨 (kim) │
├────┼──────┼────────────────────────────────────────────────────────┼──────┼────────┼────────┼──────────────┤
│REVIEW│22:40│ ⚠ 주입 의심 · 원문 제목만 표시 · AI 점수 무시됨          │  1   │EN      │ 22:40  │[검토]         │
├────┼──────┼────────────────────────────────────────────────────────┼──────┼────────┼────────┼──────────────┤
│REVIEW│21:15│ 북한, 단거리 탄도미사일 발사 (AI 처리 대기)              │  3   │KO EN   │ 22:01  │[보고][확인][무시]│
└────┴──────┴────────────────────────────────────────────────────────┴──────┴────────┴────────┴──────────────┘
 [보고] = report_to_desk (opens a note box: 요지 / 활용 가능성 / 검증 상태)   [확인] = verify   [무시] = ignore    j/k 이동 · r 보고 · v 확인 · x 무시
```

**Rows and ordering**

- One row per **event**. A singleton item is an event of size 1.
- Rows are sorted by band, then by independent sources, then by latest update.

**The 근거 line**

- It shows the rule explanation: which rule fired and which terms matched (FR-17).

**Verdict actions**

- A verdict writes an `editorial_assessment` row with an optional note. That row is the "PC등록" registration.
- A report verdict on a flash event asks whether to send a notice. The notice goes through FR-21's outbox rules.

**AI-off state**

- The header shows "AI: 중단 (규칙 모드)".
- Rows show the original title, plus the feed summary only where `display ≥ snippet`.
- A "AI 처리 대기" tag marks rows still waiting for enrichment.

**Accessibility**

- Every action is reachable by keyboard.
- The table uses no colour-only signals. The band is printed as text.

## 3. UI-2 Event detail

```
┌ 사건 E-01HZX… · FLASH · 최초 23:12 KST · 독립 출처 5 (도메인 5 / 중복군 4) · [병합] [분리] [보고] ┐
│ [AI 생성 · claude-haiku-5-5 · p v2] 요약: 미 상무부는 … (주장 출처: 미 상무부 성명)              │
│ 타임라인                                                                                       │
│ 23:12  reuters? ✗   ── (not collected)                                                          │
│ 23:12  guardian_world   "US unveils new chip export controls"        headline · 링크 ↗          │
│ 23:20  yna_intl         "미, 대중 반도체 수출통제 강화"               headline · 링크 ↗          │
│ 23:25  mock_wire_demo   MOCK-AP URGENT  (full text, 내부 열람만)       full · 원문 보기          │
│ 23:31  cna_tw_intl      "美擴大晶片出口管制"   ≈ syndicated of #2? no  headline · 링크 ↗          │
│ 23:39  dw_en_all        (revision of 23:14 item, change: update)                               │
│ 중복/재게재: 3건 접힘 [펼치기]                                                                 │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Provenance per row**

- Each row shows the source key, a link (or "원문 보기" where `display=full`), the display level, the publisher time, the
  first-seen time, and any near-duplicate or revision relation.

**Merging and splitting events**

- Merge and split record `added_by='editor:<login>'` on the membership row.

**Not in the MVP**

- Contradiction detection is deferred (ADR-005). The view shows extracted numbers per member only where enrichment
  produced them.

## 4. UI-3 Item detail

```
┌ guardian_world · 2026-11-25 23:12 KST (pub 14:12Z) · first seen 23:14 · display: headline · 출처: The Guardian ┐
│ 제목: US unveils new chip export controls                                    [원문 링크 ↗]                    │
│ [AI 생성] 한국어 제목: 미국, 새 반도체 수출통제 공개                                                          │
│ [AI 생성] 요약 (3문장) …                                                                                     │
│ [AI 생성] 누가/무엇/어디/언제: … · 인물: Gina X (원문 표기 / 한국어 표기) · 주장: "…" — 출처: 상무부 (attributed) │
│ 플래그: (none)          AI 상태: done · valid · fields_sent: title, feed_summary · $0.0013                     │
│ 관련: 같은 사건 E-01HZX… · 중복 2건                                                                           │
│ [보고] [확인] [무시]  [번역 요청 (허용된 출처만)]                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

For a `display=full` tenant-licensed item, the body is shown to signed-in internal users only. It is never included in
export or outbound messages when `redistribution=none`.

## 5. UI-4 Search

```
검색: [ 김여정 담화                ] 언어[전체] 출처[전체] 기간[7일] 등급[전체]  ☑ 교차언어 확장 (AI)   [검색]
확장된 질의: 김여정 OR "Kim Yo Jong" OR 金與正 OR 金与正   (gazetteer 3 + AI 1)       결과 42건 · 18 ms
 1. [KO] yna_nk · 11-25 09:12 · 김여정, 대남 담화 발표 … · 사건 E-… · REPORT
 2. [EN] guardian_world · 11-25 08:40 · Kim Yo Jong warns … · 사건 E-…
 3. [ZH] voa_zh · 11-25 10:03 · 金與正發表談話 …
```

- The expansion line shows exactly which terms were added, and where each came from (gazetteer aliases are
  deterministic; an AI rewrite is labelled as AI).
- A query of 2 Hangul or Han characters works, because of bigram indexing (ADR-004).
- An empty result says "0건 (검색어 확인)". It never implies "no news" when a feed is in an incident state: a banner lists
  any failing feeds that fall inside the filter.

## 6. UI-6 Digest editor

```
┌ 브리핑 · 조간 (07:00 KST) · 프로필 외신데스크 · 창 19:00–07:00 · 상태: 검토 중 · 초안: AI (claude-sonnet-5-5) [AI 생성] ┐
│ 1. 미국 반도체 수출통제 확대  [E-01HZX…]  인용: a-1, a-7, a-9  ✔ 인용 확인                                       │
│    (편집 가능 텍스트)                                                                                           │
│ 2. 홋카이도 해역 M6.1 지진 [E-…] 인용: a-12 (mock wire, 내부 전용 → 외부 수신자에게는 제목만)                    │
│ + 항목 추가 (큐에서 검색)    ↑↓ 순서    ✖ 제외                                                                  │
│ 수신자: desk@internal (허용목록) · ext@partner.com ⚠ 외부: 재배포 금지 출처 2건 → 제목·링크만                     │
│ [템플릿으로 재생성 (AI 없음)]  [미리보기]  [승인 후 발송]                                                         │
│ 발송 기록: 11-24 07:02 desk@internal 성공 · ext@… 실패 (SMTP 550)                                                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Editions**

- Scheduled editions run per profile: morning, evening, and **handoff** (from the start to the end of the shift).
- Ad hoc editions run on demand.

**Before an edition can be approved**

- The citation check must pass: every bullet cites at least one article, and every cited id belongs to the selected set.
- A send is blocked until a person approves it.

**What each recipient receives**

- Per recipient, `DisplayPolicy` and `redistribution` decide what text goes out.

## 7. UI-7 Profile editor, and how users define monitoring without code

A profile is a YAML document. It is stored versioned in `profile.yaml` and edited either as a form or as raw YAML, with
validation on save. Each profile defines what to watch, how to rank it, when to alert and digest, and to whom.

```yaml
key: foreign_desk
name: 외신 데스크 (야간)
languages: [en, ko, zh]
countries: [US, CN, JP, KP, TW, RU, UA]          # matched on located/datelines and AI 'where' (when available)
topics:                                           # free labels; optional IPTC Media Topics codes later
  - {label: 한반도, keywords: {ko: [북한, 김정은, 김여정, 미사일], en: ["North Korea", "Kim Jong Un", Pyongyang], zh: [朝鲜, 金正恩]}}
  - {label: 미중, keywords: {en: ["export controls", tariff, Taiwan Strait], ko: [수출통제, 관세], zh: [出口管制, 关税]}}
entities: [kim_yo_jong, xi_jinping, us_commerce_dept]   # ids in gazetteer.yaml (aliases in KO/EN/ZH)
exclude_keywords: {en: [horoscope, "live scores"]}
sources:
  prefer: {mock_wire_demo: 3.0, yna_intl: 1.5, guardian_world: 1.2}   # weights in ranking
  mute: [sec_edgar_atom_8k]
priority_rules:                                   # evaluated in order; highest band wins; LLM can never raise to flash
  - id: wire_flash
    when: {source_is_wire: true, urgency_lte: 2}
    band: flash
  - id: watch_entity_multi
    when: {entity_hit: true, independent_sources_gte: 3, within_hours: 6}
    band: flash
  - id: topic_hit
    when: {topic_hit: true}
    band: review
thresholds:
  independent_sources_for_report: 2
  spike_z: 2.5
  spike_min_count: 5
  ai_band_weight: 1.0                             # 0 = ignore AI band entirely
alerts:
  flash: {channels: [inapp, email], recipients: [desk@internal], auto_send: true}   # auto only to allow-listed, unflagged
  feed_incident: {channels: [inapp, email], recipients: [ops@internal], external_notice: draft_only}
schedules:
  - {edition: morning, at: "07:00", tz: Asia/Seoul, window_hours: 12, max_items: 15, recipients: [desk@internal]}
  - {edition: handoff, at: "09:00", tz: Asia/Seoul, window: shift, recipients: [desk@internal]}
review_required: true
```

**Validation on save**

- Unknown source or entity ids are rejected.
- A recipient outside `settings.allowed_recipient_domains` is marked external, and every send to it then needs approval.
- A rule that would set `flash` from an AI field alone is rejected.

**Previewing a change**

- The form shows "what would this profile have done in the last 24 h". It counts flash, report and review items by
  re-running the rules over stored items.

## 8. UI-8 Sources and feed health

```
출처            커넥터      상태       최근 성공   24h 성공률  항목/시   라이선스(저장/표시/AI/외부AI/재배포/보존)   사건
guardian_world  feed       정상       23:40      100%       6.1      metadata/headline/unknown/✔/none/90일
yna_intl        feed       비활성(문맥) —          —          —        private 전용 (internal 모드에서 꺼짐)
mock_wire_gated directory  정상       23:41      100%       0.4      full/full/yes/✗/none/30일 · 라이선스 확인 2026-11-25
fedreg_api      http_api   ⚠ 빈 응답  23:10      92%        0 (기준 2.3)  full/full/yes/✔/internal/—      [사건 #12: empty]
```

Incidents follow the FR-04 rules: open on failure or emptiness, auto-close on recovery. The admin can disable a source
(takedown, FR-26) or edit its flags. For any `licence_owner=tenant` source, the edit form is the onboarding step (FR-30):

- The customer's admin enters **the customer's own contract terms** as flags, using the DR-30 checklist from `08_LEGAL…` §13.5.
- The admin attests to them, with name, date, `agreement_ref` and `valid_until`.
- The source cannot be activated before attestation.
- The safe defaults shown for an unconfigured source are not a statement about what the contract allows.

## 9. Non-UI interfaces

**REST and MCP**

- Shapes are in deliverable 11 §6.
- The MCP tools follow [`technology/mcp-tool-design.md`](../technology/mcp-tool-design.md) §3 v1 and are read-only.

**Email**

- Plain-text and HTML parts.
- The subject is prefixed `[newsmon][FLASH]` or `[newsmon][조간]`.
- The body carries the AI label and source links.
