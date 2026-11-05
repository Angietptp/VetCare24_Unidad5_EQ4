"""Unidad 5 (E9): casos de la matriz `docs/u5/matriz_pia_u5.csv`, ejecutados con pytest.

Cada fila CP-01 a CP-09 es una prueba parametrizada que se lee del CSV con `csv.DictReader`.
CP-10 y CP-11 son pruebas de integración que ya existen (columna `prueba` de la matriz).
"""

import csv
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.emergencia import Emergencia, EstadoEmergencia
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.reglas_cita import (
    UMBRAL_BENEFICIO,
    CapacidadSuficiente,
    CitaEnContexto,
    TotalMinimo,
    disponibilidad_inicial,
)

MATRIZ = Path(__file__).resolve().parent.parent / "docs" / "u5" / "matriz_pia_u5.csv"
HORA = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _filas():
    with MATRIZ.open(encoding="utf-8", newline="") as archivo:
        filas = csv.DictReader(archivo)
        return [f for f in filas if f["prueba"].endswith("test_caso_de_la_matriz")]


def _parametros(entrada: str) -> dict[str, str]:
    return dict(par.split("=", 1) for par in entrada.split(";"))


def _contexto(cantidad: int, capacidad: int, precio: str) -> CitaEnContexto:
    servicio = ServicioVeterinario("S1", "Consulta", Money.mxn(precio), capacidad, True)
    catalogo = {"S1": servicio}
    cita = Cita(
        cita_id="C1", propietario_id="P1", mascota_id="M1",
        lineas=[ServicioSolicitado("S1", cantidad)], fecha_solicitud=date(2026, 10, 2),
        estado=EstadoCita.SOLICITADA, autorizada=True,
    )
    return CitaEnContexto(cita, Propietario("P1", "Ana", activo=True, preferente=True),
                          catalogo, disponibilidad_inicial(catalogo))


def _resumen(evaluacion) -> str:
    return "cumple" if evaluacion.cumple else "|".join(evaluacion.motivos)


def _ejecutar(regla: str, p: dict[str, str]) -> str:
    if regla.startswith("Capacidad"):
        contexto = _contexto(int(p["cantidad"]), int(p["capacidad"]), "500")
        return _resumen(CapacidadSuficiente().evaluar(contexto))
    if regla.startswith("Total mínimo"):
        contexto = _contexto(int(p["cantidad"]), 99, p["precio"])
        return _resumen(TotalMinimo(UMBRAL_BENEFICIO).evaluar(contexto))
    if regla.startswith("Registro de emergencia"):
        try:
            emergencia = Emergencia(emergencia_id="E1", motivo=p["motivo"],
                                    mascota_id=p["mascota"] or None, identificada_en=HORA)
        except InvarianteViolada as error:
            return error.codigo
        assert emergencia.estado is EstadoEmergencia.IDENTIFICADA
        return emergencia.estado.value
    raise AssertionError(f"regla sin ejecutor: {regla}")


def test_la_matriz_tiene_al_menos_nueve_casos_de_cada_tipo():
    filas = _filas()
    assert len(filas) == 9
    for tipo in ("Éxito", "Error", "Límite"):
        assert sum(f["tipo"] == tipo for f in filas) == 3


@pytest.mark.parametrize("fila", _filas(), ids=lambda f: f["id"])
def test_caso_de_la_matriz(fila):
    obtenido = _ejecutar(fila["regla"], _parametros(fila["entrada"]))
    assert obtenido == fila["resultado_esperado"], f"{fila['id']} ({fila['tipo']})"
