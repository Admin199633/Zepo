# Zepo — Real-Time Multiplayer Poker

A production-grade server-authoritative Texas Hold'em poker system built for mobile.

All game logic runs on the server. The client is display and input only — it never validates actions, never makes decisions, and never receives hidden card data before showdown.

---

## Repository Structure

```
poker_engine/          # Pure game engine — no networking, no I/O
  engine/              # Core: models, deck, evaluator, pot_calculator,
  │                    #       validator, game_engine, view_builder
  rules/               # House rule plugin system (ABC + built-in rules)
  tests/               # Full unit test suite for the engine

backend/               # Application layer surrounding the engine
  config.py            # Settings via environment variables
  persistence/         # PersistenceAdapter ABC + InMemoryPersistenceAdapter
  realtime/            # WebSocket DTO schemas + BroadcastService protocol
  sessions/            # TableSessionManager (asyncio, timers, idempotency)

agents/                # Agent definition files for the agentic workflow
docs/
  product/             # agentic-flow.md, how-to-use-agents.md
  templates/           # Document templates (feature-spec, ux-spec, etc.)
  features/            # One folder per feature, populated during development

tests/                 # Integration and backend-level tests
```

---

## Agentic Workflow

This project uses a structured multi-agent development workflow. Every feature goes through five specialist agents and six approval gates before any code is written.

**Agents** (definitions in `/agents/`):
- Product Manager — scope, acceptance criteria, priorities
- Poker Player Reviewer — realism, social feel, clarity
- Senior UI/UX Designer — screens, flows, mobile constraints
- Senior Mobile Game Developer — architecture and implementation
- Senior QA Reviewer — test coverage, edge cases, pass/fail

**Six gates** block progress until the required artifact is approved:

| Gate | Blocks |
|------|--------|
| Product Gate | Moving to UX |
| UX Gate | Moving to Technical Design |
| Technical Gate | Moving to Implementation |
| Implementation Gate | Writing code |
| QA Gate | Merging |
| Release Gate | Shipping |

**Required artifacts per feature** (all must exist and be approved before code):
`feature-spec.md`, `player-feedback.md`, `ux-spec.md`, `technical-design.md`, `qa-test-plan.md`, `task-breakdown.md`

Full workflow reference: [`/docs/product/agentic-flow.md`](/docs/product/agentic-flow.md)
Step-by-step usage guide: [`/docs/product/how-to-use-agents.md`](/docs/product/how-to-use-agents.md)

---

## Hard Rules

1. All game logic lives on the server. The client never validates, never decides.
2. Spectators never receive hole card data before showdown.
3. No feature merges without `signoff.md`.
4. No code before approved specs.
5. Scope changes always require a new PM approval entry in `feature-spec.md`.
