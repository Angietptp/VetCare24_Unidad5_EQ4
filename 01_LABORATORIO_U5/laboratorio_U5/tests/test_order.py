import pytest

from src.domain import CustomerHasDebt, Order


def test_vip_discount():
    o = Order(100, vip=True)
    assert o.confirm() == 85
    assert o.status == "CONFIRMED"


def test_regular_no_discount():
    assert Order(100).confirm() == 100


def test_customer_debt():
    with pytest.raises(CustomerHasDebt):
        Order(100).confirm(customer_debt=50)


@pytest.mark.parametrize("total", [0, -1])
def test_invalid_total(total):
    with pytest.raises(ValueError):
        Order(total).confirm()


def test_vip_discount_200():
    order = Order(200, vip=True)
    assert order.confirm() == 170
    assert order.discount == 30


def test_regular_customer_200_no_discount():
    order = Order(200)
    assert order.confirm() == 200
    assert order.discount == 0
