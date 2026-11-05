"""Permisos por rol (Etapa 7)."""

import pytest

from vetcare24.application.control_de_acceso import PERMISOS_POR_ROL, Permiso, Rol, exigir
from vetcare24.application.errores import AccesoDenegado


def test_todos_los_roles_tienen_su_conjunto_de_permisos():
    assert set(PERMISOS_POR_ROL) == set(Rol)


def test_recepcion_gestiona_citas_pero_no_las_realiza():
    for permiso in (Permiso.SOLICITAR_CITA, Permiso.MODIFICAR_CITA, Permiso.CONFIRMAR_CITA,
                    Permiso.CANCELAR_CITA, Permiso.REGISTRAR_PROPIETARIO,
                    Permiso.REGISTRAR_MASCOTA):
        exigir(Rol.RECEPCION, permiso)
    with pytest.raises(AccesoDenegado):
        exigir(Rol.RECEPCION, Permiso.REALIZAR_CITA)


def test_veterinario_realiza_y_consulta_pero_no_administra():
    exigir(Rol.VETERINARIO, Permiso.REALIZAR_CITA)
    exigir(Rol.VETERINARIO, Permiso.CONSULTAR_CITA)
    for permiso in (Permiso.SOLICITAR_CITA, Permiso.CONFIRMAR_CITA, Permiso.CANCELAR_CITA,
                    Permiso.MODIFICAR_CITA, Permiso.REGISTRAR_MASCOTA):
        with pytest.raises(AccesoDenegado):
            exigir(Rol.VETERINARIO, permiso)


def test_responsable_solo_consulta():
    exigir(Rol.RESPONSABLE, Permiso.CONSULTAR_CITA)
    exigir(Rol.RESPONSABLE, Permiso.CONSULTAR_CATALOGO)
    with pytest.raises(AccesoDenegado):
        exigir(Rol.RESPONSABLE, Permiso.CONFIRMAR_CITA)


def test_personal_clinico_solo_atiende_y_consulta_emergencias():
    """CU-05 (Etapa 10): sus únicos permisos; nada sobre citas ni vacunas (A-01, A-09, N-07)."""
    propios = {Permiso.INICIAR_ATENCION_EMERGENCIA, Permiso.CONSULTAR_EMERGENCIA}
    assert PERMISOS_POR_ROL[Rol.PERSONAL_CLINICO] == propios
    for permiso in set(Permiso) - propios:
        with pytest.raises(AccesoDenegado):
            exigir(Rol.PERSONAL_CLINICO, permiso)


def test_emergencias_las_registra_recepcion_y_las_atiende_el_personal_clinico():
    exigir(Rol.RECEPCION, Permiso.ATENDER_EMERGENCIA)  # A-01: Recepción la identifica
    exigir(Rol.PERSONAL_CLINICO, Permiso.INICIAR_ATENCION_EMERGENCIA)
    for rol in (Rol.VETERINARIO, Rol.PERSONAL_CLINICO, Rol.RESPONSABLE):
        with pytest.raises(AccesoDenegado):
            exigir(rol, Permiso.ATENDER_EMERGENCIA)
    for rol in (Rol.RECEPCION, Rol.VETERINARIO, Rol.RESPONSABLE):
        with pytest.raises(AccesoDenegado):
            exigir(rol, Permiso.INICIAR_ATENCION_EMERGENCIA)
    for rol in Rol:
        exigir(rol, Permiso.CONSULTAR_EMERGENCIA)


def test_el_error_dice_rol_y_permiso():
    with pytest.raises(AccesoDenegado) as error:
        exigir(Rol.VETERINARIO, Permiso.SOLICITAR_CITA)
    assert (error.value.rol, error.value.permiso) == ("veterinario", "solicitar_cita")


def test_los_roles_se_crean_desde_texto():
    assert Rol("recepcion") is Rol.RECEPCION
    with pytest.raises(ValueError):
        Rol("director")
