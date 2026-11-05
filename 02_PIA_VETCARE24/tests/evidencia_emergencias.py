"""Genera la evidencia de CU-05: los 20 escenarios de emergencias por HTTP.

Uso:  python -m tests.evidencia_emergencias [carpeta_de_salida]
Usa PostgreSQL si DATABASE_URL apunta a uno (Docker Compose); si no, un SQLite temporal.
La base de pruebas se vacía antes de empezar. Escribe `api_emergencias.csv`.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from tests.api_emergencias import ejecutar, sembrar_mascotas
from tests.bd import sembrar_basico
from tests.evidencia_api import _url_de_evidencia
from vetcare24.api.main import create_app
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.esquema import crear_esquema, eliminar_esquema

COLUMNAS = ["escenario", "descripcion", "rol", "metodo", "ruta", "http_esperado",
            "http_obtenido", "resultado_esperado", "resultado_obtenido", "regla", "coincide"]


def main(argv: list[str]) -> int:
    salida = Path(argv[0]) if argv else Path("docs/evidencia")
    salida.mkdir(parents=True, exist_ok=True)
    url = _url_de_evidencia()
    conexion = conectar(url)
    eliminar_esquema(conexion)
    crear_esquema(conexion)
    conexion.cerrar()
    sembrar_basico(url)
    sembrar_mascotas(url)
    resultados = ejecutar(TestClient(create_app(url, preparar_esquema=False)))

    ruta = salida / "api_emergencias.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        for r in resultados:
            e = r.escenario
            escritor.writerow([e.id, e.descripcion, e.rol or "(sin rol)", e.metodo, e.ruta,
                               e.http_esperado, r.http_obtenido, e.resultado_esperado,
                               r.resultado_obtenido, e.regla, r.coincide])
    bien = sum(r.coincide for r in resultados)
    print(f"emergencias por la API: {bien}/{len(resultados)} escenarios coinciden")
    for r in resultados:
        if not r.coincide:
            print(f"   {r.escenario.id}: esperado {r.escenario.http_esperado} "
                  f"{r.escenario.resultado_esperado}, obtenido {r.http_obtenido} "
                  f"{r.resultado_obtenido}")
    print("Evidencia:", ruta)
    return 0 if bien == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
