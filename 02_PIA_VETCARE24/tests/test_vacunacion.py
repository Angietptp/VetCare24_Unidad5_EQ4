"""Dominio de Vacunación (Etapa 9): el registro, el historial y el esquema."""

from datetime import UTC, date, datetime

import pytest

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.eventos import CitaAgendada, EventoDeDominio, VacunacionRegistrada
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.vacunacion import (
    FRECUENCIA_MAXIMA_DIAS,
    EsquemaDeVacunacion,
    Vacunacion,
    normalizar_vacuna,
)

HORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
MASCOTA = Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro")


def _codigo(funcion):
    with pytest.raises(InvarianteViolada) as error:
        funcion()
    return error.value.codigo


def _vacunacion(**cambios):
    datos = {"vacunacion_id": "V1", "mascota_id": "M1", "vacuna": "Rabia",
             "fecha_aplicacion": date(2026, 10, 1)}
    return Vacunacion(**{**datos, **cambios})


# --- nombre de la vacuna ---

def test_normalizar_vacuna_ignora_mayusculas_y_espacios():
    assert normalizar_vacuna("  Rabia  ") == "rabia"
    assert normalizar_vacuna("Triple   Felina") == "triple felina"
    assert normalizar_vacuna("RABIA") == normalizar_vacuna("rabia")


def test_normalizar_vacuna_rechaza_vacia():
    for vacio in ("", "   ", None):
        assert _codigo(lambda vacio=vacio: normalizar_vacuna(vacio)) == "VACUNA_VACIA"


# --- Vacunacion ---

def test_vacunacion_valida_y_limpia_los_espacios():
    v = _vacunacion(vacuna="  Triple   Felina ", lote=" L-001  ")
    assert (v.vacuna, v.lote, v.clave) == ("Triple Felina", "L-001", "triple felina")
    assert (v.vacunacion_id, v.mascota_id, v.fecha_aplicacion) == ("V1", "M1", date(2026, 10, 1))
    assert _vacunacion().lote is None


def test_vacunacion_exige_sus_datos():
    assert _codigo(lambda: _vacunacion(vacunacion_id="")) == "ID_VACIO"
    assert _codigo(lambda: _vacunacion(mascota_id=" ")) == "MASCOTA_REQUERIDA"
    assert _codigo(lambda: _vacunacion(vacuna="")) == "VACUNA_VACIA"
    assert _codigo(lambda: _vacunacion(lote="  ")) == "LOTE_VACIO"


@pytest.mark.parametrize("fecha", ["2026-10-01", datetime(2026, 10, 1, 8, 0), None, 20261001])
def test_la_fecha_de_aplicacion_debe_ser_una_fecha_sin_hora(fecha):
    assert _codigo(lambda: _vacunacion(fecha_aplicacion=fecha)) == "FECHA_INVALIDA"


def test_registrar_deja_el_evento_con_el_detalle():
    v = Vacunacion.registrar(vacunacion_id="V1", mascota=MASCOTA, vacuna="Rabia",
                             fecha_aplicacion=date(2026, 10, 1), lote="L-9", ocurrido_en=HORA)
    assert v.mascota_id == "M1"
    assert v.extraer_eventos() == (VacunacionRegistrada(
        ocurrido_en=HORA, vacunacion_id="V1", mascota_id="M1", vacuna="Rabia",
        fecha_aplicacion=date(2026, 10, 1), lote="L-9"),)
    assert v.extraer_eventos() == ()  # se entregan una sola vez


def test_reconstituir_no_emite_eventos():
    assert _vacunacion().extraer_eventos() == ()


def test_la_vacunacion_se_identifica_por_su_id():
    assert _vacunacion() == _vacunacion(vacuna="Otra")
    assert hash(_vacunacion()) == hash(_vacunacion())
    assert _vacunacion() != _vacunacion(vacunacion_id="V2") and _vacunacion() != "V1"
    assert "V1" in repr(_vacunacion())


# --- evento ---

def test_el_evento_se_serializa_con_la_fecha_en_texto():
    evento = VacunacionRegistrada(
        ocurrido_en=HORA, vacunacion_id="V1", mascota_id="M1", vacuna="Rabia",
        fecha_aplicacion=date(2026, 10, 1), lote=None)
    assert evento.a_diccionario() == {
        "evento": "VacunacionRegistrada", "ocurrido_en": "2026-10-31T12:00:00+00:00",
        "vacunacion_id": "V1", "mascota_id": "M1", "vacuna": "Rabia",
        "fecha_aplicacion": "2026-10-01", "lote": None}


def test_cada_evento_dice_que_agregado_lo_emitio():
    vacuna = VacunacionRegistrada(
        ocurrido_en=HORA, vacunacion_id="V1", mascota_id="M1", vacuna="Rabia",
        fecha_aplicacion=date(2026, 10, 1), lote=None)
    assert (vacuna.agregado_tipo, vacuna.agregado_id) == ("Vacunacion", "V1")
    cita = CitaAgendada(ocurrido_en=HORA, cita_id="C7", propietario_id="P1", mascota_id="M1",
                        servicios=(("S1", 1),), total=Money.mxn("10"))
    assert (cita.agregado_tipo, cita.agregado_id) == ("Cita", "C7")
    assert EventoDeDominio(ocurrido_en=HORA).agregado_tipo == ""


# --- EsquemaDeVacunacion ---

def _esquema(**cambios):
    datos = {"vacuna": "Rabia", "frecuencia_dias": 365, "requiere_refuerzo": False,
             "validado": True}
    return EsquemaDeVacunacion(**{**datos, **cambios})


def test_esquema_valido():
    e = _esquema(vacuna="  Triple  Felina ")
    assert (e.vacuna, e.clave, e.frecuencia_dias, e.requiere_refuerzo, e.validado) == (
        "Triple Felina", "triple felina", 365, False, True)
    assert _esquema(frecuencia_dias=FRECUENCIA_MAXIMA_DIAS).frecuencia_dias == 36_500


@pytest.mark.parametrize("frecuencia", [0, -1, 1.5, True, "30", 36_501])
def test_esquema_rechaza_frecuencias_invalidas(frecuencia):
    assert _codigo(lambda: _esquema(frecuencia_dias=frecuencia)) == "FRECUENCIA_INVALIDA"


def test_esquema_valida_el_resto_de_sus_campos():
    assert _codigo(lambda: _esquema(vacuna=" ")) == "VACUNA_VACIA"
    assert _codigo(lambda: _esquema(requiere_refuerzo=1)) == "REFUERZO_INVALIDO"
    assert _codigo(lambda: _esquema(validado="si")) == "VALIDADO_INVALIDO"


def test_dos_esquemas_son_iguales_si_dicen_lo_mismo():
    assert _esquema(vacuna="RABIA") == _esquema(vacuna="rabia")
    assert hash(_esquema(vacuna="RABIA")) == hash(_esquema(vacuna="rabia"))
    assert _esquema() != _esquema(validado=False) and _esquema() != "Rabia"
    assert "Rabia" in repr(_esquema()) and "cada 365 días" in repr(_esquema())
