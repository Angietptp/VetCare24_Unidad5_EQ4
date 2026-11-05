"""Genera la evidencia de la API: los 120 casos y las 20 transiciones del profesor por HTTP.

Uso:  python -m tests.evidencia_api [carpeta_de_salida]
Usa PostgreSQL si DATABASE_URL apunta a uno (Docker Compose); si no, un SQLite temporal.
La base de pruebas se vacía y se vuelve a cargar con el paquete antes de empezar.
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests import oraculo
from tests.api_paquete import (
    comparar_casos,
    comparar_confirmaciones,
    comparar_transiciones,
    ejecutar_casos,
    ejecutar_confirmaciones,
    ejecutar_transiciones,
    status_esperado,
)
from vetcare24.api.main import create_app
from vetcare24.infrastructure.adaptador_paquete import construir_dominio
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete
from vetcare24.infrastructure.esquema import crear_esquema, eliminar_esquema
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql
from vetcare24.infrastructure.sembrado import sembrar


def _url_de_evidencia() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgresql://", "postgresql+psycopg://")):
        return url
    return f"sqlite:///{Path(tempfile.mkdtemp()) / 'evidencia.db'}"


def _api_sembrada() -> tuple[TestClient, object]:
    ajustes = load_settings()
    url = _url_de_evidencia()
    conexion = conectar(url)
    eliminar_esquema(conexion)
    crear_esquema(conexion)
    conexion.cerrar()
    paquete = cargar_paquete(ajustes.data_dir)
    with UnidadDeTrabajoSql(url) as uow:
        sembrar(uow, construir_dominio(paquete))
    return TestClient(create_app(url, preparar_esquema=False)), paquete


def escribir_casos(resultados, paquete, salida: Path) -> Path:
    ruta = salida / "api_casos.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["caso_id", "operacion_id", "tipo_prueba", "peticion", "http_status",
                           "cumple_api", "cumple_oraculo", "coincide"])
        for r, caso in zip(resultados, paquete.casos, strict=True):
            esperado = oraculo.resolver_caso(paquete, caso).cumple
            escritor.writerow([r.caso_id, r.operacion_id, r.tipo_prueba, r.peticion, r.status,
                               r.cumple, esperado, r.status == 200 and r.cumple == esperado])
    return ruta


def escribir_transiciones(resultados, paquete, salida: Path) -> Path:
    ruta = salida / "api_transiciones.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["caso_id", "operacion_id", "accion", "pasos_http", "http_status",
                           "http_esperado", "estado_final_api", "estado_final_oraculo",
                           "codigo_api", "motivos_api", "eventos_api", "coincide"])
        desacuerdos = set(comparar_transiciones(resultados, paquete))
        for r, caso in zip(resultados, paquete.transiciones, strict=True):
            esperado = oraculo.resolver_transicion(paquete, caso)
            coincide = not any(d.startswith(f"{r.caso_id}:") for d in desacuerdos)
            escritor.writerow([
                r.caso_id, r.operacion_id, r.accion, " ; ".join(r.pasos), r.status_final,
                status_esperado(esperado.excepcion, esperado.motivos), r.estado_final,
                esperado.estado_final, r.codigo or "", " | ".join(r.motivos),
                "|".join(r.eventos), coincide])
    return ruta


def main(argv: list[str]) -> None:
    salida = Path(argv[0]) if argv else Path("docs/evidencia")
    salida.mkdir(parents=True, exist_ok=True)

    cliente, paquete = _api_sembrada()
    casos = ejecutar_casos(cliente, paquete)
    transiciones = ejecutar_transiciones(cliente, paquete)
    ruta_casos = escribir_casos(casos, paquete, salida)
    ruta_transiciones = escribir_transiciones(transiciones, paquete, salida)
    fallos_casos = comparar_casos(casos, paquete)
    fallos_transiciones = comparar_transiciones(transiciones, paquete)

    cliente, paquete = _api_sembrada()  # base limpia para la confirmación en orden
    confirmaciones = ejecutar_confirmaciones(cliente, paquete)
    fallos_confirmaciones = comparar_confirmaciones(confirmaciones, paquete)

    print(f"casos por la API:         {len(casos) - len(fallos_casos)}/{len(casos)} coinciden")
    print(f"transiciones por la API:  {len(transiciones) - len(fallos_transiciones)}/"
          f"{len(transiciones)} coinciden")
    veredicto = "coincide" if not fallos_confirmaciones else "NO coincide"
    print(f"confirmación de las 60:   {veredicto}")
    for desacuerdo in fallos_casos + fallos_transiciones + fallos_confirmaciones:
        print("  ", desacuerdo)
    print("Evidencia:", ruta_casos, ruta_transiciones)


if __name__ == "__main__":
    main(sys.argv[1:])
