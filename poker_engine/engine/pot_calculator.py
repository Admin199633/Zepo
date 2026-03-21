"""
Pot and side-pot calculation.

Side pots arise when a player goes all-in for less than the current bet.
Each pot has a set of eligible players (those who contributed to it).

Algorithm:
  1. Collect each player's total investment this hand.
  2. Sort by investment ascending.
  3. For each all-in level, create a pot capped at that level × eligible players.
  4. Any remaining investment above the last all-in goes into a separate pot.
"""
from __future__ import annotations

from .models import Pot


def calculate_pots(
    contributions: dict[str, int],      # user_id → total chips put in this hand
    active_player_ids: set[str],        # user_ids still in hand (not folded)
) -> list[Pot]:
    """
    Build the list of pots (main + side pots) from contributions.

    `active_player_ids` are players eligible to win each pot they contributed to.
    Folded players contributed chips but are not eligible.
    """
    if not contributions:
        return []

    # Only players who are eligible (not folded) can be in a pot
    eligible = {uid for uid in contributions if uid in active_player_ids}

    # Sort eligible players by contribution (ascending) to find all-in levels
    sorted_contribs = sorted(
        [(uid, amt) for uid, amt in contributions.items()],
        key=lambda x: x[1],
    )

    pots: list[Pot] = []
    already_allocated: dict[str, int] = {uid: 0 for uid in contributions}
    prev_level = 0

    # Find unique all-in contribution levels
    levels = sorted({amt for _, amt in sorted_contribs})

    for level in levels:
        pot_amount = 0
        pot_eligible: list[str] = []

        for uid, contrib in contributions.items():
            # Each player contributes min(their total, level) - prev_level
            contrib_to_this_pot = min(contrib, level) - prev_level
            if contrib_to_this_pot > 0:
                pot_amount += contrib_to_this_pot
                already_allocated[uid] += contrib_to_this_pot

            # Eligible if they contributed at least up to this level
            if contrib >= level and uid in eligible:
                pot_eligible.append(uid)

        if pot_amount > 0:
            pots.append(Pot(amount=pot_amount, eligible_player_ids=pot_eligible))

        prev_level = level

    # Merge pots with identical eligible sets for cleaner output
    return _merge_pots(pots)


def _merge_pots(pots: list[Pot]) -> list[Pot]:
    """Merge consecutive pots with the same eligible set."""
    if not pots:
        return []
    merged: list[Pot] = [Pot(pots[0].amount, list(pots[0].eligible_player_ids))]
    for pot in pots[1:]:
        last = merged[-1]
        if set(last.eligible_player_ids) == set(pot.eligible_player_ids):
            merged[-1] = Pot(
                amount=last.amount + pot.amount,
                eligible_player_ids=last.eligible_player_ids,
            )
        else:
            merged.append(Pot(pot.amount, list(pot.eligible_player_ids)))
    return merged


def award_pots(
    pots: list[Pot],
    winners_by_pot: dict[int, list[str]],  # pot_index → [winner_user_ids]
) -> dict[str, int]:
    """
    Distribute pot amounts to winners.
    Ties split the pot; any odd chip goes to first winner (by list order).
    Returns dict user_id → chips won.
    """
    winnings: dict[str, int] = {}
    for i, pot in enumerate(pots):
        winners = winners_by_pot.get(i, [])
        if not winners:
            continue
        per_winner, remainder = divmod(pot.amount, len(winners))
        for j, uid in enumerate(winners):
            amount = per_winner + (1 if j == 0 else 0) * remainder
            winnings[uid] = winnings.get(uid, 0) + amount
    return winnings
