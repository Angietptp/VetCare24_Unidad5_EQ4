"""Importador de los CSV del paquete de pruebas (Etapa 2).

Lee los archivos tal cual vienen (D-09): conserva también los registros que las reglas de
negocio rechazarán (tutor inactivo, operación sin detalle, servicio deshabilitado).
Solo se rechaza lo que es un archivo dañado: columnas distintas, valores que no se pueden
interpretar, ids repetidos o claves foráneas rotas.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ErrorDeDatos(ValueError):
    """El paquete de datos está dañado o incompleto."""


@dataclass(frozen=True)
class Actor:
    actor_id: str
    nombre: str
    es_preferente: bool
    activo: bool
    ciudad: str


@dataclass(frozen=True)
class Recurso:
    recurso_id: str
    descripcion: str
    precio_mxn: Decimal
    capacidad: int
    habilitado: bool


@dataclass(frozen=True)
class Operacion:
    operacion_id: str
    actor_id: str
    estado_inicial: str
    fecha_solicitud: date
    promocion_activa: bool
    autorizado: bool
    referencia: str


@dataclass(frozen=True)
class Linea:
    operacion_id: str
    recurso_id: str
    cantidad: int


@dataclass(frozen=True)
class CasoPrueba:
    caso_id: str
    operacion_id: str
    tipo_prueba: str
    regla: str
    instrucciones: str


@dataclass(frozen=True)
class TransicionPrueba:
    caso_id: str
    operacion_id: str
    accion: str
    estado_inicial: str
    instrucciones: str


@dataclass(frozen=True)
class PaqueteDatos:
    actores: dict[str, Actor]
    recursos: dict[str, Recurso]
    operaciones: dict[str, Operacion]
    lineas: dict[str, tuple[Linea, ...]]
    casos: tuple[CasoPrueba, ...]
    transiciones: tuple[TransicionPrueba, ...]

    def lineas_de(self, operacion_id: str) -> tuple[Linea, ...]:
        return self.lineas.get(operacion_id, ())

    @property
    def total_lineas(self) -> int:
        return sum(len(grupo) for grupo in self.lineas.values())


_COLUMNAS = {
    "actores": ["actor_id", "nombre", "es_preferente", "activo", "ciudad"],
    "catalogo": ["recurso_id", "descripcion", "precio_mxn", "capacidad_o_stock", "habilitado"],
    "operaciones": [
        "operacion_id", "actor_id", "estado_inicial", "fecha_solicitud",
        "promocion_activa", "autorizado", "referencia",
    ],
    "detalle_operaciones": ["operacion_id", "recurso_id", "cantidad"],
    "casos_prueba": [
        "caso_id", "operacion_id", "tipo_prueba", "regla_a_verificar",
        "resultado_alumno", "instrucciones",
    ],
    "transiciones_prueba": [
        "caso_id", "operacion_id", "accion_sugerida", "estado_inicial",
        "resultado_alumno", "instrucciones",
    ],
}


def _leer(directorio: Path, nombre: str) -> list[tuple[str, dict[str, str]]]:
    """Devuelve [(ubicación, fila)] validando que el encabezado sea el esperado."""
    ruta = directorio / f"{nombre}.csv"
    if not ruta.is_file():
        raise ErrorDeDatos(f"Falta el archivo {ruta.name} en {directorio}")
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != _COLUMNAS[nombre]:
            raise ErrorDeDatos(
                f"{ruta.name}: columnas {lector.fieldnames}, se esperaba {_COLUMNAS[nombre]}"
            )
        return [(f"{ruta.name} línea {n}", fila) for n, fila in enumerate(lector, start=2)]


def _booleano(valor: str, donde: str) -> bool:
    if valor not in ("0", "1"):
        raise ErrorDeDatos(f"{donde}: se esperaba 0 o 1 y llegó {valor!r}")
    return valor == "1"


def _entero(valor: str, donde: str) -> int:
    try:
        return int(valor)
    except ValueError as error:
        raise ErrorDeDatos(f"{donde}: entero inválido {valor!r}") from error


def _decimal(valor: str, donde: str) -> Decimal:
    try:
        numero = Decimal(valor)
    except InvalidOperation as error:
        raise ErrorDeDatos(f"{donde}: importe inválido {valor!r}") from error
    if not numero.is_finite():
        raise ErrorDeDatos(f"{donde}: importe no finito {valor!r}")
    return numero


def _fecha(valor: str, donde: str) -> date:
    try:
        return date.fromisoformat(valor)
    except ValueError as error:
        raise ErrorDeDatos(f"{donde}: fecha ISO inválida {valor!r}") from error


def _sin_repetidos(ids: list[str], que: str) -> None:
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ErrorDeDatos(f"{que}: ids repetidos {repetidos}")


def cargar_paquete(directorio: Path) -> PaqueteDatos:
    """Carga y valida los 6 CSV del alumno."""
    actores = [
        Actor(f["actor_id"], f["nombre"], _booleano(f["es_preferente"], d),
              _booleano(f["activo"], d), f["ciudad"])
        for d, f in _leer(directorio, "actores")
    ]
    recursos = [
        Recurso(f["recurso_id"], f["descripcion"], _decimal(f["precio_mxn"], d),
                _entero(f["capacidad_o_stock"], d), _booleano(f["habilitado"], d))
        for d, f in _leer(directorio, "catalogo")
    ]
    operaciones = [
        Operacion(f["operacion_id"], f["actor_id"], f["estado_inicial"],
                  _fecha(f["fecha_solicitud"], d), _booleano(f["promocion_activa"], d),
                  _booleano(f["autorizado"], d), f["referencia"])
        for d, f in _leer(directorio, "operaciones")
    ]
    lineas = [
        (d, Linea(f["operacion_id"], f["recurso_id"], _entero(f["cantidad"], d)))
        for d, f in _leer(directorio, "detalle_operaciones")
    ]
    casos = [
        CasoPrueba(f["caso_id"], f["operacion_id"], f["tipo_prueba"],
                   f["regla_a_verificar"], f["instrucciones"])
        for _, f in _leer(directorio, "casos_prueba")
    ]
    transiciones = [
        TransicionPrueba(f["caso_id"], f["operacion_id"], f["accion_sugerida"],
                         f["estado_inicial"], f["instrucciones"])
        for _, f in _leer(directorio, "transiciones_prueba")
    ]

    _sin_repetidos([a.actor_id for a in actores], "actores")
    _sin_repetidos([r.recurso_id for r in recursos], "catalogo")
    _sin_repetidos([o.operacion_id for o in operaciones], "operaciones")
    _sin_repetidos([c.caso_id for c in casos] + [t.caso_id for t in transiciones], "casos")

    ids_actor = {a.actor_id for a in actores}
    ids_recurso = {r.recurso_id for r in recursos}
    por_id_operacion = {o.operacion_id: o for o in operaciones}

    for o in operaciones:
        if o.actor_id not in ids_actor:
            raise ErrorDeDatos(f"operaciones: {o.operacion_id} usa actor inexistente {o.actor_id}")
    agrupadas: dict[str, list[Linea]] = {}
    for donde, linea in lineas:
        if linea.operacion_id not in por_id_operacion:
            raise ErrorDeDatos(f"{donde}: operación inexistente {linea.operacion_id}")
        if linea.recurso_id not in ids_recurso:
            raise ErrorDeDatos(f"{donde}: recurso inexistente {linea.recurso_id}")
        agrupadas.setdefault(linea.operacion_id, []).append(linea)
    for c in casos:
        if c.operacion_id not in por_id_operacion:
            raise ErrorDeDatos(f"casos_prueba: {c.caso_id} usa operación inexistente")
    for t in transiciones:
        operacion = por_id_operacion.get(t.operacion_id)
        if operacion is None:
            raise ErrorDeDatos(f"transiciones_prueba: {t.caso_id} usa operación inexistente")
        if operacion.estado_inicial != t.estado_inicial:
            raise ErrorDeDatos(
                f"transiciones_prueba: {t.caso_id} parte de {t.estado_inicial} "
                f"pero {t.operacion_id} está en {operacion.estado_inicial}"
            )

    return PaqueteDatos(
        actores={a.actor_id: a for a in actores},
        recursos={r.recurso_id: r for r in recursos},
        operaciones=por_id_operacion,
        lineas={k: tuple(v) for k, v in agrupadas.items()},
        casos=tuple(casos),
        transiciones=tuple(transiciones),
    )
