"""Oráculo independiente (D-15).

Calcula los resultados esperados de los 120 casos y las 20 transiciones SIN usar el dominio:
solo lee los CSV (con el importador) y evalúa el texto de cada regla. Si el dominio que se
programe después coincide con este oráculo, son dos implementaciones independientes de las
mismas reglas. Las reglas del paquete son extensión del paquete, no requerimientos del BRD.

Generar la evidencia:  python -m tests.oraculo [carpeta_de_salida]
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import (
    CasoPrueba,
    Operacion,
    PaqueteDatos,
    TransicionPrueba,
    cargar_paquete,
)

CENTAVO = Decimal("0.01")


class ReglaDesconocida(ValueError):
    """La regla menciona una condición que el oráculo no sabe evaluar (no se inventa)."""


def total_mxn(paquete: PaqueteDatos, operacion_id: str) -> Decimal:
    """Total = suma(precio_mxn x cantidad), con Decimal y 2 decimales (D-02)."""
    suma = sum(
        (paquete.recursos[ln.recurso_id].precio_mxn * ln.cantidad
         for ln in paquete.lineas_de(operacion_id)),
        Decimal("0"),
    )
    return suma.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos).strip().lower()


def _atomo(atomo: str, paquete: PaqueteDatos, op: Operacion) -> bool:
    actor = paquete.actores[op.actor_id]
    if atomo == "cliente activo":
        return actor.activo
    if atomo == "detalle no vacio":
        return len(paquete.lineas_de(op.operacion_id)) > 0
    if atomo == "autorizacion":
        return op.autorizado
    if atomo == "vip":  # el paquete lo llama VIP; en los datos es es_preferente
        return actor.es_preferente
    if atomo == "promocion":
        return op.promocion_activa
    umbral = re.fullmatch(r"total >= ?(\d+(?:\.\d+)?)", atomo)
    if umbral:
        return total_mxn(paquete, op.operacion_id) >= Decimal(umbral.group(1))
    raise ReglaDesconocida(atomo)


def evaluar_regla(
    texto: str, paquete: PaqueteDatos, op: Operacion
) -> tuple[bool, tuple[str, ...]]:
    """Evalúa 'a AND b OR NOT c' (NOT > AND > OR). Devuelve (cumple, condiciones fallidas)."""
    expresion = re.sub(r"^validar ", "", _normalizar(texto))
    fallidas: list[str] = []
    cumple = False
    for termino in expresion.split(" or "):
        todo = True
        for factor in termino.split(" and "):
            negado = factor.startswith("not ")
            nombre = factor[4:] if negado else factor
            valor = _atomo(nombre.strip(), paquete, op)
            valor = (not valor) if negado else valor
            if not valor:
                fallidas.append(factor.strip())
            todo = todo and valor
        cumple = cumple or todo
    return cumple, tuple(fallidas)


@dataclass(frozen=True)
class ResultadoCaso:
    caso_id: str
    operacion_id: str
    tipo_prueba: str
    regla: str
    cumple: bool
    total_mxn: Decimal
    condiciones_fallidas: tuple[str, ...]


def resolver_caso(paquete: PaqueteDatos, caso: CasoPrueba) -> ResultadoCaso:
    op = paquete.operaciones[caso.operacion_id]
    cumple, fallidas = evaluar_regla(caso.regla, paquete, op)
    return ResultadoCaso(
        caso.caso_id, caso.operacion_id, caso.tipo_prueba, caso.regla,
        cumple, total_mxn(paquete, caso.operacion_id), fallidas,
    )


# --- Máquina de estados de referencia (D-07, D-08, D-11, D-12) --------------------------

TRANSICIONES = {
    ("SOLICITADA", "confirmar"): "CONFIRMADA",
    ("CONFIRMADA", "realizar"): "REALIZADA",
    ("SOLICITADA", "cancelar"): "CANCELADA",
    ("CONFIRMADA", "cancelar"): "CANCELADA",
}
EVENTOS = {"confirmar": "CitaAgendada", "realizar": "CitaRealizada", "cancelar": "CitaCancelada"}
ACCIONES = {
    "aprobar": ("confirmar",),
    "completar": ("confirmar", "realizar"),
    "cancelar": ("cancelar",),
    "repetir_aprobacion": ("confirmar", "confirmar"),
    "saltar_estado": ("realizar",),
}


def bloqueos_para_confirmar(
    paquete: PaqueteDatos, op: Operacion, disponible: dict[str, int]
) -> tuple[str, ...]:
    """Guardas de 'confirmar': elegibilidad (regla 1) + líneas válidas + capacidad."""
    motivos: list[str] = []
    if not paquete.actores[op.actor_id].activo:
        motivos.append("ACTOR_INACTIVO")
    lineas = paquete.lineas_de(op.operacion_id)
    if not lineas:
        motivos.append("DETALLE_VACIO")
    if not op.autorizado:
        motivos.append("NO_AUTORIZADA")
    pedido: dict[str, int] = {}
    for ln in lineas:
        if not paquete.recursos[ln.recurso_id].habilitado:
            motivos.append(f"SERVICIO_DESHABILITADO:{ln.recurso_id}")
        if ln.cantidad < 1:
            motivos.append(f"CANTIDAD_INVALIDA:{ln.recurso_id}")
        pedido[ln.recurso_id] = pedido.get(ln.recurso_id, 0) + ln.cantidad
    for recurso_id, cantidad in pedido.items():
        if cantidad > disponible[recurso_id]:
            motivos.append(f"CAPACIDAD_INSUFICIENTE:{recurso_id}")
    return tuple(dict.fromkeys(motivos))


@dataclass(frozen=True)
class ResultadoTransicion:
    caso_id: str
    operacion_id: str
    accion: str
    estado_inicial: str
    estado_final: str
    eventos: tuple[str, ...]
    excepcion: str | None
    motivos: tuple[str, ...]


def resolver_transicion(paquete: PaqueteDatos, caso: TransicionPrueba) -> ResultadoTransicion:
    """Cada caso es independiente: parte de la capacidad inicial del catálogo."""
    if caso.accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {caso.accion}")
    op = paquete.operaciones[caso.operacion_id]
    disponible = {r.recurso_id: r.capacidad for r in paquete.recursos.values()}
    estado = caso.estado_inicial
    eventos: list[str] = []

    def terminar(excepcion: str | None, motivos: tuple[str, ...]) -> ResultadoTransicion:
        return ResultadoTransicion(
            caso.caso_id, caso.operacion_id, caso.accion, caso.estado_inicial,
            estado, tuple(eventos), excepcion, motivos,
        )

    for paso in ACCIONES[caso.accion]:
        destino = TRANSICIONES.get((estado, paso))
        if destino is None:  # D-12: primero la validez de la transición
            return terminar("TransicionInvalida", (f"{paso} desde {estado}",))
        if paso == "confirmar":
            motivos = bloqueos_para_confirmar(paquete, op, disponible)
            if motivos:
                return terminar("PrecondicionNoCumplida", motivos)
            for ln in paquete.lineas_de(op.operacion_id):
                disponible[ln.recurso_id] -= ln.cantidad
        estado = destino
        eventos.append(EVENTOS[paso])
    return terminar(None, ())


def confirmar_en_secuencia(paquete: PaqueteDatos) -> dict[str, tuple[str, ...]]:
    """Intenta confirmar las 60 operaciones EN ORDEN, compartiendo la capacidad (D-08).

    Devuelve {operacion_id: motivos de bloqueo}; tupla vacía = quedó CONFIRMADA y consumió
    capacidad. Es la prueba de que la capacidad es acumulada y de que el orden importa.
    """
    disponible = {r.recurso_id: r.capacidad for r in paquete.recursos.values()}
    resultado: dict[str, tuple[str, ...]] = {}
    for operacion_id, op in paquete.operaciones.items():
        motivos = bloqueos_para_confirmar(paquete, op, disponible)
        if not motivos:
            for ln in paquete.lineas_de(operacion_id):
                disponible[ln.recurso_id] -= ln.cantidad
        resultado[operacion_id] = motivos
    return resultado


# --- Generación de evidencia -------------------------------------------------------------

def generar_evidencia(paquete: PaqueteDatos, salida: Path) -> tuple[Path, Path]:
    salida.mkdir(parents=True, exist_ok=True)
    ruta_casos = salida / "oraculo_casos.csv"
    with ruta_casos.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["caso_id", "operacion_id", "tipo_prueba", "regla_a_verificar",
                    "resultado_esperado", "total_mxn", "condiciones_fallidas"])
        for caso in paquete.casos:
            r = resolver_caso(paquete, caso)
            w.writerow([r.caso_id, r.operacion_id, r.tipo_prueba, r.regla,
                        "CUMPLE" if r.cumple else "NO_CUMPLE", f"{r.total_mxn:.2f}",
                        " | ".join(r.condiciones_fallidas)])
    ruta_trans = salida / "oraculo_transiciones.csv"
    with ruta_trans.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["caso_id", "operacion_id", "accion", "estado_inicial", "estado_final",
                    "eventos", "excepcion", "motivos"])
        for caso in paquete.transiciones:
            r = resolver_transicion(paquete, caso)
            w.writerow([r.caso_id, r.operacion_id, r.accion, r.estado_inicial, r.estado_final,
                        "|".join(r.eventos), r.excepcion or "", " | ".join(r.motivos)])
    return ruta_casos, ruta_trans


def generar_evidencia_secuencia(paquete: PaqueteDatos, salida: Path) -> Path:
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / "oraculo_secuencia.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["operacion_id", "resultado", "motivos"])
        for operacion_id, motivos in confirmar_en_secuencia(paquete).items():
            estado = "RECHAZADA" if motivos else "CONFIRMADA"
            w.writerow([operacion_id, estado, " | ".join(motivos)])
    return ruta


def main(argv: list[str]) -> None:
    paquete = cargar_paquete(load_settings().data_dir)
    salida = Path(argv[0]) if argv else Path("docs/evidencia")
    ruta_casos, ruta_trans = generar_evidencia(paquete, salida)
    casos = [resolver_caso(paquete, c) for c in paquete.casos]
    for tipo in sorted({c.tipo_prueba for c in casos}):
        grupo = [c for c in casos if c.tipo_prueba == tipo]
        print(f"{tipo}: {sum(c.cumple for c in grupo)} CUMPLE / "
              f"{sum(not c.cumple for c in grupo)} NO_CUMPLE de {len(grupo)}")
    trans = [resolver_transicion(paquete, t) for t in paquete.transiciones]
    por_excepcion: dict[str, int] = {}
    for t in trans:
        clave = t.excepcion or "OK"
        por_excepcion[clave] = por_excepcion.get(clave, 0) + 1
    print("transiciones:", por_excepcion)
    secuencia = confirmar_en_secuencia(paquete)
    print(f"confirmación en secuencia: {sum(not m for m in secuencia.values())} CONFIRMADA / "
          f"{sum(bool(m) for m in secuencia.values())} RECHAZADA de {len(secuencia)}")
    ruta_secuencia = generar_evidencia_secuencia(paquete, salida)
    print("Evidencia:", ruta_casos, ruta_trans, ruta_secuencia)


if __name__ == "__main__":
    main(sys.argv[1:])
