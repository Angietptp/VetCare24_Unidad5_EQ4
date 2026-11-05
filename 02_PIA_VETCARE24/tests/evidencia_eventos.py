"""Genera la evidencia de Domain Events con el DOMINIO (no con el oráculo).

Confirma las 60 citas en orden, publica los eventos y los guarda en un CSV.
Uso:  python -m tests.evidencia_eventos [carpeta_de_salida]
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from vetcare24.application.despachador import Despachador, RegistroDeEventos
from vetcare24.domain.ciclo_de_vida import CicloDeVidaDeCita
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import PrecondicionNoCumplida
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.infrastructure.adaptador_paquete import construir_dominio
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete


def confirmar_todas_publicando() -> RegistroDeEventos:
    datos = construir_dominio(cargar_paquete(load_settings().data_dir))
    registro, despachador = RegistroDeEventos(), Despachador()
    despachador.suscribir(EventoDeDominio, registro)
    ciclo, disponibilidad = CicloDeVidaDeCita(), Disponibilidad.desde_catalogo(datos.servicios)
    for cita in datos.citas.values():
        try:
            ciclo.confirmar(cita, datos.propietarios[cita.propietario_id], datos.servicios,
                            disponibilidad)
        except PrecondicionNoCumplida:
            continue
        despachador.publicar(cita.extraer_eventos())
    return registro


def escribir_csv(registro: RegistroDeEventos, salida: Path) -> Path:
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / "dominio_eventos.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["secuencia", "evento", "cita_id", "ocurrido_en", "detalle_json"])
        for r in registro.registrados:
            datos = r.evento.a_diccionario()
            escritor.writerow([r.secuencia, datos["evento"], datos["cita_id"],
                               datos["ocurrido_en"], json.dumps(datos, ensure_ascii=False)])
    return ruta


def main(argv: list[str]) -> None:
    registro = confirmar_todas_publicando()
    ruta = escribir_csv(registro, Path(argv[0]) if argv else Path("docs/evidencia"))
    print(f"{len(registro.registrados)} eventos publicados. Evidencia: {ruta}")


if __name__ == "__main__":
    main(sys.argv[1:])
