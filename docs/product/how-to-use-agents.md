# How to Use the Agent System

This guide explains how to run a feature through the agentic workflow.
Follow this process for every feature, without exception.

---

## The Golden Rule

> No implementation starts until five artifacts are approved and one task breakdown exists.

---

## Step-by-Step: Running a Feature

### 1. Open a new feature folder

```
/docs/features/<feature-name>/
```

Use lowercase and hyphens. Examples: `auth`, `table-join-flow`, `reconnect`.

Copy all templates from `/docs/templates/` into the folder.

---

### 2. Run the Product Manager agent

**File:** `/agents/product-manager.md`

**Prompt format:**
```
You are the Product Manager agent defined in /agents/product-manager.md.

Feature: [Feature Name]

Create feature-spec.md for this feature.
```

**Output:** `feature-spec.md`

**Gate:** Product Gate — approved when scope is clear, acceptance criteria are testable, and no critical questions remain open.

---

### 3. Run the Poker Player Reviewer agent

**File:** `/agents/poker-player-reviewer.md`

**Prompt format:**
```
You are the Poker Player Reviewer agent defined in /agents/poker-player-reviewer.md.

Feature: [Feature Name]
Input: [paste feature-spec.md content]

Create player-feedback.md for this feature.
```

**Output:** `player-feedback.md`

Findings feed back to the Product Manager for any scope adjustments before moving on.

---

### 4. Run the Senior UI/UX Designer agent

**File:** `/agents/senior-ui-ux-designer.md`

**Prompt format:**
```
You are the Senior UI/UX Designer agent defined in /agents/senior-ui-ux-designer.md.

Feature: [Feature Name]
Input: [paste feature-spec.md and player-feedback.md]

Create ux-spec.md for this feature.
```

**Output:** `ux-spec.md`

**Gate:** UX Gate — approved when all screens, states, and mobile constraints are defined with no ambiguity.

---

### 5. Run the Senior Mobile Game Developer agent

**File:** `/agents/senior-mobile-game-developer.md`

**Prompt format:**
```
You are the Senior Mobile Game Developer agent defined in /agents/senior-mobile-game-developer.md.

Feature: [Feature Name]
Input: [paste feature-spec.md, ux-spec.md]

Create technical-design.md for this feature.
```

**Output:** `technical-design.md`

**Gate:** Technical Gate — approved when modules, contracts, events, and state transitions are clear.

---

### 6. Run the Senior QA Reviewer agent

**File:** `/agents/senior-qa-reviewer.md`

**Prompt format:**
```
You are the Senior QA Reviewer agent defined in /agents/senior-qa-reviewer.md.

Feature: [Feature Name]
Input: [paste feature-spec.md, technical-design.md]

Create qa-test-plan.md for this feature.
```

**Output:** `qa-test-plan.md`

QA also reviews the technical design and feeds risk notes back to the developer.

---

### 7. Create the task breakdown

**Agent:** Senior Mobile Game Developer

**Prompt format:**
```
You are the Senior Mobile Game Developer agent defined in /agents/senior-mobile-game-developer.md.

Feature: [Feature Name]
Input: [paste technical-design.md, qa-test-plan.md]

Create task-breakdown.md for this feature.
```

**Output:** `task-breakdown.md`

**Gate:** Implementation Gate — approved when tasks are ordered, dependencies are clear, and QA scope is agreed.

---

### 8. Implement

Only the Senior Mobile Game Developer writes code.

Code must conform to:
- The technical design
- The approved architecture (server-authoritative, no game logic on client)
- The existing module boundaries in `backend/` and `poker_engine/`

---

### 9. QA Validation

After implementation:

```
You are the Senior QA Reviewer agent defined in /agents/senior-qa-reviewer.md.

Feature: [Feature Name]
Input: [paste qa-test-plan.md and implementation notes]

Validate the implementation and update qa-test-plan.md with results.
```

Then run UX review and Poker Player review.

---

### 10. Sign off

```
You are the Product Manager agent defined in /agents/product-manager.md.

Feature: [Feature Name]

All artifacts and QA results are attached. Create signoff.md.
```

**Gate:** Release Gate — no merge without a complete `signoff.md`.

---

## What Each Agent Owns

| Agent | Owns | Cannot Do |
|-------|------|-----------|
| Product Manager | Scope, acceptance criteria, priorities | Write code, define architecture |
| Poker Player Reviewer | Realism, social feel, clarity | Set scope, propose architecture |
| Senior UI/UX Designer | Screens, flows, states, layout | Change gameplay logic, write code |
| Senior Mobile Game Developer | Architecture, implementation, events | Expand scope without PM approval |
| Senior QA Reviewer | Pass/fail, test coverage, edge cases | Redefine scope, write production code |

---

## Artifacts Required Before Code is Written

All five of these must exist and be approved:

1. `feature-spec.md` — PM approved
2. `player-feedback.md` — reviewed, no blocking concerns
3. `ux-spec.md` — UX Gate passed
4. `technical-design.md` — Technical Gate passed
5. `qa-test-plan.md` — QA risks reviewed
6. `task-breakdown.md` — Implementation Gate passed

---

## The Six Approval Gates

| Gate | Owner | Blocks |
|------|-------|--------|
| Product Gate | PM | Moving to UX |
| UX Gate | UI/UX + PM | Moving to Technical Design |
| Technical Gate | Dev + QA + PM | Moving to Implementation |
| Implementation Gate | Dev | Writing code |
| QA Gate | QA | Merging |
| Release Gate | PM | Shipping |

---

## Recommended Feature Order

Build in this sequence to minimize dependency risk:

1. `auth` — phone login, OTP, display name
2. `clubs` — create, invite link, join
3. `home-screen` — club list, active table CTA
4. `table-join-flow` — seat assignment, spectator join
5. `table-shell-ui` — layout, action area, chat drawer
6. `game-engine` ✅ complete
7. `realtime-sync` ✅ complete
8. `reconnect-sit-out`
9. `house-rules-mvp`
10. `spectator-mode`
11. `chat`
12. `stats-leaderboard`
13. `push-notifications`
14. `analytics-hardening`

---

## Hard Rules (Never Break These)

1. All game logic lives on the server. The client never validates, never decides.
2. Spectators never receive hole card data before showdown.
3. No feature merges without `signoff.md`.
4. No code before approved specs.
5. Scope changes always require a new PM approval entry in `feature-spec.md`.
