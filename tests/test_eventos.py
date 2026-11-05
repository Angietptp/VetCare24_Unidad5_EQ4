"""Pruebas de los Domain Events (Etapa 6)."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.eventos import (
    CitaAgendada,
    CitaCancelada,
    CitaModificada,
    CitaRealizada,
    EventoDeDominio,
)
from vetcare24.domain.money import Money

AHORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _agendada(**cambios):
    datos = {
        "ocurrido_en": AHORA, "cita_id": "C1", "propietario_id": "P1", "mascota_id": "M1",
        "servicios": (("S1", 2), ("S2", 1)), "total": Money.mxn("700"),
    }
    return CitaAgendada(**{**datos, **cambios})


def test_el_evento_es_inmutable():
    evento = _agendada()
    with pytest.raises(dataclasses.FrozenInstanceError):
        evento.cita_id = "C2"


def test_el_nombre_es_el_de_la_clase():
    assert _agendada().nombre == "CitaAgendada"
    assert CitaRealizada(ocurrido_en=AHORA, cita_id="C1", propietario_id="P1",
                         mascota_id="M1").nombre == "CitaRealizada"


def test_dos_eventos_con_los_mismos_datos_son_iguales():
    assert _agendada() == _agendada()
    assert _agendada() != _agendada(cita_id="C2")


def test_exige_fecha_con_zona_horaria():
    for invalida in (datetime(2026, 10, 31, 12, 0), "2026-10-31", None):
        with pytest.raises(InvarianteViolada) as error:
            _agendada(ocurrido_en=invalida)
        assert error.value.codigo == "EVENTO_SIN_ZONA_HORARIA"


def test_acepta_cualquier_zona_horaria():
    monterrey = timezone(timedelta(hours=-6))
    assert _agendada(ocurrido_en=datetime(2026, 10, 31, 6, 0, tzinfo=monterrey)).cita_id == "C1"


def test_a_diccionario_deja_solo_texto_numeros_y_listas():
    assert _agendada().a_diccionario() == {
        "evento": "CitaAgendada",
        "ocurrido_en": "2026-10-31T12:00:00+00:00",
        "cita_id": "C1", "propietario_id": "P1", "mascota_id": "M1",
        "servicios": [["S1", 2], ["S2", 1]],
        "total": "700.00",
    }


def test_cancelada_y_modificada_llevan_su_detalle():
    cancelada = CitaCancelada(ocurrido_en=AHORA, cita_id="C1", propietario_id="P1",
                              mascota_id="M1", estado_anterior="CONFIRMADA")
    assert cancelada.a_diccionario()["estado_anterior"] == "CONFIRMADA"
    modificada = CitaModificada(ocurrido_en=AHORA, cita_id="C1", propietario_id="P1",
                                mascota_id="M1", servicios_anteriores=(("S1", 2),),
                                servicios_nuevos=(("S1", 3),))
    datos = modificada.a_diccionario()
    assert datos["servicios_anteriores"] == [["S1", 2]]
    assert datos["servicios_nuevos"] == [["S1", 3]]


def test_todos_los_eventos_son_eventos_de_dominio():
    assert issubclass(CitaAgendada, EventoDeDominio)
    assert issubclass(CitaModificada, EventoDeDominio)
