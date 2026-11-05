"""Ejecuta los datos del profesor A TRAVÉS DE LA API y los compara con el oráculo.

Cubre: los 120 casos de prueba (reglas de elegibilidad), las 20 pruebas de transición y la
confirmación de las 60 citas en orden. Solo habla HTTP: no importa el dominio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tests import oraculo
from vetcare24.infrastructure.csv_loader import PaqueteDatos

REGLA_DE_CADA_TIPO = {"validar_operacion": "procesamiento", "evaluar_beneficio": "beneficio"}

# acción del paquete -> pasos HTTP (D-11): (acción de la cita, rol que la ejecuta)
PASOS_DE_CADA_ACCION: dict[str, tuple[tuple[str, str], ...]] = {
    "aprobar": (("confirmar", "recepcion"),),
    "completar": (("confirmar", "recepcion"), ("realizar", "veterinario")),
    "cancelar": (("cancelar", "recepcion"),),
    "repetir_aprobacion": (("confirmar", "recepcion"), ("confirmar", "recepcion")),
    "saltar_estado": (("realizar", "veterinario"),),
}


def status_esperado(excepcion: str | None, motivos: tuple[str, ...]) -> int:
    """El contrato HTTP del equipo aplicado a lo que dice el oráculo."""
    if excepcion is None:
        return 200
    if excepcion == "TransicionInvalida":
        return 409
    # K-03 / H-07: si entre los motivos está la capacidad, es un conflicto (409)
    hay_capacidad = any(m.startswith("CAPACIDAD_INSUFICIENTE") for m in motivos)
    return 409 if hay_capacidad else 422


def _encabezado(rol: str) -> dict[str, str]:
    return {"X-Rol": rol}


# --- los 120 casos ----------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoCasoApi:
    caso_id: str
    operacion_id: str
    tipo_prueba: str
    peticion: str
    status: int
    cumple: bool | None


def ejecutar_casos(cliente: Any, paquete: PaqueteDatos) -> list[ResultadoCasoApi]:
    resultados = []
    for caso in paquete.casos:
        ruta = f"/citas/{caso.operacion_id}/evaluaciones/{REGLA_DE_CADA_TIPO[caso.tipo_prueba]}"
        respuesta = cliente.get(ruta, headers=_encabezado("recepcion"))
        cumple = respuesta.json()["cumple"] if respuesta.status_code == 200 else None
        resultados.append(ResultadoCasoApi(
            caso.caso_id, caso.operacion_id, caso.tipo_prueba, f"GET {ruta}",
            respuesta.status_code, cumple))
    return resultados


def comparar_casos(resultados: list[ResultadoCasoApi], paquete: PaqueteDatos) -> list[str]:
    """Devuelve los desacuerdos con el oráculo (lista vacía = todo coincide)."""
    desacuerdos = []
    for resultado, caso in zip(resultados, paquete.casos, strict=True):
        esperado = oraculo.resolver_caso(paquete, caso).cumple
        if resultado.status != 200 or resultado.cumple != esperado:
            desacuerdos.append(
                f"{caso.caso_id}: API {resultado.status}/{resultado.cumple}, "
                f"esperado 200/{esperado}")
    return desacuerdos


# --- las 20 transiciones ----------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoTransicionApi:
    caso_id: str
    operacion_id: str
    accion: str
    pasos: tuple[str, ...]
    status_final: int
    estado_final: str
    codigo: str | None
    motivos: tuple[str, ...]
    eventos: tuple[str, ...]


def ejecutar_transiciones(cliente: Any, paquete: PaqueteDatos) -> list[ResultadoTransicionApi]:
    resultados = []
    for caso in paquete.transiciones:
        pasos: list[str] = []
        status, codigo, motivos = 200, None, ()
        for accion, rol in PASOS_DE_CADA_ACCION[caso.accion]:
            ruta = f"/citas/{caso.operacion_id}/{accion}"
            respuesta = cliente.post(ruta, headers=_encabezado(rol))
            pasos.append(f"POST {ruta} -> {respuesta.status_code}")
            if respuesta.status_code != 200:
                error = respuesta.json()["error"]
                status, codigo, motivos = (
                    respuesta.status_code, error["codigo"], tuple(error["motivos"]))
                break
        estado = cliente.get(f"/citas/{caso.operacion_id}", headers=_encabezado("recepcion"))
        eventos = cliente.get("/eventos", headers=_encabezado("responsable")).json()
        nombres = tuple(e["evento"] for e in eventos if e["cita_id"] == caso.operacion_id)
        resultados.append(ResultadoTransicionApi(
            caso.caso_id, caso.operacion_id, caso.accion, tuple(pasos), status,
            estado.json()["estado"], codigo, motivos, nombres))
    return resultados


def comparar_transiciones(
    resultados: list[ResultadoTransicionApi], paquete: PaqueteDatos
) -> list[str]:
    desacuerdos = []
    for resultado, caso in zip(resultados, paquete.transiciones, strict=True):
        esperado = oraculo.resolver_transicion(paquete, caso)
        problemas = []
        if resultado.estado_final != esperado.estado_final:
            problemas.append(f"estado {resultado.estado_final} != {esperado.estado_final}")
        if resultado.status_final != status_esperado(esperado.excepcion, esperado.motivos):
            problemas.append(f"status {resultado.status_final}")
        if resultado.motivos != esperado.motivos:
            problemas.append(f"motivos {resultado.motivos} != {esperado.motivos}")
        if resultado.eventos != esperado.eventos:
            problemas.append(f"eventos {resultado.eventos} != {esperado.eventos}")
        if problemas:
            desacuerdos.append(f"{caso.caso_id}: " + "; ".join(problemas))
    return desacuerdos


# --- confirmar las 60 citas en orden ----------------------------------------------------------

Confirmaciones = dict[str, tuple[int, tuple[str, ...]]]


def ejecutar_confirmaciones(cliente: Any, paquete: PaqueteDatos) -> Confirmaciones:
    resultado = {}
    for cita_id in paquete.operaciones:
        respuesta = cliente.post(f"/citas/{cita_id}/confirmar", headers=_encabezado("recepcion"))
        motivos = (
            tuple(respuesta.json()["error"]["motivos"]) if respuesta.status_code != 200 else ())
        resultado[cita_id] = (respuesta.status_code, motivos)
    return resultado


def comparar_confirmaciones(obtenido: Confirmaciones, paquete: PaqueteDatos) -> list[str]:
    desacuerdos = []
    for cita_id, motivos in oraculo.confirmar_en_secuencia(paquete).items():
        excepcion = "PrecondicionNoCumplida" if motivos else None
        esperado = (status_esperado(excepcion, motivos), motivos)
        if obtenido[cita_id] != esperado:
            desacuerdos.append(f"{cita_id}: API {obtenido[cita_id]}, esperado {esperado}")
    return desacuerdos
