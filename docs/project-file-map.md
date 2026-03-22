# Project File Map — Zepo

**Scan scope:** `C:/Users/LiorSw/Desktop/Zepo`
**Mapped files:** ~292
**Ignored:** `.git`, `node_modules`, `dist`, `build`, `.expo`, `coverage`, `__pycache__`, `venv`, `.venv`, `.pytest_cache`, `.mypy_cache`, `*.pyc`

---

## Top-Level Summary

| Folder / File | Purpose |
|---|---|
| `backend/` | FastAPI server — REST + WebSocket |
| `poker_engine/` | Pure Python poker engine (no I/O) |
| `simulation/` | Test harness + scenario drivers |
| `mobile/` | Expo/React Native client |
| `tests/` | Integration + simulation test suite |
| `docs/` | Feature specs, designs, templates |
| `agents/` | AI agent prompt definitions |
| `CLAUDE.md` | Claude Code project instructions |
| `README.md` | Project overview |
| `requirements-backend.txt` | Python dependencies |
| `pytest.ini` | Root pytest config |
| `dev_bot.py` | Dev utility script |

---

## Compact Directory Tree

```
Zepo/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── session_registry.py
│   ├── dev_seed.py
│   ├── analytics/
│   │   ├── events.py
│   │   └── service.py
│   ├── api/
│   │   ├── auth_router.py
│   │   ├── clubs_router.py
│   │   ├── health_router.py
│   │   └── tables_router.py
│   ├── auth/
│   │   ├── models.py
│   │   └── service.py
│   ├── chat/
│   │   ├── models.py
│   │   └── service.py
│   ├── clubs/
│   │   ├── models.py
│   │   └── service.py
│   ├── persistence/
│   │   ├── adapter.py
│   │   ├── memory.py
│   │   └── sqlite_adapter.py
│   ├── realtime/
│   │   ├── broadcaster.py
│   │   ├── schemas.py
│   │   ├── ws_broadcaster.py
│   │   └── ws_router.py
│   ├── sessions/
│   │   ├── models.py
│   │   └── session_manager.py
│   ├── stats/
│   │   ├── models.py
│   │   └── service.py
│   └── tables/
│       ├── models.py
│       └── service.py
│
├── poker_engine/
│   ├── engine/
│   │   ├── deck.py
│   │   ├── evaluator.py
│   │   ├── game_engine.py
│   │   ├── models.py
│   │   ├── pot_calculator.py
│   │   ├── validator.py
│   │   └── view_builder.py
│   ├── rules/
│   │   ├── base.py
│   │   └── builtin_rules.py
│   └── tests/
│       ├── helpers.py
│       ├── test_deck.py
│       ├── test_evaluator.py
│       ├── test_game_engine.py
│       ├── test_pot_calculator.py
│       └── test_view_builder.py
│
├── simulation/
│   ├── app_factory.py
│   ├── client.py
│   ├── deck_control.py
│   ├── event_log.py
│   ├── helpers.py
│   ├── runner.py
│   ├── debug/
│   │   ├── report.py
│   │   ├── snapshot.py
│   │   └── summary.py
│   ├── load_lite/
│   │   ├── assertions.py
│   │   ├── orchestrator.py
│   │   └── table_scenario.py
│   └── scenarios/
│       ├── s1_two_player_hand.py
│       ├── s2_mid_hand_join.py
│       ├── s3_spectator_filtering.py
│       ├── s4_reconnect.py
│       ├── s5_full_table_rejection.py
│       ├── s6_timeout_auto_action.py
│       ├── s7_disconnect_reserve_expiry.py
│       ├── s8_player_acted_fields.py
│       ├── s9_phase_community_timer.py
│       ├── s10_action_bar_correctness.py
│       ├── s11_live_pot_tracking.py
│       ├── s12_showdown_privacy.py
│       ├── deterministic/
│       │   ├── ds1_known_winner.py
│       │   ├── ds2_known_board.py
│       │   ├── ds3_deterministic_reconnect.py
│       │   ├── ds4_deterministic_spectator.py
│       │   └── ds5_duplicate_request.py
│       ├── gameplay/
│       │   ├── action_driver.py
│       │   ├── rg1_three_player_multi_hand.py
│       │   ├── rg2_mixed_actions.py
│       │   ├── rg3_inactive_player.py
│       │   ├── rg4_reconnect_multi_hand.py
│       │   ├── rg5_spectator_multi_hand.py
│       │   └── rg6_session_continuity.py
│       └── load_lite/
│           ├── ll1_multi_table.py
│           ├── ll2_concurrent_joins.py
│           ├── ll3_spectator_isolation.py
│           ├── ll4_reconnect_concurrent.py
│           ├── ll5_churn.py
│           └── ll6_completion_summary.py
│
├── mobile/
│   ├── app.json
│   ├── babel.config.js
│   ├── jest.config.js
│   ├── jest.setup.js
│   ├── package.json
│   ├── tsconfig.json
│   ├── app/
│   │   ├── _layout.tsx
│   │   ├── +not-found.tsx
│   │   ├── (auth)/
│   │   │   ├── _layout.tsx
│   │   │   ├── login.tsx
│   │   │   └── verify.tsx
│   │   └── (app)/
│   │       ├── _layout.tsx
│   │       ├── index.tsx
│   │       ├── clubs/[clubId].tsx
│   │       └── table/[tableId].tsx
│   ├── src/
│   │   ├── api/
│   │   │   ├── auth.ts
│   │   │   ├── client.ts
│   │   │   ├── clubs.ts
│   │   │   ├── tables.ts
│   │   │   └── types.ts
│   │   ├── components/
│   │   │   ├── common/
│   │   │   │   ├── AppErrorBoundary.tsx
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── ErrorDisplay.tsx
│   │   │   │   ├── LoadingSpinner.tsx
│   │   │   │   └── TableInfoCard.tsx
│   │   │   └── table/
│   │   │       ├── ActionBar.tsx
│   │   │       ├── CardChip.tsx
│   │   │       ├── CommunityCards.tsx
│   │   │       ├── ConnectionBanner.tsx
│   │   │       ├── HandInfoBar.tsx
│   │   │       ├── HandResultOverlay.tsx
│   │   │       ├── MyHoleCards.tsx
│   │   │       ├── PlayerList.tsx
│   │   │       ├── RaisePanel.tsx
│   │   │       └── RoleBadge.tsx
│   │   ├── store/
│   │   │   ├── authStore.ts
│   │   │   ├── clubStore.ts
│   │   │   └── tableStore.ts
│   │   ├── utils/
│   │   │   └── logger.ts
│   │   └── ws/
│   │       ├── SocketClient.ts
│   │       └── types.ts
│   └── __tests__/
│       ├── ActionBar.test.tsx
│       ├── CardChip.test.tsx
│       ├── CommunityCards.test.tsx
│       ├── ConnectionBanner.test.tsx
│       ├── HandInfoBar.test.tsx
│       ├── HandResultOverlay.test.tsx
│       ├── RaisePanel.test.tsx
│       ├── SocketClient.test.ts
│       ├── TableInfoCard.test.tsx
│       ├── authStore.test.ts
│       ├── canActDerivation.test.ts
│       ├── clubStore.test.ts
│       ├── holeCardGuard.test.tsx
│       ├── tableStore.test.ts
│       ├── tableStoreDisconnectReset.test.ts
│       ├── tableStoreHandResult.test.ts
│       ├── tableStoreJoinPending.test.ts
│       └── tableStoreSyncRequest.test.ts
│
├── tests/
│   ├── conftest.py
│   ├── test_app_integration.py
│   ├── test_connection_resilience.py
│   ├── test_debug_observability.py
│   ├── test_deck_control.py
│   ├── test_gameplay_scenarios.py
│   ├── test_load_lite.py
│   ├── test_persistence.py
│   ├── test_realtime_schemas.py
│   ├── test_session_manager.py
│   ├── test_simulation_deterministic.py
│   ├── test_simulation_scenarios.py
│   └── test_sqlite_persistence.py
│
├── docs/
│   ├── product/
│   │   ├── agentic-flow.md
│   │   └── how-to-use-agents.md
│   ├── templates/
│   │   ├── feature-spec.template.md
│   │   ├── player-feedback.template.md
│   │   ├── qa-test-plan.template.md
│   │   ├── signoff.template.md
│   │   ├── task-breakdown.template.md
│   │   ├── technical-design.template.md
│   │   └── ux-spec.template.md
│   └── features/
│       ├── backend-app-bootstrap/
│       ├── backend-application-wiring/
│       ├── connection-resilience-and-session-recovery/
│       ├── debug-observability-for-simulation/
│       ├── deterministic-simulation-scenarios/
│       ├── light-persistence-layer/
│       ├── load-lite-simulation/
│       ├── mobile-client-mvp-foundation/
│       ├── mobile-live-hand-flow/
│       ├── private-playtest-readiness/
│       ├── real-gameplay-scenarios/
│       └── simulation-harness/
│
└── agents/
    ├── poker-player-reviewer.md
    ├── product-manager.md
    ├── senior-mobile-game-developer.md
    ├── senior-qa-reviewer.md
    └── senior-ui-ux-designer.md
```

---

## Key Files by Folder

### Root
| File | Purpose |
|---|---|
| `CLAUDE.md` | Claude Code project instructions |
| `README.md` | Project overview |
| `pytest.ini` | Root pytest config |
| `requirements-backend.txt` | Python dependencies |
| `dev_bot.py` | Dev utility script |
| `.env.example` | Env var template |

### backend/
| File | Purpose |
|---|---|
| `main.py` | FastAPI app entrypoint |
| `config.py` | App config / env vars |
| `dependencies.py` | FastAPI dependency injection |
| `session_registry.py` | Table session registry |
| `dev_seed.py` | Dev data seeding; seeds Admin user (idempotent) |
| `api/auth_router.py` | Username/password auth endpoints (register, login) |
| `api/clubs_router.py` | Club CRUD endpoints; POST /clubs/join |
| `api/tables_router.py` | Table config endpoints |
| `api/health_router.py` | Health check endpoint |
| `auth/service.py` | Username/password auth logic (bcrypt) |
| `auth/models.py` | Auth data models |
| `clubs/service.py` | Club business logic |
| `clubs/models.py` | Club data models |
| `tables/service.py` | Table management logic |
| `tables/models.py` | Table data models |
| `sessions/session_manager.py` | Per-table WS session orchestrator; handles rebuy |
| `sessions/models.py` | Session state models |
| `realtime/ws_router.py` | WebSocket route handler |
| `realtime/ws_broadcaster.py` | WS message broadcaster |
| `realtime/broadcaster.py` | Broadcast service interface |
| `realtime/schemas.py` | WS message Pydantic schemas; REBUY, PLAYER_REBOUGHT |
| `persistence/adapter.py` | Persistence interface |
| `persistence/memory.py` | In-memory persistence |
| `persistence/sqlite_adapter.py` | SQLite persistence; auto-migrates rebuy columns |
| `analytics/service.py` | Analytics event service |
| `analytics/events.py` | Analytics event types |
| `chat/service.py` | Chat message service |
| `stats/service.py` | Player stats service |

### poker_engine/
| File | Purpose |
|---|---|
| `engine/models.py` | Core dataclasses (Card, GameState, PlayerSession with rebuy fields, events) |
| `engine/game_engine.py` | Hand state machine |
| `engine/evaluator.py` | 5-7 card hand evaluator |
| `engine/deck.py` | Deck / deal utilities |
| `engine/pot_calculator.py` | Pot split / side pot logic |
| `engine/validator.py` | Action legality checks |
| `engine/view_builder.py` | Player-safe state snapshot builder; exposes rebuy fields |
| `rules/base.py` | House rules interface |
| `rules/builtin_rules.py` | Default house rules |

### simulation/
| File | Purpose |
|---|---|
| `app_factory.py` | TestClient factory with patched delays |
| `client.py` | SimulatedClient (HTTP + WS) |
| `event_log.py` | Per-client event log |
| `helpers.py` | Setup helpers (two-player, drive hand) |
| `deck_control.py` | Deterministic deck seeding |
| `runner.py` | Standalone scenario runner |
| `debug/snapshot.py` | Client state snapshot for diagnostics |
| `debug/report.py` | Debug report formatter |
| `debug/summary.py` | Client summary helper |
| `load_lite/orchestrator.py` | Concurrent table orchestrator |
| `load_lite/table_scenario.py` | Single-table load scenario |
| `load_lite/assertions.py` | Load test assertions |
| `scenarios/s1_*.py` | Two-player happy path |
| `scenarios/s2_*.py` | Mid-hand join |
| `scenarios/s3_*.py` | Spectator event filtering |
| `scenarios/s4_*.py` | Reconnect within window |
| `scenarios/s5_*.py` | Full-table rejection |
| `scenarios/s6_*.py` | Turn timer auto-action |
| `scenarios/s7_*.py` | Disconnect reserve expiry |
| `scenarios/s8_*.py` | PLAYER_ACTED payload fields |
| `scenarios/s9_*.py` | Phase/community card/timer fields |
| `scenarios/s10_*.py` | Action bar call_amount correctness |
| `scenarios/s11_*.py` | Live pot tracking |
| `scenarios/s12_*.py` | Showdown privacy / winner reveal |
| `scenarios/deterministic/ds*.py` | Seeded-deck deterministic scenarios |
| `scenarios/gameplay/rg*.py` | Multi-hand real gameplay scenarios |
| `scenarios/load_lite/ll*.py` | Concurrent load scenarios |

### mobile/
| File | Purpose |
|---|---|
| `app/_layout.tsx` | Root navigation layout |
| `app/(auth)/login.tsx` | Combined login + register screen (username/password) |
| `app/(auth)/verify.tsx` | Redirects to login (legacy OTP stub) |
| `app/(app)/index.tsx` | Club list / home screen; join club; Admin create-club |
| `app/(app)/clubs/[clubId].tsx` | Club detail screen |
| `app/(app)/table/[tableId].tsx` | Live table screen; rebuy modal |
| `src/api/client.ts` | Axios HTTP client |
| `src/api/auth.ts` | Auth API calls (register, login) |
| `src/api/clubs.ts` | Clubs API calls |
| `src/api/tables.ts` | Tables API calls |
| `src/api/types.ts` | API response types |
| `src/store/authStore.ts` | Auth Zustand store; persists token, userId, displayName |
| `src/store/clubStore.ts` | Club list Zustand store |
| `src/store/tableStore.ts` | Table game state Zustand store; sendRebuy, PLAYER_REBOUGHT handler |
| `src/ws/SocketClient.ts` | WebSocket client with reconnect |
| `src/ws/types.ts` | WS message TypeScript types |
| `src/utils/logger.ts` | Table event logger |
| `src/components/common/Button.tsx` | Shared button component |
| `src/components/common/TableInfoCard.tsx` | Table summary card |
| `src/components/common/AppErrorBoundary.tsx` | Error boundary |
| `src/components/table/ActionBar.tsx` | Fold/Check/Call/Raise bar |
| `src/components/table/CardChip.tsx` | Single playing card display |
| `src/components/table/CommunityCards.tsx` | Board cards display |
| `src/components/table/ConnectionBanner.tsx` | WS connection status banner |
| `src/components/table/HandInfoBar.tsx` | Phase / pot info bar |
| `src/components/table/HandResultOverlay.tsx` | Hand end winner overlay |
| `src/components/table/MyHoleCards.tsx` | Player's own hole cards |
| `src/components/table/PlayerList.tsx` | Player rows with status/bet/rebuy badge |
| `src/components/table/RaisePanel.tsx` | Raise amount slider panel |
| `src/components/table/RoleBadge.tsx` | Player/watcher role badge |

### tests/
| File | Purpose |
|---|---|
| `conftest.py` | Shared pytest fixtures |
| `test_app_integration.py` | Full app integration tests |
| `test_connection_resilience.py` | Reconnect / disconnect tests |
| `test_session_manager.py` | Session manager unit tests |
| `test_realtime_schemas.py` | WS schema validation tests |
| `test_persistence.py` | Persistence adapter tests |
| `test_sqlite_persistence.py` | SQLite adapter tests |
| `test_simulation_scenarios.py` | S1–S12 scenario test runner |
| `test_simulation_deterministic.py` | DS1–DS5 deterministic tests |
| `test_gameplay_scenarios.py` | RG1–RG6 gameplay tests |
| `test_load_lite.py` | LL1–LL6 load tests |
| `test_debug_observability.py` | Debug tooling tests |
| `test_deck_control.py` | Deck seeding tests |

### docs/features/ (each folder contains the same 5–7 doc types)
| Folder | Feature |
|---|---|
| `backend-app-bootstrap/` | Initial FastAPI setup |
| `backend-application-wiring/` | Backend service wiring |
| `connection-resilience-and-session-recovery/` | Reconnect / reserve seats |
| `debug-observability-for-simulation/` | Debug snapshot tooling |
| `deterministic-simulation-scenarios/` | Seeded-deck test scenarios |
| `light-persistence-layer/` | SQLite persistence |
| `load-lite-simulation/` | Concurrent load harness |
| `mobile-client-mvp-foundation/` | Mobile app foundation |
| `mobile-live-hand-flow/` | Live hand UI + WS events |
| `private-playtest-readiness/` | Playtest hardening |
| `real-gameplay-scenarios/` | Multi-hand gameplay tests |
| `simulation-harness/` | SimulatedClient harness |

### agents/
| File | Purpose |
|---|---|
| `poker-player-reviewer.md` | Agent: player UX review |
| `product-manager.md` | Agent: feature/product decisions |
| `senior-mobile-game-developer.md` | Agent: mobile implementation |
| `senior-qa-reviewer.md` | Agent: QA / test review |
| `senior-ui-ux-designer.md` | Agent: UI/UX design |
