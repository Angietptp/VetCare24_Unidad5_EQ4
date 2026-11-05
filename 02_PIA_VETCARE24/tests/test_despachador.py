"""Despacho de eventos (Etapa 6)."""

from datetime import UTC, datetime

import pytest

from vetcare24.application.despachador import Despachador, RegistroDeEventos
from vetcare24.domain.eventos import CitaAgendada, CitaCancelada, CitaRealizada, EventoDeDominio
from vetcare24.domain.money import Money

AHORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _realizada(cita_id="C1"):
    return CitaRealizada(ocurrido_en=AHORA, cita_id=cita_id, propietario_id="P1", mascota_id="M1")


def _agendada(cita_id="C1"):
    return CitaAgendada(ocurrido_en=AHORA, cita_id=cita_id, propietario_id="P1", mascota_id="M1",
                        servicios=(("S1", 1),), total=Money.mxn("10"))


def test_el_manejador_solo_recibe_los_eventos_de_su_tipo():
    recibidos = []
    despachador = Despachador()
    despachador.suscribir(CitaRealizada, recibidos.append)
    despachador.publicar([_agendada(), _realizada()])
    assert [e.nombre for e in recibidos] == ["CitaRealizada"]


def test_suscribirse_al_tipo_base_recibe_todos_en_orden():
    registro, despachador = RegistroDeEventos(), Despachador()
    despachador.suscribir(EventoDeDominio, registro)
    despachador.publicar([_agendada("C1"), _realizada("C1"), _agendada("C2")])
    assert [r.secuencia for r in registro.registrados] == [1, 2, 3]
    assert [r.evento.nombre for r in registro.registrados] == [
        "CitaAgendada", "CitaRealizada", "CitaAgendada"]
    assert len(registro.de_tipo(CitaAgendada)) == 2
    assert registro.de_tipo(CitaCancelada) == ()


def test_varios_manejadores_reciben_el_mismo_evento():
    a, b = [], []
    despachador = Despachador()
    despachador.suscribir(CitaRealizada, a.append)
    despachador.suscribir(CitaRealizada, b.append)
    despachador.publicar([_realizada()])
    assert len(a) == len(b) == 1


def test_un_manejador_que_falla_no_impide_los_demas_y_queda_registrado():
    def malo(evento):
        raise RuntimeError("fallo del manejador")

    recibidos = []
    despachador = Despachador()
    despachador.suscribir(CitaRealizada, malo)
    despachador.suscribir(CitaRealizada, recibidos.append)
    despachador.publicar([_realizada()])
    assert len(recibidos) == 1
    assert len(despachador.fallos) == 1
    fallo = despachador.fallos[0]
    assert fallo.manejador is malo and isinstance(fallo.error, RuntimeError)
    assert fallo.evento.nombre == "CitaRealizada"


def test_publicar_sin_eventos_o_sin_suscriptores_no_hace_nada():
    despachador = Despachador()
    despachador.publicar([])
    despachador.publicar([_realizada()])
    assert despachador.fallos == []


def test_solo_se_suscribe_a_tipos_de_evento():
    despachador = Despachador()
    for invalido in (int, "CitaRealizada", None):
        with pytest.raises(TypeError):
            despachador.suscribir(invalido, lambda e: None)
