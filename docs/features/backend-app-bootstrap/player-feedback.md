# Player Feedback — backend-app-bootstrap

> Owner: Poker Player Reviewer
> Input: feature-spec.md
> Status: Reviewed — no blocking concerns

---

## What Feels Natural

- **Automatic hand start once two players are seated.** Real home games don't have a
  "start game" button. You sit down, someone deals. The 3-second delay between hands is
  also right — gives time to see the result before cards fly again.

- **60-second disconnect window.** Perfect. In real home games, if your phone dies you
  get maybe a minute before someone takes your chips. 60 seconds is generous but fair.

- **STATE_SNAPSHOT on reconnect.** You rejoin and the table looks exactly as it should.
  No confusion about whose turn it is or what the pot is. This is what players expect.

- **Single WebSocket for all events.** Players don't want to think about connections.
  They tap the table, they see cards, they act. The underlying channel is irrelevant.

- **SYNC_REQUEST.** Good to have. If I open the app and the table looks wrong (rare but
  happens), tapping "refresh" and getting the correct state back is the right behavior.

---

## What Feels Confusing

- **The `role` parameter in JOIN_TABLE (player vs spectator).** Real players don't think
  "I am joining as a player." They either sit down or they watch. The mobile UI must
  make this binary and obvious — a "Take a Seat" button vs a "Watch" button. If the API
  exposes this as a text field, a bug in the client could silently seat a user as
  spectator even though they wanted to play.

- **No visible feedback when an action is rejected.** If a player sends RAISE 500 and
  the server rejects it (not their turn, invalid amount), the player needs to know
  immediately. The ERROR event must surface a human-readable reason, not just a code.
  "It's not your turn" is fine. "ERR_NOT_YOUR_TURN" alone is not.

- **Table config PATCH requires knowing you're an admin.** In a friend group, the host
  creates the club and is the admin. But after a few hands, new players join and nobody
  told them who the admin is. The STATE_SNAPSHOT or club response should clearly indicate
  which user is admin, so the UI can show or hide the config button.

---

## What May Frustrate Players

- **Stale connection with no warning.** If a player's phone goes to background and the
  WS silently dies, the 60-second timer starts. The player comes back at second 58,
  reconnects fine. But if they come back at second 61, they're sitting out with no
  explanation on screen. The client must detect this and show "you were sat out —
  reconnecting..." clearly.

- **Silent message drops on malformed JSON.** If a bug in the mobile client sends
  malformed JSON, the player gets no response and their action appears to have been
  ignored. The server must respond with an ERROR event even for bad payloads. Never
  silently ignore a client message.

- **Starting a new game while players are still reading the result.** The 3-second delay
  is right, but it needs to be enforced strictly. If a bug causes the next hand to start
  in 0.5 seconds, players will see cards without seeing the result of the previous hand.
  This is one of the most frustrating things in an online poker app.

---

## What Feels Unrealistic

- **Nothing specific to the bootstrap plumbing.** The rules of what goes over the wire
  are correct. Private hole cards only to the owner, community cards to everyone,
  pot updates to everyone. The server-authoritative model is how real online poker works.

---

## Social and Gameplay Concerns

- **Chat must survive the connection lifecycle.** If a player's connection drops and
  reconnects, they should still be able to chat. Chat is social glue — losing chat
  history on reconnect makes the table feel cold.

- **PLAYER_LEFT event must be visible.** If my friend leaves mid-hand, I need to know.
  A player disappearing silently from the table is disorienting.

---

## Suggestions to Simplify

1. **ERROR events must include a `message` string in plain language**, not just a code.
   The mobile UI may display it directly to the user in certain cases.

2. **STATE_SNAPSHOT should include the club name and admin_id** so the client can show
   the table name and enable/disable admin controls without a separate HTTP call.

3. **The 60-second timer value should be visible to the client** — ideally included in
   the PLAYER_STATUS "disconnected" event as `reserve_until: <timestamp>`. Players
   watching the table can see a countdown for a disconnected seat.
