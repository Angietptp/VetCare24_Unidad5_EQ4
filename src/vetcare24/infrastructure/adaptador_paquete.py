"""Adaptador del paquete de pruebas al dominio (ADR-08, capa anticorrupción).

Convierte las filas de los CSV en objetos del dominio. Es la única pieza que conoce los
nombres del paquete (actor, recurso, operación...). El dominio solo habla VetCare 24.

Decisión D-10: los CSV no traen mascotas ni veterinarios, así que se crea una mascota
sintética por propietario, marcada como fixture, para poder asociar cada cita a una mascota.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.ciclo_de_vida import Accion, CicloDeVidaDeCita
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import InvarianteViolada, PrecondicionNoCumplida, TransicionInvalida
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.infrastructure.csv_loader import ErrorDeDatos, PaqueteDatos, TransicionPrueba

ESPECIE_FIXTURE = "Fixture"


def id_mascota_sintetica(propietario_id: str) -> str:
    return f"{propietario_id}-MASCOTA"


@dataclass(frozen=True)
class DatosDeDominio:
    propietarios: dict[str, Propietario]
    mascotas: dict[str, Mascota]
    servicios: dict[str, ServicioVeterinario]
    citas: dict[str, Cita]


def construir_dominio(paquete: PaqueteDatos) -> DatosDeDominio:
    try:
        propietarios = {
            a.actor_id: Propietario(a.actor_id, a.nombre, a.activo, a.es_preferente)
            for a in paquete.actores.values()
        }
        mascotas = {
            id_mascota_sintetica(a.actor_id): Mascota(
                mascota_id=id_mascota_sintetica(a.actor_id),
                propietario_id=a.actor_id,
                nombre=f"Mascota fixture de {a.nombre}",
                especie=ESPECIE_FIXTURE,
            )
            for a in paquete.actores.values()
        }
        servicios = {
            r.recurso_id: ServicioVeterinario(
                r.recurso_id, r.descripcion, Money.mxn(r.precio_mxn), r.capacidad, r.habilitado
            )
            for r in paquete.recursos.values()
        }
        citas = {}
        for op in paquete.operaciones.values():
            try:
                estado = EstadoCita(op.estado_inicial)
            except ValueError as error:
                raise ErrorDeDatos(
                    f"{op.operacion_id}: estado desconocido {op.estado_inicial!r}"
                ) from error
            citas[op.operacion_id] = Cita(
                cita_id=op.operacion_id,
                propietario_id=op.actor_id,
                mascota_id=id_mascota_sintetica(op.actor_id),
                lineas=[
                    ServicioSolicitado(ln.recurso_id, ln.cantidad)
                    for ln in paquete.lineas_de(op.operacion_id)
                ],
                fecha_solicitud=op.fecha_solicitud,
                estado=estado,
                autorizada=op.autorizado,
                promocion_activa=op.promocion_activa,
                referencia=op.referencia,
            )
    except InvarianteViolada as error:
        raise ErrorDeDatos(f"El paquete no cabe en el dominio: {error}") from error
    return DatosDeDominio(propietarios, mascotas, servicios, citas)


# --- Acciones del paquete sobre el dominio (D-11) ---------------------------------------------

ACCIONES_DEL_PAQUETE: dict[str, tuple[Accion, ...]] = {
    "aprobar": (Accion.CONFIRMAR,),
    "completar": (Accion.CONFIRMAR, Accion.REALIZAR),
    "cancelar": (Accion.CANCELAR,),
    "repetir_aprobacion": (Accion.CONFIRMAR, Accion.CONFIRMAR),
    "saltar_estado": (Accion.REALIZAR,),
}


@dataclass(frozen=True)
class ResultadoDeAccion:
    estado_final: str
    excepcion: str | None
    motivos: tuple[str, ...]
    eventos: tuple[str, ...] = ()


def ejecutar_accion_del_paquete(datos: DatosDeDominio, caso: TransicionPrueba) -> ResultadoDeAccion:
    """Ejecuta una acción de `transiciones_prueba.csv` sobre una COPIA de la cita.

    Cada caso es independiente: parte de SOLICITADA y de la capacidad inicial (E-04). Una
    acción de varios pasos no es atómica: si un paso falla, los anteriores se conservan (E-05).
    """
    pasos = ACCIONES_DEL_PAQUETE.get(caso.accion)
    if pasos is None:
        raise ErrorDeDatos(f"{caso.caso_id}: acción desconocida {caso.accion!r}")
    cita = copy.deepcopy(datos.citas[caso.operacion_id])
    propietario = datos.propietarios[cita.propietario_id]
    disponibilidad = Disponibilidad.desde_catalogo(datos.servicios)
    ciclo = CicloDeVidaDeCita()

    def resultado(excepcion: str | None, motivos: tuple[str, ...]) -> ResultadoDeAccion:
        eventos = tuple(evento.nombre for evento in cita.extraer_eventos())
        return ResultadoDeAccion(cita.estado.value, excepcion, motivos, eventos)

    for paso in pasos:
        try:
            if paso is Accion.CONFIRMAR:
                ciclo.confirmar(cita, propietario, datos.servicios, disponibilidad)
            elif paso is Accion.REALIZAR:
                ciclo.realizar(cita)
            else:
                ciclo.cancelar(cita, disponibilidad)
        except TransicionInvalida as error:
            return resultado("TransicionInvalida", (error.motivo,))
        except PrecondicionNoCumplida as error:
            return resultado("PrecondicionNoCumplida", error.motivos)
    return resultado(None, ())
