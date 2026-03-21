# Agentic Flow — Mobile Poker Game

> This document is the authoritative workflow reference for all feature development.
> Every contributor and every agent must follow this process without exception.

---

## 1. Core Principle

**No code is written before four artifacts are approved.**

For every feature, in order:

| Step | Agent | Output |
|------|-------|--------|
| 1 | Product Manager | `feature-spec.md` |
| 2 | Poker Player Reviewer | `player-feedback.md` |
| 3 | Senior UI/UX Designer | `ux-spec.md` |
| 4 | Senior Mobile Game Developer | `technical-design.md` |
| 5 | Senior QA Reviewer | `qa-test-plan.md` |
| 6 | Senior Mobile Game Developer | `task-breakdown.md` |
| 7 | Senior Mobile Game Developer | **implementation** |
| 8 | Senior QA Reviewer + all agents | `signoff.md` |

---

## 2. Agent Ownership

Each domain has exactly one owner. Ownership prevents conflicting decisions.

| Domain | Owner | Can Override |
|--------|-------|-------------|
| Scope, priorities, acceptance criteria | Product Manager | Nobody |
| Interaction hierarchy, screens, states | Senior UI/UX Designer | Nobody |
| Architecture, implementation, events | Senior Mobile Game Developer | Nobody |
| Pass/fail, test coverage, regressions | Senior QA Reviewer | Nobody |
| Realism, social feel, house-rule sanity | Poker Player Reviewer | Nobody |

---

## 3. The Six Gates

A feature cannot advance past a gate until its exit criteria are met.

### Gate 1 — Product Gate
**Owner:** Product Manager
**Exit criteria:**
- Feature goal is unambiguous
- Scope boundaries are explicit (in-scope AND out-of-scope listed)
- Acceptance criteria are testable
- No critical open questions remain
- Dependencies are identified

### Gate 2 — UX Gate
**Owner:** Senior UI/UX Designer + PM sign-off
**Exit criteria:**
- All screens and states are defined
- Player vs. spectator distinction is explicit
- Mobile (landscape) layout constraints are addressed
- No ambiguity about component behavior or empty/error/loading states

### Gate 3 — Technical Gate
**Owner:** Senior Mobile Game Developer + QA review + PM sign-off
**Exit criteria:**
- Module boundaries are clear
- Data structures and event contracts are defined
- State transitions are documented
- QA has flagged risks and edge cases
- No unresolved architecture questions

### Gate 4 — Implementation Gate
**Owner:** Senior Mobile Game Developer
**Exit criteria:**
- Task list is ordered with dependencies
- Each task has a clear definition of done
- Testing scope is agreed with QA
- All four prerequisite artifacts exist and are approved

### Gate 5 — QA Gate
**Owner:** Senior QA Reviewer
**Exit criteria:**
- All test scenarios from `qa-test-plan.md` have been verified
- No blocker defects remain open
- Edge cases and reconnect scenarios have been tested
- No hidden-data leaks observed
- Regression checklist is clean

### Gate 6 — Release Gate
**Owner:** Product Manager (final decision)
**Exit criteria:**
- PM confirms acceptance criteria are met
- UX and Poker Player Reviewer have no blocking objections
- `signoff.md` is complete with all agent approvals

---

## 4. Required Artifacts per Feature

Every feature folder under `/docs/features/<feature-name>/` must contain:

```
feature-spec.md        ← Product Manager
player-feedback.md     ← Poker Player Reviewer
ux-spec.md             ← Senior UI/UX Designer
technical-design.md    ← Senior Mobile Game Developer
qa-test-plan.md        ← Senior QA Reviewer
task-breakdown.md      ← Senior Mobile Game Developer
signoff.md             ← All agents
```

Templates for each file are in `/docs/templates/`.

---

## 5. Workflow Stages in Detail

### Stage 1 — Product Definition
```
Product Manager → Poker Player Reviewer → Product Manager (finalize)
```
Produces: `feature-spec.md`, `player-feedback.md`

### Stage 2 — UX Definition
```
Product Manager (brief) → UI/UX Designer → Poker Player Reviewer → Product Manager (finalize)
```
Produces: `ux-spec.md`

### Stage 3 — Technical Design
```
Product Manager (brief) → Senior Developer → QA Reviewer → Product Manager (finalize)
```
Produces: `technical-design.md`, QA risk notes (fed into `qa-test-plan.md`)

### Stage 4 — Implementation Planning
```
Senior Developer → QA Reviewer → Product Manager (approve)
```
Produces: `task-breakdown.md`

### Stage 5 — Implementation
```
Senior Developer only
```
Produces: code + `implementation-notes.md` (optional)

### Stage 6 — QA Validation
```
QA Reviewer → UI/UX Designer → Poker Player Reviewer → Product Manager
```
Produces: `signoff.md`

---

## 6. Rules That Prevent Agent Chaos

1. Only the Product Manager sets scope. Scope cannot expand during implementation.
2. Only the Senior Developer writes production code.
3. Only QA determines pass/fail on test coverage.
4. Only UI/UX determines interaction hierarchy and screen layout.
5. The Poker Player Reviewer is a reviewer, not an architect or decision-maker.
6. No feature enters implementation without all four prerequisite artifacts approved.
7. No feature merges without a completed `signoff.md`.
8. Any deviation from the approved PRD requires explicit PM approval and a new feature-spec entry.
9. All game logic stays on the server. Client is display and input only.
10. Spectator hidden-data protection is non-negotiable and enforced at the server level.

---

## 7. Recommended Build Order

Build features in this sequence to minimize dependency risk:

1. Authentication (phone + OTP)
2. Clubs (create, invite, join)
3. Home Screen
4. Table Join Flow
5. Table Shell UI
6. Core Game Engine ✅ *(complete)*
7. Realtime Sync + Session Manager ✅ *(complete)*
8. Reconnect + Sit Out
9. House Rules MVP (bonus, invalid hand, straddle)
10. Spectator Mode
11. Chat
12. Stats + Leaderboard
13. Push Notifications
14. Analytics + Hardening

---

## 8. Definition of Done

A feature is **Done** when all of the following are true:

- [ ] PM acceptance criteria are fully met
- [ ] UX spec is implemented as designed
- [ ] Technical design is implemented as specified
- [ ] All QA test scenarios pass
- [ ] Primary edge cases are covered
- [ ] No hidden-data leaks exist
- [ ] No known desync issues exist
- [ ] No blocker on the critical path
- [ ] `signoff.md` is complete
