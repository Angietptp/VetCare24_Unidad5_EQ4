"""Pruebas de Money (Etapa 3)."""

from decimal import Decimal

import pytest

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money


def test_siempre_tiene_dos_decimales():
    m = Money.mxn("313")
    assert m.monto == Decimal("313.00")
    assert m.monto.as_tuple().exponent == -2


def test_redondeo_half_up():
    assert Money.mxn("10.005").monto == Decimal("10.01")
    assert Money.mxn("10.004").monto == Decimal("10.00")


def test_acepta_int_str_y_decimal():
    assert Money.mxn(5) == Money.mxn("5.00") == Money.mxn(Decimal("5"))


@pytest.mark.parametrize("valor", [1.5, True, "abc", "NaN", "Infinity", None])
def test_rechaza_valores_no_validos(valor):
    with pytest.raises(InvarianteViolada) as error:
        Money.mxn(valor)
    assert error.value.codigo == "MONTO_INVALIDO"


def test_rechaza_negativos():
    with pytest.raises(InvarianteViolada) as error:
        Money.mxn("-0.01")
    assert error.value.codigo == "MONTO_INVALIDO"


def test_suma_y_por():
    assert Money.mxn("10.10") + Money.mxn("0.20") == Money.mxn("10.30")
    assert Money.mxn("10.10").por(3) == Money.mxn("30.30")
    assert Money.mxn("10.10").por(0) == Money.cero()


def test_por_rechaza_cantidad_invalida():
    for cantidad in (-1, 1.5, True):
        with pytest.raises(InvarianteViolada) as error:
            Money.mxn("1").por(cantidad)
        assert error.value.codigo == "CANTIDAD_INVALIDA"


def test_suma_de_varios_y_vacia():
    assert Money.suma([Money.mxn("1.10"), Money.mxn("2.20")]) == Money.mxn("3.30")
    assert Money.suma([]) == Money.cero()


def test_el_decimal_evita_el_error_clasico_del_float():
    assert Money.mxn("0.10") + Money.mxn("0.20") == Money.mxn("0.30")


def test_comparaciones_incluyen_el_umbral():
    assert Money.mxn("1500.00") >= Money.mxn("1500")
    assert Money.mxn("1499.99") < Money.mxn("1500")


def test_no_se_suma_con_otros_tipos():
    with pytest.raises(TypeError):
        Money.mxn("1") + 1


def test_texto_legible():
    assert str(Money.mxn("1500")) == "1500.00 MXN"
