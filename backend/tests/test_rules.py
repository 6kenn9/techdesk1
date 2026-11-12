"""Модульні тести бізнес-правил, які не потребують бази даних."""
from decimal import Decimal

import pytest

from app.core.security import RateLimiter
from app.services.domain import ALLOWED, STAGES, order_total

def test_lifecycle_moves_forward_only():
    for current, following in zip(STAGES, STAGES[1:]):
        assert following in ALLOWED[current]
    assert "completed" not in ALLOWED and "returned" not in ALLOWED  # кінцеві етапи
    # скасований пристрій ще в сервісі: єдиний крок — повернути його клієнту
    assert ALLOWED["cancelled"] == {"returned"}

@pytest.mark.parametrize("stage", ["registered", "diagnostics", "waiting_approval", "in_repair"])
def test_cancel_allowed_before_pickup(stage):
    assert "cancelled" in ALLOWED[stage]

def test_cannot_cancel_ready_order():
    assert "cancelled" not in ALLOWED["ready_for_pickup"]
    assert "returned" in ALLOWED["ready_for_pickup"]  # клієнт не забрав або відмовився платити

def test_extra_work_goes_back_to_approval():
    assert "waiting_approval" in ALLOWED["in_repair"]

def test_repair_requires_approval_stage():
    assert "in_repair" not in ALLOWED["diagnostics"]
    assert ALLOWED["registered"] == {"diagnostics", "cancelled"}

def test_order_total():
    assert order_total(Decimal("750.00"), Decimal("2499.50")) == Decimal("3249.50")
    assert order_total(Decimal("750.00"), Decimal("2499.50"), warranty_case=True) == 0

def test_rate_limiter_window():
    moment = [0.0]
    limiter = RateLimiter(limit=2, window=60, clock=lambda: moment[0])
    key = ("127.0.0.1", "user@example.com")
    assert not limiter.hit(key) and not limiter.hit(key)
    assert limiter.blocked(key) and limiter.hit(key)
    moment[0] = 61
    assert not limiter.blocked(key)
    limiter.hit(key)
    limiter.reset(key)
    assert not limiter.blocked(key)
