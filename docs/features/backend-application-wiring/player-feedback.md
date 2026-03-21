# Player Feedback — backend-application-wiring

> Owner: Poker Player Reviewer
> Input: feature-spec.md
> Status: Reviewed — two concerns, neither blocking

---

## What Feels Natural

- **Explicit JOIN_TABLE after connecting.** This matches how real apps work — you load
  the table, you see it, then you choose to sit down or watch. The separation is natural.

- **Automatic hand start once two players are seated.** Still correct. Dealt hands should
  feel automatic, not button-triggered.

- **Reserve_until timestamp on disconnect.** Including the exact deadline in the
  disconnect event is exactly what a watching friend or worried player needs. "Lior has
  60 seconds to reconnect" is clear. A bare "disconnected" status is not.

- **Separate player and spectator views.** Spectators cannot see hole cards. Players
  cannot see opponents' hole cards. This is exactly how live poker works and it must
  never be compromised.

---

## What Feels Confusing

- **STATE_SNAPSHOT sent only after JOIN_TABLE, not on connect.** This is a technical
  trade-off (noted as resolved in the spec), but the client developer needs to know that
  the table state is not visible until they send JOIN_TABLE. If a mobile client developer
  doesn't read the docs, they might show a blank table for a second while waiting for
  that event. This needs to be documented explicitly in the integration guide.

- **No acknowledgment on WS connect before JOIN_TABLE.** When the WS opens, nothing
  happens until the client sends JOIN_TABLE. An inexperienced client developer might
  wonder if the connection worked. A simple `CONNECTED` event on WS accept would remove
  any ambiguity. (Not requesting a scope change — just flagging this as a future
  improvement.)

---

## What May Frustrate Players

- **Console OTP in development.** Fine for developers. But if someone tests the app
  for the first time and doesn't know to look at the server terminal for the OTP,
  they'll be stuck. The API response should hint that OTP was "sent" without saying
  where (keeping the interface consistent between dev and prod).

- **Silent action drops on duplicate request_id.** This is correct behavior for
  idempotency, but the player must not see their action button freeze with no feedback.
  The mobile client must optimistically show the result while waiting for the server
  event. This is a mobile client responsibility, but worth stating explicitly.

- **Reconnect replaces the old WS handle.** If a player's phone reconnects while the
  old connection is still technically "open" (bad network handshake), the old connection
  must be properly cleaned up. Otherwise the player gets two PLAYER_STATUS events and
  the mobile UI may flicker. This is a quality item for the broadcaster implementation.

---

## What Feels Unrealistic

- **Nothing in the gameplay logic.** The engine behavior is unchanged. Blinds, hand
  progression, all-in handling, and timeout logic are all correct.

---

## Social and Gameplay Concerns

- **A player who was mid-hand when the server restarted will rejoin to a table with
  no hand in progress.** Their chips are gone (in-memory reset). This is called out as
  a known limitation. But from a player's perspective, losing chips to a server restart
  is extremely frustrating. Until the SQLite adapter is fully implemented, this server
  should only run in private/test environments. Recommend adding a visible warning to
  `GET /health` in development mode: `"state_persistence": "in_memory_volatile"`.

- **Chat history is not preserved across reconnects** (in-memory). Same category as
  above — acceptable for MVP but needs a note in the health endpoint or documentation.

---

## Suggestions to Simplify

1. Add `"state_persistence": "in_memory_volatile"` to `GET /health` response when
   `app_env == "development"`. Gives operators an immediate signal that data is not
   durable. Zero implementation cost.

2. All ERROR events should echo back the `request_id` of the triggering message. This
   allows the mobile client to correlate errors to specific user actions. The
   `ErrorPayload` model already has `request_id: Optional[str]` — it should always
   be populated when the error is caused by a client message.
