"""
Dev bot — connects to the demo table as Bob and auto-acts (check or call).

Usage:
    python dev_bot.py

Requires: pip install websockets
"""
import asyncio
import json
import uuid

import websockets

TABLE_ID   = "00000000-0000-0000-0000-000000000020"
BOB_TOKEN  = "dev_00000000-0000-0000-0000-000000000002"
BOB_ID     = BOB_TOKEN[4:]   # strip "dev_"
WS_URL     = f"ws://10.100.102.3:8000/ws/table/{TABLE_ID}?token={BOB_TOKEN}"

def _envelope(msg_type: str, payload: dict | None = None) -> str:
    return json.dumps({
        "type": msg_type,
        "request_id": str(uuid.uuid4()),
        "table_id": TABLE_ID,
        "payload": payload or {},
    })


async def run() -> None:
    print(f"[Bot] Connecting to {WS_URL}")

    # Per-street bet tracking
    current_bet = 0   # highest outstanding bet on the current street
    bob_bet     = 0   # how much Bob has put in on the current street

    async with websockets.connect(WS_URL) as ws:
        print("[Bot] Connected — joining as player")
        await ws.send(_envelope("JOIN_TABLE", {"role": "player"}))

        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = msg.get("type")
            payload    = msg.get("payload", {})

            if event_type == "STATE_SNAPSHOT":
                players = payload.get("players", {})
                n_connected = sum(1 for p in players.values() if p.get("is_connected"))
                hand = payload.get("hand")
                if hand:
                    betting = hand.get("betting", {})
                    current_bet = betting.get("current_bet", 0)
                    bob_bet     = betting.get("bets_by_player", {}).get(BOB_ID, 0)
                    print(f"[Bot] STATE_SNAPSHOT — connected: {n_connected}, "
                          f"current_bet={current_bet}, bob_bet={bob_bet}")
                else:
                    current_bet = 0
                    bob_bet     = 0
                    print(f"[Bot] STATE_SNAPSHOT — players connected: {n_connected}, no active hand")

            elif event_type == "BLINDS_POSTED":
                # Pre-flop baseline: BB sets the opening bet
                bb_amount = payload.get("big_blind_amount", 0)
                sb_amount = payload.get("small_blind_amount", 0)
                current_bet = bb_amount
                if payload.get("big_blind_user_id") == BOB_ID:
                    bob_bet = bb_amount
                elif payload.get("small_blind_user_id") == BOB_ID:
                    bob_bet = sb_amount
                else:
                    bob_bet = 0
                print(f"[Bot] BLINDS_POSTED — current_bet={current_bet}, bob_bet={bob_bet}")

            elif event_type == "PHASE_CHANGED":
                phase = payload.get("phase", "")
                # Reset per-street bets only on post-flop streets.
                # PRE_FLOP must NOT reset — BLINDS_POSTED fires before this event
                # and has already set current_bet/bob_bet correctly.
                if phase.upper() in ("FLOP", "TURN", "RIVER"):
                    current_bet = 0
                    bob_bet     = 0
                    print(f"[Bot] PHASE_CHANGED({phase}) — bets reset for new street")
                else:
                    print(f"[Bot] PHASE_CHANGED({phase}) — bets preserved")

            elif event_type == "PLAYER_ACTED":
                action = payload.get("action")
                uid    = payload.get("user_id")
                amount = payload.get("amount", 0)
                if action == "raise":
                    # amount = raise-to total; this is the new current_bet
                    current_bet = amount
                    if uid == BOB_ID:
                        bob_bet = amount
                elif action == "call":
                    # amount = delta; current_bet unchanged
                    if uid == BOB_ID:
                        bob_bet = current_bet
                # check / fold: no change to bet levels
                print(f"[Bot] PLAYER_ACTED — {str(uid)[:8]} {action} {amount} "
                      f"(street_bet={current_bet})")

            elif event_type == "TURN_CHANGED":
                acting_uid = payload.get("user_id")
                if acting_uid == BOB_ID:
                    amount_to_call = current_bet - bob_bet
                    action = "call" if amount_to_call > 0 else "check"
                    print(f"[Bot] My turn — {action} "
                          f"(street_bet={current_bet}, my_bet={bob_bet})")
                    await ws.send(_envelope("ACTION", {"action": action, "amount": 0}))
                else:
                    print(f"[Bot] Turn changed — acting player: {str(acting_uid)[:8]}")

            elif event_type == "HAND_RESULT":
                winners = payload.get("winners", [])
                print(f"[Bot] Hand over — winners: {winners}")
                # Reset for next hand
                current_bet = 0
                bob_bet     = 0

            elif event_type == "ERROR":
                print(f"[Bot] ERROR from server: {payload}")

            else:
                print(f"[Bot] {event_type}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[Bot] Disconnected.")
