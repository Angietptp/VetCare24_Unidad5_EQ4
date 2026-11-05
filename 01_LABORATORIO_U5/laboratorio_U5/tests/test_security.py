from datetime import UTC, datetime, timedelta

from src.security import can_cancel

FIXED_NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

def test_owner_within_24h():
    now = datetime.now(UTC)
    assert can_cancel("NEW", 1, 1, False, now - timedelta(hours=1), now)

def test_stranger_denied():
    now = datetime.now(UTC)
    assert not can_cancel("NEW", 1, 2, False, now, now)

def test_shipped_denied_even_admin():
    now = datetime.now(UTC)
    assert not can_cancel("SHIPPED", 1, 1, True, now, now)

def test_expired_denied():
    now = datetime.now(UTC)
    assert not can_cancel("NEW", 1, 1, False, now - timedelta(hours=25), now)


def test_admin_cancels_new_order_of_other_user():
    assert can_cancel("NEW", 1, 2, True, FIXED_NOW, FIXED_NOW)


def test_owner_exactly_24h_denied():
    assert not can_cancel("NEW", 1, 1, False, FIXED_NOW - timedelta(hours=24), FIXED_NOW)
