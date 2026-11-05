"""TDD (paso E3): un pedido ya confirmado no puede confirmarse otra vez.

Fase RED: la prueba falla porque el código original permitía confirmar dos veces.
Fase GREEN: se agregó la guarda «already confirmed» al inicio de Order.confirm().
"""
import pytest

from src.domain import Order


def test_cannot_confirm_twice():
    order = Order(100)
    order.confirm()
    with pytest.raises(ValueError, match="already confirmed"):
        order.confirm()
