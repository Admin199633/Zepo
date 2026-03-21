"""
Tests for realtime DTO schemas — validation correctness.
"""
import pytest

from backend.realtime.schemas import (
    ActionPayload, CardDTO, ChatPayload, ClientEnvelope, ClientMessageType,
    JoinTablePayload, ServerEnvelope, ServerEventType, StateSnapshotDTO,
)


class TestCardDTO:
    def test_valid_card(self):
        c = CardDTO(rank="A", suit="S")
        assert c.rank == "A"

    def test_masked_card(self):
        c = CardDTO(rank="?", suit="?")
        assert c.rank == "?"

    def test_invalid_rank_raises(self):
        with pytest.raises(Exception):
            CardDTO(rank="X", suit="S")

    def test_invalid_suit_raises(self):
        with pytest.raises(Exception):
            CardDTO(rank="A", suit="Z")


class TestServerEnvelope:
    def test_build_produces_valid_envelope(self):
        from backend.realtime.schemas import PhaseChangedPayload
        env = ServerEnvelope.build(
            seq=1,
            table_id="t1",
            event_type=ServerEventType.PHASE_CHANGED,
            payload=PhaseChangedPayload(phase="PRE_FLOP"),
        )
        assert env.seq == 1
        assert env.table_id == "t1"
        assert env.type == ServerEventType.PHASE_CHANGED
        assert env.payload["phase"] == "PRE_FLOP"

    def test_seq_is_monotonic_contract(self):
        """seq must increase — this is a contract test."""
        envs = [
            ServerEnvelope.build(
                seq=i,
                table_id="t1",
                event_type=ServerEventType.CHAT_MESSAGE,
                payload={"x": i},
            )
            for i in range(1, 6)
        ]
        seqs = [e.seq for e in envs]
        assert seqs == sorted(seqs)

    def test_to_json_serializable(self):
        env = ServerEnvelope.build(
            seq=1,
            table_id="t1",
            event_type=ServerEventType.ERROR,
            payload={"code": "TEST", "message": "test"},
        )
        json_str = env.to_json()
        assert '"seq"' in json_str
        assert '"table_id"' in json_str


class TestClientEnvelope:
    def test_valid_action_envelope(self):
        env = ClientEnvelope(
            type=ClientMessageType.ACTION,
            request_id="req-1",
            table_id="t1",
            payload={"action": "fold", "amount": 0},
        )
        assert env.type == ClientMessageType.ACTION

    def test_requires_request_id(self):
        with pytest.raises(Exception):
            ClientEnvelope(type=ClientMessageType.ACTION, table_id="t1")


class TestActionPayload:
    def test_valid_fold(self):
        p = ActionPayload(action="fold")
        assert p.action == "fold"
        assert p.amount == 0

    def test_valid_raise(self):
        p = ActionPayload(action="raise", amount=200)
        assert p.amount == 200

    def test_negative_amount_raises(self):
        with pytest.raises(Exception):
            ActionPayload(action="raise", amount=-50)

    def test_invalid_action_raises(self):
        with pytest.raises(Exception):
            ActionPayload(action="bet")  # "bet" is not a valid action


class TestChatPayload:
    def test_valid_message(self):
        p = ChatPayload(message="שלום")
        assert p.message == "שלום"

    def test_empty_message_raises(self):
        with pytest.raises(Exception):
            ChatPayload(message="   ")

    def test_too_long_message_raises(self):
        with pytest.raises(Exception):
            ChatPayload(message="x" * 501)

    def test_strips_whitespace(self):
        p = ChatPayload(message="  hello  ")
        assert p.message == "hello"


class TestJoinTablePayload:
    def test_default_role_is_player(self):
        p = JoinTablePayload()
        assert p.role == "player"

    def test_spectator_role(self):
        p = JoinTablePayload(role="spectator")
        assert p.role == "spectator"

    def test_invalid_role_raises(self):
        with pytest.raises(Exception):
            JoinTablePayload(role="admin")
