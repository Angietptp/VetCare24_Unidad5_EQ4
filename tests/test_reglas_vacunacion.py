"""Specifications del seguimiento de vacunación (Etapa 9, D-06 ajustada)."""

from datetime import date

import pytest

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.reglas_vacunacion import (
    EsquemaDefinido,
    EsquemaValidado,
    RequiereRefuerzo,
    VacunacionEnContexto,
    seguimiento_calculable,
    seguimiento_pendiente,
)
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion

ULTIMA = Vacunacion(vacunacion_id="V1", mascota_id="M1", vacuna="Rabia",
                    fecha_aplicacion=date(2026, 10, 1))


def _contexto(esquema="valido"):
    esquemas = {
        "valido": EsquemaDeVacunacion(vacuna="rabia", frecuencia_dias=365,
                                      requiere_refuerzo=True, validado=True),
        "sin_validar": EsquemaDeVacunacion(vacuna="Rabia", frecuencia_dias=365,
                                           requiere_refuerzo=False, validado=False),
        "ninguno": None,
    }
    return VacunacionEnContexto(ULTIMA, esquemas[esquema])


def test_las_reglas_atomicas():
    assert EsquemaDefinido().es_satisfecha_por(_contexto("valido"))
    assert EsquemaDefinido().es_satisfecha_por(_contexto("sin_validar"))
    assert not EsquemaDefinido().es_satisfecha_por(_contexto("ninguno"))
    assert EsquemaValidado().es_satisfecha_por(_contexto("valido"))
    assert not EsquemaValidado().es_satisfecha_por(_contexto("sin_validar"))
    assert not EsquemaValidado().es_satisfecha_por(_contexto("ninguno"))
    assert RequiereRefuerzo().es_satisfecha_por(_contexto("valido"))
    assert not RequiereRefuerzo().es_satisfecha_por(_contexto("sin_validar"))
    assert not RequiereRefuerzo().es_satisfecha_por(_contexto("ninguno"))


def test_seguimiento_calculable_exige_esquema_definido_y_validado():
    assert seguimiento_calculable().evaluar(_contexto("valido")).cumple
    sin_validar = seguimiento_calculable().evaluar(_contexto("sin_validar"))
    assert not sin_validar.cumple and sin_validar.motivos == ("ESQUEMA_NO_VALIDADO",)
    ninguno = seguimiento_calculable().evaluar(_contexto("ninguno"))
    assert not ninguno.cumple and ninguno.motivos == ("ESQUEMA_NO_DEFINIDO",)  # sin repetir


def test_requerir_refuerzo_no_condiciona_el_seguimiento():
    """Una vacuna sin refuerzo, con esquema validado, también se puede calcular."""
    sin_refuerzo = VacunacionEnContexto(ULTIMA, EsquemaDeVacunacion(
        vacuna="Rabia", frecuencia_dias=365, requiere_refuerzo=False, validado=True))
    assert seguimiento_calculable().es_satisfecha_por(sin_refuerzo)
    assert not RequiereRefuerzo().es_satisfecha_por(sin_refuerzo)


def test_seguimiento_pendiente_es_el_not_del_calculable():
    assert seguimiento_pendiente().es_satisfecha_por(_contexto("sin_validar"))
    assert seguimiento_pendiente().es_satisfecha_por(_contexto("ninguno"))
    calculable = seguimiento_pendiente().evaluar(_contexto("valido"))
    assert not calculable.cumple
    assert calculable.motivos == ("SEGUIMIENTO_PENDIENTE_DE_ESQUEMA_VALIDADO",)


def test_descripciones_legibles():
    assert seguimiento_calculable().descripcion() == "EsquemaDefinido AND EsquemaValidado"
    assert seguimiento_pendiente().descripcion() == "NOT (EsquemaDefinido AND EsquemaValidado)"


def test_el_esquema_debe_ser_de_la_misma_vacuna():
    otro = EsquemaDeVacunacion(vacuna="Parvovirus", frecuencia_dias=30,
                               requiere_refuerzo=True, validado=True)
    with pytest.raises(InvarianteViolada) as error:
        VacunacionEnContexto(ULTIMA, otro)
    assert error.value.codigo == "ESQUEMA_INCORRECTO"
