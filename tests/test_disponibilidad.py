"""Pruebas de Disponibilidad (Etapa 5)."""

import pytest

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money


def _codigo(funcion):
    with pytest.raises(InvarianteViolada) as error:
        funcion()
    return error.value.codigo


def test_parte_de_la_capacidad_completa():
    d = Disponibilidad({"S1": 5, "S2": 0})
    assert (d.disponible("S1"), d.disponible("S2"), d.reservado("S1")) == (5, 0, 0)
    assert d.como_mapa() == {"S1": 5, "S2": 0}


def test_se_construye_desde_el_catalogo():
    catalogo = {"S1": ServicioVeterinario("S1", "Consulta", Money.mxn("1"), capacidad=7)}
    assert Disponibilidad.desde_catalogo(catalogo).disponible("S1") == 7


def test_servicio_desconocido_cuenta_como_cero():
    assert Disponibilidad({"S1": 5}).disponible("S9") == 0


@pytest.mark.parametrize("capacidad", [-1, 1.5, True, "3"])
def test_rechaza_capacidades_invalidas(capacidad):
    assert _codigo(lambda: Disponibilidad({"S1": capacidad})) == "CAPACIDAD_INVALIDA"


def test_rechaza_id_vacio():
    assert _codigo(lambda: Disponibilidad({"": 1})) == "ID_VACIO"


def test_reservar_y_liberar():
    d = Disponibilidad({"S1": 5})
    d.reservar({"S1": 3})
    assert (d.disponible("S1"), d.reservado("S1")) == (2, 3)
    d.liberar({"S1": 2})
    assert (d.disponible("S1"), d.reservado("S1")) == (4, 1)


def test_reservar_es_todo_o_nada():
    d = Disponibilidad({"S1": 5, "S2": 1})
    assert _codigo(lambda: d.reservar({"S1": 2, "S2": 2})) == "CAPACIDAD_INSUFICIENTE"
    assert (d.disponible("S1"), d.disponible("S2")) == (5, 1)  # S1 no quedó reservada


def test_reservar_servicio_desconocido_falla():
    d = Disponibilidad({"S1": 5})
    assert _codigo(lambda: d.reservar({"S9": 1})) == "CAPACIDAD_INSUFICIENTE"


def test_se_puede_reservar_exactamente_la_capacidad():
    d = Disponibilidad({"S1": 5})
    d.reservar({"S1": 5})
    assert d.disponible("S1") == 0


def test_no_se_libera_mas_de_lo_reservado_y_es_todo_o_nada():
    d = Disponibilidad({"S1": 5, "S2": 5})
    d.reservar({"S1": 2, "S2": 1})
    assert _codigo(lambda: d.liberar({"S1": 2, "S2": 2})) == "LIBERACION_INVALIDA"
    assert (d.reservado("S1"), d.reservado("S2")) == (2, 1)


def test_faltantes_simula_una_liberacion_sin_modificar_nada():
    d = Disponibilidad({"S1": 5})
    d.reservar({"S1": 4})  # quedan 1
    assert d.faltantes({"S1": 3}) == ("S1",)
    assert d.faltantes({"S1": 3}, liberando={"S1": 2}) == ()
    assert d.disponible("S1") == 1
