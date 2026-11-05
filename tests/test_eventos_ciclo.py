"""Cada transición de la cita emite su evento (Etapa 6)."""

from datetime import UTC, date, datetime

import pytest

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.ciclo_de_vida import CicloDeVidaDeCita
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import PrecondicionNoCumplida, TransicionInvalida
from vetcare24.domain.eventos import CitaAgendada, CitaCancelada, CitaModificada, CitaRealizada
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario

HORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
CICLO = CicloDeVidaDeCita(reloj=lambda: HORA)
PROPIETARIO = Propietario("P1", "Ana")
CATALOGO = {
    "S1": ServicioVeterinario("S1", "Consulta", Money.mxn("300"), 5),
    "S2": ServicioVeterinario("S2", "Vacuna", Money.mxn("100"), 5),
}


def _cita(lineas=(("S1", 2), ("S2", 1))):
    return Cita(
        cita_id="C1", propietario_id="P1", mascota_id="M1",
        lineas=[ServicioSolicitado(s, q) for s, q in lineas],
        fecha_solicitud=date(2026, 10, 2), estado=EstadoCita.SOLICITADA, autorizada=True,
    )


def _confirmada():
    cita, disp = _cita(), Disponibilidad.desde_catalogo(CATALOGO)
    CICLO.confirmar(cita, PROPIETARIO, CATALOGO, disp)
    return cita, disp


def test_confirmar_emite_cita_agendada_con_el_detalle():
    cita, _ = _confirmada()
    assert cita.extraer_eventos() == (CitaAgendada(
        ocurrido_en=HORA, cita_id="C1", propietario_id="P1", mascota_id="M1",
        servicios=(("S1", 2), ("S2", 1)), total=Money.mxn("700"),
    ),)


def test_realizar_emite_cita_realizada():
    cita, _ = _confirmada()
    cita.extraer_eventos()
    CICLO.realizar(cita)
    assert cita.extraer_eventos() == (CitaRealizada(
        ocurrido_en=HORA, cita_id="C1", propietario_id="P1", mascota_id="M1"),)


def test_cancelar_indica_desde_que_estado_se_cancelo():
    cita, disp = _confirmada()
    cita.extraer_eventos()
    CICLO.cancelar(cita, disp)
    (evento,) = cita.extraer_eventos()
    assert isinstance(evento, CitaCancelada) and evento.estado_anterior == "CONFIRMADA"

    otra = _cita()
    CICLO.cancelar(otra, Disponibilidad.desde_catalogo(CATALOGO))
    assert otra.extraer_eventos()[0].estado_anterior == "SOLICITADA"


def test_modificar_emite_lo_anterior_y_lo_nuevo():
    cita = _cita()
    CICLO.modificar(cita, [ServicioSolicitado("S2", 4)], CATALOGO,
                    Disponibilidad.desde_catalogo(CATALOGO))
    (evento,) = cita.extraer_eventos()
    assert isinstance(evento, CitaModificada)
    assert evento.servicios_anteriores == (("S1", 2), ("S2", 1))
    assert evento.servicios_nuevos == (("S2", 4),)


def test_completar_deja_los_eventos_en_orden():
    cita, _ = _confirmada()
    CICLO.realizar(cita)
    assert [e.nombre for e in cita.extraer_eventos()] == ["CitaAgendada", "CitaRealizada"]


def test_extraer_entrega_una_sola_vez():
    cita, _ = _confirmada()
    assert len(cita.extraer_eventos()) == 1
    assert cita.extraer_eventos() == ()


def test_una_accion_rechazada_no_emite_eventos():
    cita = _cita()
    disp = Disponibilidad.desde_catalogo(CATALOGO)
    with pytest.raises(PrecondicionNoCumplida):
        CICLO.confirmar(cita, Propietario("P1", "Ana", activo=False), CATALOGO, disp)
    with pytest.raises(TransicionInvalida):
        CICLO.realizar(cita)
    assert cita.extraer_eventos() == ()


def test_el_reloj_por_omision_da_hora_con_zona_horaria():
    cita, disp = _cita(), Disponibilidad.desde_catalogo(CATALOGO)
    CicloDeVidaDeCita().confirmar(cita, PROPIETARIO, CATALOGO, disp)
    assert cita.extraer_eventos()[0].ocurrido_en.tzinfo is not None
