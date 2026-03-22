"""
TableSessionManager — orchestrates everything that happens at a live table.

Responsibilities (in order of call flow):
  1. Seat / spectator lifecycle (join, leave, disconnect, reconnect, sit-out)
  2. Delegates game logic to GameEngine (pure, no I/O)
  3. Persists at defined boundaries (join, HAND_END, phase transitions)
  4. Emits filtered WebSocket messages via BroadcastService
  5. Manages turn timers and disconnect timers with asyncio tasks

Threading model:
  - All public methods acquire self._lock before mutating state
  - asyncio tasks (timers) also acquire the lock before acting
  - This makes the manager safe for concurrent WebSocket message handlers

Invariants:
  - self._state is the single source of truth for active game
  - Deck never leaves server memory (never persisted, never broadcast)
  - Engine is called with a deep-copied state; result replaces self._state
"""
from __future__ import annotations

import asyncio
import copy
import time
import uuid
from typing import Optional

from poker_engine.engine.game_engine import GameEngine
from poker_engine.engine.models import (
    Action, ActionType, EngineEvent,
    EvtBlindsPosted, EvtBonusAwarded, EvtCardsDealt, EvtCommunityCards,
    EvtHandResult, EvtPhaseChanged, EvtPlayerActed, EvtPlayerStatus,
    EvtPotUpdated, EvtTurnChanged,
    GameState, HandPhase,
    PlayerSession, PlayerStatus, TableConfig,
)
from poker_engine.engine.view_builder import build_player_view, build_spectator_view
from poker_engine.rules.builtin_rules import load_rules

from ..analytics.events import AnalyticsEvent, AnalyticsEventType
from ..analytics.service import AnalyticsService, NoopAnalyticsService
from ..persistence.adapter import PersistenceAdapter
from ..realtime.broadcaster import BroadcastService
from ..realtime.schemas import (
    BlindsPostedPayload, BonusAwardedPayload, CardDTO, CardsDealtPayload,
    ChatMessagePayload, CommunityCardsPayload, HandResultPayload,
    PhaseChangedPayload, PlayerActedPayload, PlayerJoinedPayload,
    PlayerLeftPayload, PlayerReboughtPayload, PlayerStatusPayload,
    PotDTO, PotUpdatedPayload,
    ServerEnvelope, ServerEventType, ShowdownHandDTO, StateSnapshotDTO,
    TurnChangedPayload, WinnerEntryDTO,
)
from ..tables.models import HandSummary
from .models import ConnectionInfo, JoinErrorCode, JoinResult, ReconnectResult, SpectatorInfo


# How many seconds a disconnected seat is reserved
DISCONNECT_RESERVE_SECONDS = 60

# Delay between hands (gives players time to see the result)
BETWEEN_HANDS_DELAY = 3.0

# Max seats
MAX_PLAYERS = 10


class TableSessionManager:
    """
    Manages the full lifecycle of a single table.
    One instance per active table; created by the table service on demand.
    """

    def __init__(
        self,
        table_id: str,
        club_id: str,
        config: TableConfig,
        persistence: PersistenceAdapter,
        broadcaster: BroadcastService,
        analytics: Optional[AnalyticsService] = None,
        disconnect_reserve_seconds: Optional[int] = None,
    ) -> None:
        self._table_id  = table_id
        self._club_id   = club_id
        self._config    = config

        # None → reads DISCONNECT_RESERVE_SECONDS lazily at call time (supports monkeypatching)
        # explicit value → used directly (for tests and registry wiring)
        self._disconnect_reserve_seconds: Optional[int] = disconnect_reserve_seconds

        rules = load_rules(config.house_rules)
        self._engine    = GameEngine(rules=rules)

        self._persistence = persistence
        self._broadcaster = broadcaster
        self._analytics   = analytics or NoopAnalyticsService()

        # Build initial empty GameState
        self._state = GameState(
            table_id=table_id,
            club_id=club_id,
            config=config,
            phase=HandPhase.WAITING_FOR_PLAYERS,
            players={},
            seat_map={},
            hand=None,
            hand_number=0,
        )

        self._spectators: dict[str, SpectatorInfo] = {}      # uid → info
        self._connections: dict[str, ConnectionInfo] = {}    # uid → conn info
        self._disconnect_tasks: dict[str, asyncio.Task] = {} # uid → task
        self._turn_task: Optional[asyncio.Task]  = None
        self._seq: int = 0
        self._lock = asyncio.Lock()

        # Idempotency: track recently processed request_ids
        self._seen_request_ids: dict[str, float] = {}  # req_id → processed_at

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    def _resolve_reserve_seconds(self) -> int:
        """Return the effective disconnect reserve seconds (instance override or module constant)."""
        if self._disconnect_reserve_seconds is not None:
            return self._disconnect_reserve_seconds
        return DISCONNECT_RESERVE_SECONDS

    @property
    def table_id(self) -> str:
        return self._table_id

    @property
    def player_count(self) -> int:
        return len(self._state.players)

    @property
    def spectator_count(self) -> int:
        return len(self._spectators)

    # -----------------------------------------------------------------------
    # Public: Join / Leave
    # -----------------------------------------------------------------------

    async def join_as_player(
        self, user_id: str, display_name: str, connection_id: str
    ) -> JoinResult:
        async with self._lock:
            # Already seated?
            if user_id in self._state.players:
                # Treat as reconnect
                return await self._do_reconnect(user_id, connection_id)

            # Table full?
            active_seats = sorted(self._state.seat_map.keys())
            used_seats = set(active_seats)
            available = [s for s in range(self._config.max_players) if s not in used_seats]
            if not available:
                return JoinResult(
                    success=False,
                    error_code=JoinErrorCode.TABLE_FULL,
                    error_message="Table is full",
                )

            seat_index = available[0]
            hand_in_progress = (
                self._state.hand is not None
                and self._state.phase not in (
                    HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END
                )
            )

            status = PlayerStatus.WAITING if hand_in_progress else PlayerStatus.ACTIVE
            session = PlayerSession(
                user_id=user_id,
                display_name=display_name,
                seat_index=seat_index,
                stack=self._config.starting_stack,
                status=status,
                original_buy_in=self._config.starting_stack,
            )

            # Mutate state
            self._state.players[user_id] = session
            self._state.seat_map[seat_index] = user_id
            self._connections[user_id] = ConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                role="player",
            )

            # Persist
            await self._persistence.save_player_session(self._table_id, session)

            # Broadcast join event to everyone
            await self._broadcast_all(
                ServerEventType.PLAYER_JOINED,
                PlayerJoinedPayload(
                    user_id=user_id,
                    display_name=display_name,
                    seat_index=seat_index,
                    stack=self._config.starting_stack,
                    role="player",
                ),
            )

            # Send full state snapshot to the new player
            snapshot = self._build_player_snapshot(user_id)
            await self._send_snapshot_to(user_id, snapshot)

            await self._emit_analytics(AnalyticsEventType.JOIN_TABLE, user_id)

            await self._maybe_start_hand_unlocked()

            return JoinResult(success=True, role="player", seat_index=seat_index)

    async def join_as_spectator(
        self, user_id: str, display_name: str, connection_id: str
    ) -> JoinResult:
        async with self._lock:
            if user_id in self._spectators:
                # Re-joining spectator: just update connection and resend snapshot
                self._spectators[user_id].connection_id = connection_id
                snapshot = self._build_spectator_snapshot()
                await self._send_snapshot_to(user_id, snapshot)
                return JoinResult(success=True, role="spectator")

            info = SpectatorInfo(
                user_id=user_id,
                display_name=display_name,
                connection_id=connection_id,
                joined_at=time.time(),
            )
            self._spectators[user_id] = info
            self._connections[user_id] = ConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                role="spectator",
            )

            await self._broadcast_all(
                ServerEventType.PLAYER_JOINED,
                PlayerJoinedPayload(
                    user_id=user_id,
                    display_name=display_name,
                    seat_index=-1,
                    stack=0,
                    role="spectator",
                ),
            )

            snapshot = self._build_spectator_snapshot()
            await self._send_snapshot_to(user_id, snapshot)

            return JoinResult(success=True, role="spectator")

    async def leave(self, user_id: str) -> None:
        async with self._lock:
            await self._do_leave(user_id, voluntary=True)

    # -----------------------------------------------------------------------
    # Public: Disconnect / Reconnect
    # -----------------------------------------------------------------------

    async def disconnect(self, user_id: str) -> None:
        """
        Called when a player's WebSocket connection drops.
        Starts 60-second timer; if they reconnect within the window, seat is saved.
        """
        async with self._lock:
            if user_id in self._spectators:
                # Spectators just leave immediately
                del self._spectators[user_id]
                self._connections.pop(user_id, None)
                return

            player = self._state.players.get(user_id)
            if player is None:
                return

            # Guard: only a fresh disconnect (connected → disconnected) starts the timer.
            # If already disconnected, do nothing — preserve original disconnect_at and timer.
            if not player.is_connected:
                return

            player.is_connected = False
            player.disconnect_at = time.time()
            self._connections.pop(user_id, None)

            reserve_secs = self._resolve_reserve_seconds()
            await self._broadcast_all(
                ServerEventType.PLAYER_STATUS,
                PlayerStatusPayload(
                    user_id=user_id,
                    status="disconnected",
                    stack=player.stack,
                    reserve_until=time.time() + reserve_secs,
                ),
            )

            # Start the reserve timer
            self._cancel_disconnect_timer(user_id)
            task = asyncio.create_task(
                self._run_disconnect_timer(user_id),
                name=f"disconnect_{user_id}",
            )
            self._disconnect_tasks[user_id] = task

    async def reconnect(
        self, user_id: str, connection_id: str
    ) -> ReconnectResult:
        async with self._lock:
            return await self._do_reconnect(user_id, connection_id)

    # -----------------------------------------------------------------------
    # Public: Sit out / Sit in
    # -----------------------------------------------------------------------

    async def sit_out(self, user_id: str) -> None:
        async with self._lock:
            player = self._state.players.get(user_id)
            if player is None or player.status == PlayerStatus.SIT_OUT:
                return
            await self._force_sit_out_unlocked(user_id, reason="voluntary")

    async def sit_in(self, user_id: str) -> None:
        async with self._lock:
            player = self._state.players.get(user_id)
            if player is None or player.status != PlayerStatus.SIT_OUT:
                return

            # Only allow sit-in if they have chips
            if player.stack <= 0:
                return

            player.status = PlayerStatus.WAITING  # will join next hand

            await self._broadcast_all(
                ServerEventType.PLAYER_STATUS,
                PlayerStatusPayload(
                    user_id=user_id,
                    status=PlayerStatus.WAITING.value,
                    stack=player.stack,
                ),
            )
            await self._persistence.save_player_session(self._table_id, player)
            await self._maybe_start_hand_unlocked()

    async def rebuy(self, user_id: str, amount: int) -> None:
        async with self._lock:
            player = self._state.players.get(user_id)
            if player is None:
                return  # not seated

            # Only between hands
            hand_active = (
                self._state.hand is not None
                and self._state.phase not in (HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END)
            )
            if hand_active:
                return

            # Cap at half the original buy-in
            max_rebuy = player.original_buy_in // 2
            if amount > max_rebuy or amount <= 0:
                return

            player.stack += amount
            player.rebuy_count += 1

            await self._persistence.save_player_session(self._table_id, player)
            await self._broadcast_all(
                ServerEventType.PLAYER_REBOUGHT,
                PlayerReboughtPayload(
                    user_id=user_id,
                    amount=amount,
                    new_stack=player.stack,
                    rebuy_count=player.rebuy_count,
                ),
            )

    # -----------------------------------------------------------------------
    # Public: Actions
    # -----------------------------------------------------------------------

    async def handle_action(
        self,
        user_id: str,
        action_type: str,
        amount: int,
        request_id: str,
    ) -> None:
        """
        Route a player action through the engine.
        Idempotent: duplicate request_id within TTL is silently dropped.
        Raises ValueError on invalid action (caller should send ERROR back).
        """
        async with self._lock:
            # Idempotency check
            if self._is_duplicate_request(request_id):
                return
            self._mark_request(request_id)

            action = Action(
                user_id=user_id,
                action_type=ActionType(action_type),
                amount=amount,
            )

            # Engine validates and applies
            new_state, events = self._engine.apply_action(self._state, action)
            self._state = new_state

            # Cancel current turn timer (will be rescheduled by events)
            self._cancel_turn_timer()

            await self._dispatch_events(events)
            await self._maybe_persist_phase()

    async def handle_chat(
        self, user_id: str, display_name: str, message: str
    ) -> None:
        import uuid as _uuid
        msg_id = str(_uuid.uuid4())
        ts = time.time()

        from ..chat.models import ChatMessage
        chat_msg = ChatMessage(
            id=msg_id,
            table_id=self._table_id,
            user_id=user_id,
            display_name=display_name,
            message=message,
            timestamp=ts,
        )
        # Persist async (fire and forget); log on failure
        import logging as _logging
        _task = asyncio.create_task(self._persistence.save_chat_message(chat_msg))
        _task.add_done_callback(
            lambda t: _logging.getLogger(__name__).warning(
                "save_chat_message failed: %s", t.exception()
            ) if not t.cancelled() and t.exception() else None
        )

        await self._broadcast_all(
            ServerEventType.CHAT_MESSAGE,
            ChatMessagePayload(
                message_id=msg_id,
                user_id=user_id,
                display_name=display_name,
                message=message,
                ts=ts,
            ),
        )
        await self._emit_analytics(AnalyticsEventType.CHAT_SENT, user_id)

    async def send_sync(self, user_id: str) -> None:
        """Re-send the full state snapshot on SYNC_REQUEST."""
        async with self._lock:
            if user_id in self._state.players:
                snap = self._build_player_snapshot(user_id)
            elif user_id in self._spectators:
                snap = self._build_spectator_snapshot()
            else:
                return
            await self._send_snapshot_to(user_id, snap)

    # -----------------------------------------------------------------------
    # Internal: Reconnect helper (called with lock held)
    # -----------------------------------------------------------------------

    async def _do_reconnect(
        self, user_id: str, connection_id: str
    ) -> ReconnectResult:
        self._cancel_disconnect_timer(user_id)

        player = self._state.players.get(user_id)
        if player is None:
            return ReconnectResult(
                success=False,
                error_code="NOT_SEATED",
                error_message="Player is not at this table",
            )

        player.is_connected = True
        player.disconnect_at = None
        self._connections[user_id] = ConnectionInfo(
            connection_id=connection_id,
            user_id=user_id,
            role="player",
        )

        await self._broadcast_all(
            ServerEventType.PLAYER_STATUS,
            PlayerStatusPayload(
                user_id=user_id,
                status=player.status.value,
                stack=player.stack,
            ),
        )

        snapshot = self._build_player_snapshot(user_id)
        await self._send_snapshot_to(user_id, snapshot)
        await self._emit_analytics(AnalyticsEventType.RECONNECT, user_id)

        # If enough players are now ready, start the next hand
        await self._maybe_start_hand_unlocked()

        return ReconnectResult(success=True, role="player")

    # -----------------------------------------------------------------------
    # Internal: Leave helper (called with lock held)
    # -----------------------------------------------------------------------

    async def _do_leave(self, user_id: str, voluntary: bool = True) -> None:
        self._cancel_disconnect_timer(user_id)

        if user_id in self._spectators:
            del self._spectators[user_id]
            self._connections.pop(user_id, None)
            await self._broadcast_all(
                ServerEventType.PLAYER_LEFT,
                PlayerLeftPayload(user_id=user_id, role="spectator"),
            )
            return

        player = self._state.players.get(user_id)
        if player is None:
            return

        hand_in_progress = (
            self._state.hand is not None
            and self._state.phase not in (
                HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END
            )
            and player.status == PlayerStatus.ACTIVE
        )

        if hand_in_progress:
            # Auto-fold the departing player
            if (
                self._state.hand
                and self._state.hand.current_turn_seat == player.seat_index
            ):
                try:
                    fold_action = Action(user_id=user_id, action_type=ActionType.FOLD)
                    new_state, events = self._engine.apply_action(self._state, fold_action)
                    self._state = new_state
                    self._cancel_turn_timer()
                    await self._dispatch_events(events)
                except Exception:
                    pass  # fold failed (e.g. wrong phase) — just remove
            else:
                player.status = PlayerStatus.FOLDED

        seat = player.seat_index
        del self._state.players[user_id]
        self._state.seat_map.pop(seat, None)
        self._connections.pop(user_id, None)

        await self._persistence.delete_player_session(self._table_id, user_id)
        await self._broadcast_all(
            ServerEventType.PLAYER_LEFT,
            PlayerLeftPayload(user_id=user_id, role="player"),
        )
        if voluntary:
            await self._emit_analytics(AnalyticsEventType.LEAVE_TABLE, user_id)

    # -----------------------------------------------------------------------
    # Internal: Timer management
    # -----------------------------------------------------------------------

    async def _run_disconnect_timer(self, user_id: str) -> None:
        """60-second countdown. If player hasn't reconnected, sit them out."""
        try:
            await asyncio.sleep(self._resolve_reserve_seconds())
        except asyncio.CancelledError:
            return

        async with self._lock:
            player = self._state.players.get(user_id)
            if player and not player.is_connected:
                await self._force_sit_out_unlocked(user_id, reason="disconnect_timeout")

    async def _run_turn_timer(
        self, deadline: float, expected_seat: int
    ) -> None:
        """Wait until deadline, then apply timeout if turn hasn't advanced."""
        remaining = deadline - time.time()
        if remaining > 0:
            try:
                await asyncio.sleep(remaining)
            except asyncio.CancelledError:
                return

        async with self._lock:
            hand = self._state.hand
            if hand is None or hand.current_turn_seat != expected_seat:
                return  # turn already advanced

            new_state, events = self._engine.handle_timeout(self._state)
            self._state = new_state
            await self._dispatch_events(events)
            await self._maybe_persist_phase()

    def _schedule_turn_timer(self, deadline: float, seat: int) -> None:
        self._cancel_turn_timer()
        self._turn_task = asyncio.create_task(
            self._run_turn_timer(deadline, seat),
            name=f"turn_{self._table_id}_{seat}",
        )

    def _cancel_turn_timer(self) -> None:
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
        self._turn_task = None

    def _cancel_disconnect_timer(self, user_id: str) -> None:
        task = self._disconnect_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    # -----------------------------------------------------------------------
    # Internal: Hand start
    # -----------------------------------------------------------------------

    async def _maybe_start_hand_unlocked(self) -> None:
        """
        Check if we can start a new hand.
        Must be called while holding self._lock.
        """
        if self._state.phase not in (
            HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END
        ):
            return  # hand already in progress

        eligible = [
            p for p in self._state.players.values()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.WAITING)
            and p.stack > 0
            and p.is_connected
        ]
        if len(eligible) < 2:
            return

        # Schedule with a small delay so HAND_END result is visible
        asyncio.create_task(
            self._start_hand_after_delay(),
            name=f"start_hand_{self._table_id}",
        )

    async def _start_hand_after_delay(self) -> None:
        await asyncio.sleep(BETWEEN_HANDS_DELAY)
        async with self._lock:
            if self._state.phase not in (
                HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END
            ):
                return

            eligible = [
                p for p in self._state.players.values()
                if p.status in (PlayerStatus.ACTIVE, PlayerStatus.WAITING)
                and p.stack > 0
            ]
            if len(eligible) < 2:
                return

            try:
                new_state, events = self._engine.start_hand(self._state)
                self._state = new_state
                await self._dispatch_events(events)
                await self._persist_phase_snapshot()
                await self._emit_analytics(
                    AnalyticsEventType.HAND_START,
                    user_id="system",
                )
            except Exception as exc:
                # Log but don't crash the table
                print(f"[ERROR] start_hand failed on {self._table_id}: {exc}")

    # -----------------------------------------------------------------------
    # Internal: Event dispatch
    # -----------------------------------------------------------------------

    async def _dispatch_events(self, events: list[EngineEvent]) -> None:
        """
        Fan out engine events to the appropriate recipients via broadcaster.
        - EvtCardsDealt → send ONLY to that player (private hole cards)
        - All other events → broadcast to all (players + spectators)
        Post-event: schedule turn timer if EvtTurnChanged is present.
        """
        for event in events:

            if isinstance(event, EvtCardsDealt):
                # Private — only to the named player
                cards = [CardDTO(rank=c.rank.value, suit=c.suit.value) for c in event.cards]
                await self._send_to_player(
                    event.user_id,
                    ServerEventType.CARDS_DEALT,
                    CardsDealtPayload(your_cards=cards),
                )

            elif isinstance(event, EvtPhaseChanged):
                phase_hand = self._state.hand
                phase_pot_total = 0
                if phase_hand:
                    phase_pot_total = (
                        sum(p.amount for p in phase_hand.pots)
                        + sum(phase_hand.betting.bets_by_player.values())
                    )
                await self._broadcast_all(
                    ServerEventType.PHASE_CHANGED,
                    PhaseChangedPayload(phase=event.phase.value, pot_total=phase_pot_total),
                )
                if event.phase == HandPhase.HAND_END:
                    await self._on_hand_end()

            elif isinstance(event, EvtCommunityCards):
                cards = [CardDTO(rank=c.rank.value, suit=c.suit.value) for c in event.cards]
                await self._broadcast_all(
                    ServerEventType.COMMUNITY_CARDS,
                    CommunityCardsPayload(cards=cards, phase=event.phase.value),
                )

            elif isinstance(event, EvtPlayerActed):
                acted_hand = self._state.hand
                betting = acted_hand.betting if acted_hand else None
                acted_pot_total = 0
                if acted_hand:
                    acted_pot_total = (
                        sum(p.amount for p in acted_hand.pots)
                        + sum(acted_hand.betting.bets_by_player.values())
                    )
                await self._broadcast_all(
                    ServerEventType.PLAYER_ACTED,
                    PlayerActedPayload(
                        user_id=event.user_id,
                        action=event.action_type.value,
                        amount=event.amount,
                        stack_remaining=event.stack_remaining,
                        new_current_bet=betting.current_bet if betting else 0,
                        min_raise_to=betting.min_raise_to if betting else 0,
                        pot_total=acted_pot_total,
                    ),
                )

            elif isinstance(event, EvtTurnChanged):
                hand = self._state.hand
                player = self._state.players.get(event.user_id)
                call_amount = 0
                min_raise_to = 0
                max_raise = 0
                if hand and player:
                    player_bet = hand.betting.bets_by_player.get(event.user_id, 0)
                    call_amount = max(0, hand.betting.current_bet - player_bet)
                    min_raise_to = hand.betting.min_raise_to
                    my_legal_max = player_bet + player.stack
                    # Effective stack cap: cap raise at what any active opponent can match.
                    # ALL_IN opponents can't respond to a raise so they don't set the cap.
                    active_opponents = [
                        p for uid, p in self._state.players.items()
                        if uid != event.user_id and p.status == PlayerStatus.ACTIVE
                    ]
                    if active_opponents:
                        max_opponent_total = max(
                            hand.betting.bets_by_player.get(p.user_id, 0) + p.stack
                            for p in active_opponents
                        )
                        max_raise = min(my_legal_max, max_opponent_total)
                    else:
                        max_raise = my_legal_max
                secs_remaining = (
                    max(0, round(event.deadline - time.time()))
                    if event.deadline is not None
                    else None
                )
                await self._broadcast_all(
                    ServerEventType.TURN_CHANGED,
                    TurnChangedPayload(
                        seat=event.seat,
                        user_id=event.user_id,
                        deadline=event.deadline,
                        seconds_remaining=secs_remaining,
                        call_amount=call_amount,
                        min_raise_to=min_raise_to,
                        max_raise=max_raise,
                    ),
                )
                if event.deadline is not None:
                    self._schedule_turn_timer(event.deadline, event.seat)

            elif isinstance(event, EvtPotUpdated):
                pots = [
                    PotDTO(amount=p.amount, eligible_player_ids=p.eligible_player_ids)
                    for p in event.pots
                ]
                await self._broadcast_all(
                    ServerEventType.POT_UPDATED,
                    PotUpdatedPayload(pots=pots),
                )

            elif isinstance(event, EvtPlayerStatus):
                await self._broadcast_all(
                    ServerEventType.PLAYER_STATUS,
                    PlayerStatusPayload(
                        user_id=event.user_id,
                        status=event.status.value,
                        stack=event.stack,
                    ),
                )

            elif isinstance(event, EvtHandResult):
                # Player-centric winners: one entry per user who won chips
                winner_entries = [
                    WinnerEntryDTO(
                        user_id=uid,
                        amount=amount,
                        hand_description=event.hand_descriptions.get(uid, "uncontested"),
                    )
                    for uid, amount in event.winnings.items()
                ]
                # Showdown hands: only non-folded players who reached showdown
                showdown_hands = [
                    ShowdownHandDTO(
                        user_id=uid,
                        hole_cards=[CardDTO(rank=c.rank.value, suit=c.suit.value) for c in cards],
                        hand_description=event.hand_descriptions.get(uid, ""),
                    )
                    for uid, cards in event.showdown_cards.items()
                ]
                # Final board and hand metadata
                result_hand = self._state.hand
                hand_id = result_hand.hand_id if result_hand else ""
                final_board = (
                    [CardDTO(rank=c.rank.value, suit=c.suit.value) for c in result_hand.community_cards]
                    if result_hand else []
                )
                await self._broadcast_all(
                    ServerEventType.HAND_RESULT,
                    HandResultPayload(
                        hand_id=hand_id,
                        hand_number=self._state.hand_number,
                        winners=winner_entries,
                        final_board=final_board,
                        showdown_hands=showdown_hands,
                        pot_total=event.pot_total,
                    ),
                )

            elif isinstance(event, EvtBlindsPosted):
                await self._broadcast_all(
                    ServerEventType.BLINDS_POSTED,
                    BlindsPostedPayload(
                        small_blind_user_id=event.small_blind_user_id,
                        small_blind_amount=event.small_blind_amount,
                        big_blind_user_id=event.big_blind_user_id,
                        big_blind_amount=event.big_blind_amount,
                    ),
                )

            elif isinstance(event, EvtBonusAwarded):
                await self._broadcast_all(
                    ServerEventType.BONUS_AWARDED,
                    BonusAwardedPayload(
                        rule_id=event.rule_id,
                        from_user_id=event.from_user_id,
                        to_user_id=event.to_user_id,
                        amount=event.amount,
                    ),
                )

    # -----------------------------------------------------------------------
    # Internal: Hand end bookkeeping
    # -----------------------------------------------------------------------

    async def _on_hand_end(self) -> None:
        """Persist hand summary, update stats, trigger next hand scheduling."""
        hand = self._state.hand
        if hand is None:
            return

        # Build HandSummary
        start_stacks = hand.stacks_at_start
        end_stacks = {uid: p.stack for uid, p in self._state.players.items()}
        winner_ids = list({
            uid
            for w in (hand.winners or [])
            for uid in w.get("winner_ids", [])
        })

        summary = HandSummary(
            hand_id=hand.hand_id,
            table_id=self._table_id,
            club_id=self._club_id,
            hand_number=self._state.hand_number,
            phase_reached=hand.phase.value,
            winner_ids=winner_ids,
            pot_total=sum(p.amount for p in hand.pots),
            player_ids=list(self._state.players.keys()),
            stacks_before=start_stacks,
            stacks_after=end_stacks,
            community_cards=[str(c) for c in hand.community_cards],
            timestamp=time.time(),
        )
        await self._persistence.save_hand_summary(summary)

        # Persist updated player stacks
        for uid, player in self._state.players.items():
            await self._persistence.save_player_session(self._table_id, player)

        await self._emit_analytics(AnalyticsEventType.HAND_END, "system")

        # Schedule next hand
        await self._maybe_start_hand_unlocked()

    # -----------------------------------------------------------------------
    # Internal: Force sit-out (called with lock held)
    # -----------------------------------------------------------------------

    async def _force_sit_out_unlocked(self, user_id: str, reason: str) -> None:
        player = self._state.players.get(user_id)
        if player is None:
            return

        # If it's this player's turn, fold them first
        hand = self._state.hand
        if (
            hand is not None
            and hand.current_turn_seat == player.seat_index
            and player.status == PlayerStatus.ACTIVE
        ):
            try:
                fold = Action(user_id=user_id, action_type=ActionType.FOLD)
                new_state, events = self._engine.apply_action(self._state, fold)
                self._state = new_state
                self._cancel_turn_timer()
                await self._dispatch_events(events)
            except Exception:
                pass

        player = self._state.players.get(user_id)
        if player:
            player.status = PlayerStatus.SIT_OUT
            await self._broadcast_all(
                ServerEventType.PLAYER_STATUS,
                PlayerStatusPayload(
                    user_id=user_id,
                    status=PlayerStatus.SIT_OUT.value,
                    stack=player.stack,
                ),
            )
            await self._persistence.save_player_session(self._table_id, player)
            await self._emit_analytics(AnalyticsEventType.SIT_OUT, user_id)

    # -----------------------------------------------------------------------
    # Internal: Persistence
    # -----------------------------------------------------------------------

    async def _persist_phase_snapshot(self) -> None:
        """Snapshot current state (without deck) for reconnect/crash recovery."""
        # Use spectator view as basis — hole cards masked, deck excluded
        snapshot = build_spectator_view(self._state)
        await self._persistence.save_game_state_snapshot(self._table_id, snapshot)

    async def _maybe_persist_phase(self) -> None:
        """Persist on phase transitions."""
        if self._state.hand is None:
            return
        if self._state.phase in (
            HandPhase.FLOP, HandPhase.TURN, HandPhase.RIVER,
            HandPhase.DEAL_HOLE_CARDS,
        ):
            await self._persist_phase_snapshot()

    # -----------------------------------------------------------------------
    # Internal: Broadcasting helpers
    # -----------------------------------------------------------------------

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def _broadcast_all(
        self, event_type: ServerEventType, payload: object
    ) -> None:
        """Broadcast to everyone (players + spectators)."""
        env = ServerEnvelope.build(
            seq=self._next_seq(),
            table_id=self._table_id,
            event_type=event_type,
            payload=payload,
        )
        await self._broadcaster.broadcast_to_table(self._table_id, env)

    async def _send_to_player(
        self, user_id: str, event_type: ServerEventType, payload: object
    ) -> None:
        env = ServerEnvelope.build(
            seq=self._next_seq(),
            table_id=self._table_id,
            event_type=event_type,
            payload=payload,
        )
        await self._broadcaster.send_to_player(self._table_id, user_id, env)

    async def _send_snapshot_to(self, user_id: str, snapshot: dict) -> None:
        env = ServerEnvelope.build(
            seq=self._next_seq(),
            table_id=self._table_id,
            event_type=ServerEventType.STATE_SNAPSHOT,
            payload=snapshot,
        )
        await self._broadcaster.send_to_player(self._table_id, user_id, env)

    def _build_player_snapshot(self, user_id: str) -> dict:
        return build_player_view(self._state, user_id)

    def _build_spectator_snapshot(self) -> dict:
        return build_spectator_view(self._state)

    # -----------------------------------------------------------------------
    # Internal: Idempotency
    # -----------------------------------------------------------------------

    def _is_duplicate_request(self, request_id: str) -> bool:
        from ..config import settings
        ttl = settings.request_id_ttl_seconds
        now = time.time()
        # Clean up old entries
        self._seen_request_ids = {
            k: v for k, v in self._seen_request_ids.items() if now - v < ttl
        }
        return request_id in self._seen_request_ids

    def _mark_request(self, request_id: str) -> None:
        self._seen_request_ids[request_id] = time.time()

    # -----------------------------------------------------------------------
    # Internal: Analytics
    # -----------------------------------------------------------------------

    async def _emit_analytics(
        self, event_type: AnalyticsEventType, user_id: str
    ) -> None:
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            table_id=self._table_id,
            club_id=self._club_id,
        )
        asyncio.create_task(self._analytics.track(event))
