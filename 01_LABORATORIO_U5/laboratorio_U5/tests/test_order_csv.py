"""Casos CP01 a CP12 de datos/casos_de_prueba.csv ejecutados como prueba parametrizada.

Los CSV no se cargan solos: se leen aquí con csv.DictReader.
"""
import csv
from pathlib import Path

import pytest

from src.domain import CustomerHasDebt, Order

DATOS = Path(__file__).resolve().parent.parent / "datos"


def _leer(nombre):
    with (DATOS / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


CLIENTES = {int(c["cliente_id"]): c for c in _leer("clientes_prueba.csv")}
PEDIDOS = {int(p["pedido_id"]): p for p in _leer("pedidos_prueba.csv")}
CASOS = [c for c in _leer("casos_de_prueba.csv") if c["accion"] == "confirmar"]


def _esperado(caso):
    # CP08 en el CSV describe el comportamiento original; tras el TDD se rechaza.
    if caso["caso_id"] == "CP08":
        return ValueError, None
    texto = caso["resultado_esperado"]
    if texto == "CustomerHasDebt":
        return CustomerHasDebt, None
    if texto == "ValueError":
        return ValueError, None
    return None, float(texto.split("cobro")[1])


@pytest.mark.parametrize("caso", CASOS, ids=[c["caso_id"] for c in CASOS])
def test_casos_del_csv(caso):
    pedido = PEDIDOS[int(caso["pedido_id"])]
    cliente = CLIENTES[int(pedido["cliente_id"])]
    orden = Order(
        float(pedido["total"]),
        vip=cliente["es_vip"] == "1",
        status=pedido["estado_inicial"],
    )
    deuda = float(cliente["deuda"])
    error, cobro = _esperado(caso)
    if error:
        with pytest.raises(error):
            orden.confirm(customer_debt=deuda)
    else:
        assert orden.confirm(customer_debt=deuda) == pytest.approx(cobro, abs=0.005)
        assert orden.status == "CONFIRMED"
