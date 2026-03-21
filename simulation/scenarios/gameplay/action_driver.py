"""
N-player hand driver and ActionScript for realistic gameplay scenarios.

Generalises _drive_hand (2-player) and _drive_three_player_hand (3-player)
to any number of players, with optional scripted fold/raise injection.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActionScript:
    """
    Per-player scripted action overrides for a multi-hand session.

    fold_on_turns:  set of (hand_index, turn_within_hand) pairs where the
                    player sends FOLD instead of the default check/call.
                    turn_within_hand is a 0-indexed count of TURN_CHANGED
                    events received for this player within the current hand.

    raise_on_turns: set of (hand_index, turn_within_hand) pairs where the
                    player sends RAISE (amount = 2 * big_blind) instead of
                    the default check/call.  Only injected when the player
                    has nothing to call (can_check=True) to guarantee legality.

    hand_index is 0-indexed: the first hand driven is index 0.
    """
    fold_on_turns: set = field(default_factory=set)
    raise_on_turns: set = field(default_factory=set)


def drive_n_player_hand(
    owner,
    players: list,
    table_id: str,
    hand_index: int = 0,
    scripts: dict | None = None,
    big_blind: int = 20,
    max_iter: int = 300,
) -> dict:
    """
    Drive one complete hand for N players, from BLINDS_POSTED to HAND_RESULT.

    Calling convention
    ------------------
    The caller must NOT drain BLINDS_POSTED before calling this function.
    The driver drains BLINDS_POSTED itself to initialise the betting state
    from the payload (needed for correct SB/BB accounting in pre-flop).

    After each call to drive_n_player_hand, the next hand will auto-start
    after BETWEEN_HANDS_DELAY.  The next call to drive_n_player_hand will
    then drain that hand's BLINDS_POSTED.

    Bet tracking
    ------------
    The driver maintains:

      current_bet     : highest total bet in the current betting round
      bets_this_round : {user_id: total_chips_committed_in_this_round}

    This enables precise can_check determination:
      amount_to_call = current_bet - bets_this_round.get(uid, 0)
      can_check      = (amount_to_call <= 0)

    On BLINDS_POSTED:         current_bet = bb_amount; bets = {sb_uid: sb_amt, bb_uid: bb_amt}
    On PLAYER_ACTED{call}:    bets[uid] += amount
    On PLAYER_ACTED{raise}:   bets[uid] = amount (total); current_bet = amount
    On PHASE_CHANGED{FLOP…}:  current_bet = 0; bets = {}
    On COMMUNITY_CARDS:        current_bet = 0; bets = {}

    Parameters
    ----------
    owner       : Oracle player.  Must be inside connect() context.
    players     : All players [owner, p1, p2, ...]; owner must be index 0.
    table_id    : Active table id.
    hand_index  : 0-indexed hand number (used for ActionScript key lookup).
    scripts     : Optional {player_index: ActionScript}.
    big_blind   : Big blind amount (used for raise sizing).
    max_iter    : Safety guard — raises RuntimeError if exceeded.

    Returns
    -------
    HAND_RESULT event payload dict (keys: winners, showdown_cards, pot_total)
    """
    scripts = scripts or {}
    uid_to_idx: dict[str, int] = {p.user_id: i for i, p in enumerate(players)}
    turn_counts: dict[int, int] = {i: 0 for i in range(len(players))}

    # -----------------------------------------------------------------------
    # Step 1: drain BLINDS_POSTED from oracle and initialise bet state.
    # Non-owner players also need to drain BLINDS_POSTED so their logs are
    # in sync (they receive it as a broadcast).
    # -----------------------------------------------------------------------
    blinds_msg = owner.drain_until("BLINDS_POSTED", max_msgs=100)
    for p in players[1:]:
        p.drain_until("BLINDS_POSTED", max_msgs=100)

    payload = blinds_msg["payload"]
    sb_uid: str = payload.get("small_blind_user_id", "")
    sb_amt: int = payload.get("small_blind_amount", 0)
    bb_uid: str = payload.get("big_blind_user_id", "")
    bb_amt: int = payload.get("big_blind_amount", 0)

    current_bet: int = bb_amt
    bets_this_round: dict[str, int] = {sb_uid: sb_amt, bb_uid: bb_amt}

    # -----------------------------------------------------------------------
    # Step 2: main drive loop.
    # -----------------------------------------------------------------------
    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            for p in players[1:]:
                p.drain_until("HAND_RESULT", max_msgs=200)
            return msg["payload"]

        elif t == "BLINDS_POSTED":
            # Unexpected second BLINDS_POSTED inside the same hand drive.
            # Reset bet tracking (e.g. if the driver is reused for subsequent hands
            # without the multi-hand wrapper — should not occur normally).
            inner = msg["payload"]
            sb_uid = inner.get("small_blind_user_id", "")
            sb_amt = inner.get("small_blind_amount", 0)
            bb_uid = inner.get("big_blind_user_id", "")
            bb_amt = inner.get("big_blind_amount", 0)
            current_bet = bb_amt
            bets_this_round = {sb_uid: sb_amt, bb_uid: bb_amt}

        elif t == "PHASE_CHANGED":
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                current_bet = 0
                bets_this_round = {}

        elif t == "COMMUNITY_CARDS":
            current_bet = 0
            bets_this_round = {}

        elif t == "PLAYER_ACTED":
            ep = msg["payload"]
            action = ep.get("action", "")
            amount = ep.get("amount", 0)
            uid = ep.get("user_id", "")
            if action == "call":
                bets_this_round[uid] = bets_this_round.get(uid, 0) + amount
            elif action == "raise":
                # amount is the TOTAL raise target (see validator.py)
                bets_this_round[uid] = amount
                current_bet = amount

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            if acting_uid not in uid_to_idx:
                continue

            idx = uid_to_idx[acting_uid]
            actor = players[idx]
            turn_key = (hand_index, turn_counts[idx])

            already_bet = bets_this_round.get(acting_uid, 0)
            amount_to_call = current_bet - already_bet
            can_check = (amount_to_call <= 0)

            action = "check" if can_check else "call"
            raise_amount = 0

            script = scripts.get(idx)
            if script is not None:
                if turn_key in script.fold_on_turns:
                    action = "fold"
                elif turn_key in script.raise_on_turns and can_check:
                    action = "raise"
                    raise_amount = 2 * big_blind

            actor.send_action(table_id, action, raise_amount)
            turn_counts[idx] += 1

            if action == "raise":
                bets_this_round[acting_uid] = raise_amount
                current_bet = raise_amount

    raise RuntimeError(
        f"HAND_RESULT not reached within {max_iter} iterations (hand_index={hand_index}). "
        f"Owner event types (last 20): {owner.log.types()[-20:]}"
    )
