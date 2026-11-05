"""Control de acceso por rol (ADR-04, R-09, R-14, NB-20).

Cada rol solo puede hacer lo que le corresponde. Recepción opera en nombre del propietario
(A-03). Esta matriz es una propuesta del equipo y se amplía con cada caso de uso nuevo.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from vetcare24.application.errores import AccesoDenegado


class Rol(StrEnum):
    RECEPCION = "recepcion"
    VETERINARIO = "veterinario"
    PERSONAL_CLINICO = "personal_clinico"
    RESPONSABLE = "responsable"


class Permiso(StrEnum):
    REGISTRAR_PROPIETARIO = "registrar_propietario"
    REGISTRAR_MASCOTA = "registrar_mascota"
    SOLICITAR_CITA = "solicitar_cita"
    MODIFICAR_CITA = "modificar_cita"
    CONFIRMAR_CITA = "confirmar_cita"
    CANCELAR_CITA = "cancelar_cita"
    REALIZAR_CITA = "realizar_cita"
    CONSULTAR_CITA = "consultar_cita"
    CONSULTAR_CATALOGO = "consultar_catalogo"
    REGISTRAR_VACUNACION = "registrar_vacunacion"
    CONSULTAR_VACUNACION = "consultar_vacunacion"
    ATENDER_EMERGENCIA = "atender_emergencia"  # CU-05: registrar la emergencia (informe)
    INICIAR_ATENCION_EMERGENCIA = "iniciar_atencion_emergencia"
    CONSULTAR_EMERGENCIA = "consultar_emergencia"


PERMISOS_POR_ROL: Mapping[Rol, frozenset[Permiso]] = {
    Rol.RECEPCION: frozenset({
        Permiso.REGISTRAR_PROPIETARIO, Permiso.REGISTRAR_MASCOTA, Permiso.SOLICITAR_CITA,
        Permiso.MODIFICAR_CITA, Permiso.CONFIRMAR_CITA, Permiso.CANCELAR_CITA,
        Permiso.CONSULTAR_CITA, Permiso.CONSULTAR_CATALOGO, Permiso.CONSULTAR_VACUNACION,
        Permiso.ATENDER_EMERGENCIA, Permiso.CONSULTAR_EMERGENCIA,  # A-01: la identifica
    }),
    Rol.VETERINARIO: frozenset({
        Permiso.REALIZAR_CITA, Permiso.CONSULTAR_CITA, Permiso.CONSULTAR_CATALOGO,
        Permiso.REGISTRAR_VACUNACION, Permiso.CONSULTAR_VACUNACION,
        Permiso.CONSULTAR_EMERGENCIA,  # recibe la notificación y consulta
    }),
    # A-01, A-09: el personal clínico atiende la emergencia (US20). N-07.
    Rol.PERSONAL_CLINICO: frozenset({
        Permiso.INICIAR_ATENCION_EMERGENCIA, Permiso.CONSULTAR_EMERGENCIA,
    }),
    Rol.RESPONSABLE: frozenset({
        Permiso.CONSULTAR_CITA, Permiso.CONSULTAR_CATALOGO, Permiso.CONSULTAR_VACUNACION,
        Permiso.CONSULTAR_EMERGENCIA,
    }),
}


def exigir(rol: Rol, permiso: Permiso) -> None:
    if permiso not in PERMISOS_POR_ROL[rol]:
        raise AccesoDenegado(rol.value, permiso.value)
