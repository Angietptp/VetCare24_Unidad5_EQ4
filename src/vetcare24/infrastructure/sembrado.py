"""Carga los CSV del alumno en la base de datos (D-09: tal cual, sin filtrar) y los esquemas
de vacunación de ejemplo.

Uso:  python -m vetcare24.infrastructure.sembrado
Crea el esquema si falta y carga los datos solo si la base está vacía.
"""

from __future__ import annotations

from vetcare24.application.errores import YaExiste
from vetcare24.application.puertos import UnidadDeTrabajo
from vetcare24.domain.vacunacion import EsquemaDeVacunacion
from vetcare24.infrastructure.adaptador_paquete import DatosDeDominio, construir_dominio
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete
from vetcare24.infrastructure.esquema import crear_esquema
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

# Los CSV del profesor no traen vacunas ni esquemas: estos son datos de EJEMPLO (fixtures),
# sin valor clínico, para poder probar el seguimiento (A-08). Uno de ellos está sin validar a
# propósito, para ejercitar el caso "seguimiento pendiente de esquema validado" (ADR-05).
ESQUEMAS_DE_EJEMPLO = (
    EsquemaDeVacunacion(
        vacuna="VAC-ANUAL", frecuencia_dias=365, requiere_refuerzo=False, validado=True),
    EsquemaDeVacunacion(
        vacuna="VAC-REFUERZO-30D", frecuencia_dias=30, requiere_refuerzo=True, validado=True),
    EsquemaDeVacunacion(
        vacuna="VAC-SIN-VALIDAR", frecuencia_dias=90, requiere_refuerzo=True, validado=False),
)


def sembrar(uow: UnidadDeTrabajo, datos: DatosDeDominio) -> None:
    """Guarda servicios, propietarios, mascotas y citas en UNA transacción."""
    if uow.servicios.todos() or uow.propietarios.todos():
        raise YaExiste("datos", "el paquete (la base ya tiene información)")
    for servicio in datos.servicios.values():
        uow.servicios.agregar(servicio)
    for propietario in datos.propietarios.values():
        uow.propietarios.agregar(propietario)
    for mascota in datos.mascotas.values():
        uow.mascotas.agregar(mascota)
    for cita in datos.citas.values():
        uow.citas.agregar(cita)
    for esquema in ESQUEMAS_DE_EJEMPLO:
        uow.esquemas.agregar(esquema)
    uow.commit()


def main() -> None:
    ajustes = load_settings()
    conexion = conectar(ajustes.database_url)
    crear_esquema(conexion)
    conexion.cerrar()
    datos = construir_dominio(cargar_paquete(ajustes.data_dir))
    try:
        with UnidadDeTrabajoSql(ajustes.database_url) as uow:
            sembrar(uow, datos)
    except YaExiste:
        print("La base ya tenía datos; no se cargó nada.")
        return
    print(f"Cargados: {len(datos.servicios)} servicios, {len(datos.propietarios)} propietarios, "
          f"{len(datos.mascotas)} mascotas, {len(datos.citas)} citas.")


if __name__ == "__main__":
    main()
