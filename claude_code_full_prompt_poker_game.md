# Claude Code Prompt - Mobile Poker Game (Texas Hold'em Clubs)

## Context
You are building a mobile-first real-time multiplayer Texas Hold'em poker game for iOS and Android.

This is a PRIVATE CLUB-BASED poker system (no public matchmaking).

The system must be production-grade, scalable, and server-authoritative.

---

## Core Requirements

### Product
- Texas Hold'em (No-Limit)
- Cash game only
- Play money only
- Private clubs
- One table per club
- Up to 10 players per table
- Unlimited spectators

---

## Architecture Principles

- Server authoritative (CRITICAL)
- Client is display + input only
- No game logic on client
- Deterministic game engine
- Event-driven system
- WebSocket real-time communication

---

## Core Systems

### 1. Game Engine
Responsible for:
- Deck generation
- Secure shuffle (server-side RNG)
- Card dealing
- Betting logic
- Pot calculation
- Winner evaluation
- House rules execution

Must include:
- Deterministic state machine
- Action validation
- Turn management
- Timeout handling

---

### 2. Table Session Manager
Responsible for:
- Player seating (auto assign)
- Spectator tracking
- Join/leave logic
- Sit-out handling
- Reconnect handling

Rules:
- Max 10 players
- Join mid-game → wait until next hand
- Disconnect → seat saved for 60 seconds
- After 60s → sit out

---

### 3. Realtime Layer
- WebSocket-based
- One channel per table
- Broadcast state updates
- Low latency

---

### 4. Chat System
- Per-table chat
- Real-time messaging
- UTF-8 support (including Hebrew)

---

### 5. Persistence Layer
Store:
- Users
- Clubs
- Stats
- Game results
- Logs

---

## User System

Authentication:
- Phone number login
- SMS verification

User Model:
- id
- phone_number
- display_name

---

## Clubs System

- Join via invite link
- No approval required

Admin capabilities:
- Create table
- Configure rules
- Promote admins
- Remove/block users

---

## Table Configuration

- Starting stack (fixed)
- Blinds (fixed)
- Turn timer (preset values)
- Rebuy only when busted
- House rules (predefined set)

---

## Turn Timer Values
- 30s
- 60s
- 90s
- 2m
- 5m
- 15m
- 30m
- 60m

---

## Game Flow (State Machine)

States:
- WAITING_FOR_PLAYERS
- START_HAND
- DEAL_HOLE_CARDS
- PRE_FLOP
- FLOP
- TURN
- RIVER
- SHOWDOWN
- HAND_END

---

## Turn Handling

If player acts:
- Validate action
- Apply to game state

If timeout:
- If possible → auto-check
- Else → auto-fold

Repeated timeouts:
- Move player to sit-out

---

## House Rules (MVP)

### Bonus Hand
- Example: win with 2-7 → receive bonus from all players

### Invalid Hand
- Example: 7-10 → auto-fold immediately

### Straddle
- Optional blind before pre-flop

IMPORTANT:
- Must be modular
- Must not break core game flow

---

## Spectator System

Capabilities:
- Watch game
- Chat

Restrictions:
- No hidden data exposure
- No action prompts

CRITICAL:
- Spectators must NEVER receive hidden cards in payload

---

## Chips & Economy

- Session-based only
- No persistent balance
- Fixed starting stack
- Rebuy only when stack = 0

---

## Stats & Leaderboard

Track per player:
- Wins
- Hands played
- Win rate

Leaderboard:
- Per club
- Sorted by wins

---

## Notifications

Push notifications for:
- Club invite
- Table active
- Player turn
- Chat message

---

## Analytics Events

Track:
- login
- join_table
- leave_table
- hand_start
- hand_end
- reconnect
- sit_out
- chat_sent
- notification_opened

---

## Security Requirements

- Server authoritative logic
- No trust in client

Client must NOT control:
- Cards
- Deck
- Winner
- Valid actions

---

## UX Requirements

Orientation:
- Landscape only

Table UI:

Always visible:
- Pot
- Timer
- Player names
- Chip counts
- Action buttons

Secondary UI:
- Chat (drawer)
- Rules (modal)

---

## Home Screen

- Last club (top)
- Invites
- Club list
- CTA to active table

---

## Critical Constraints

1. Game engine must be fully server-side
2. State must be synchronized via events (not polling)
3. Reconnect must restore full state
4. Spectator data must be filtered at server level
5. House rules must be plug-in based
6. System must support future extensions:
   - Voice chat
   - Advanced rules
   - Multiple tables

---

## Development Priority

1. Core engine (no UI)
2. Realtime sync
3. Table/session system
4. Basic client UI
5. Chat
6. Stats + notifications

---

## Output Expectation from Claude Code

You must:
- Generate modular, production-ready code
- Separate concerns clearly
- Avoid monolithic design
- Ensure testability of game engine
- Include validation layers
- Ensure scalability


DO NOT:
- Put logic in client
- Mix networking with game logic
- Skip validation

---

End of prompt.

