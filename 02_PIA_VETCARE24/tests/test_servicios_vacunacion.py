"""Casos de uso de Vacunación (Etapa 9), en SQLite y en PostgreSQL si hay."""

from datetime import date

import pytest

from tests.bd import BACKENDS, armar, preparar, sembrar_basico, sembrar_esquemas
from vetcare24.application.comandos import RegistrarVacunacion
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import AccesoDenegado, NoEncontrado, YaExiste
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.eventos import VacunacionRegistrada
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.seguimiento_vacunacion import EstadoDeSeguimiento
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

VETERINARIO, RECEPCION, RESPONSABLE = Rol.VETERINARIO, Rol.RECEPCION, Rol.RESPONSABLE


def _entorno(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    sembrar_esquemas(url)
    return armar(url)


def _vacunar(entorno, vacuna="VAC-REFUERZO", fecha=date(2026, 10, 1), mascota="M1", **extra):
    return entorno.vacunacion.registrar(VETERINARIO, RegistrarVacunacion(
        mascota_id=mascota, vacuna=vacuna, fecha_aplicacion=fecha, **extra))


def _segunda_mascota(entorno):
    with UnidadDeTrabajoSql(entorno.url) as uow:
        uow.propietarios.agregar(Propietario("P2", "Luis"))
        uow.mascotas.agregar(
            Mascota(mascota_id="M2", propietario_id="P2", nombre="Max", especie="Perro"))
        uow.commit()


# --- registrar ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_guarda_publica_y_calcula_el_seguimiento(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    resultado = _vacunar(entorno, lote="L-1")
    assert resultado.vacunacion.vacunacion_id == "VAC-001" and resultado.vacunacion.lote == "L-1"
    s = resultado.seguimiento
    assert s.estado is EstadoDeSeguimiento.CALCULADO
    assert (s.proxima_aplicacion, s.es_refuerzo) == (date(2026, 10, 31), True)
    (registrado,) = entorno.eventos.registrados
    assert isinstance(registrado.evento, VacunacionRegistrada)
    with entorno.fabrica() as uow:
        (guardado,) = uow.eventos.todos()
    assert (guardado["agregado_tipo"], guardado["agregado_id"]) == ("Vacunacion", "VAC-001")
    assert guardado["payload"]["vacuna"] == "VAC-REFUERZO"


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_no_depende_del_esquema(backend, tmp_path):
    """ADR-05 (b): sin esquema o con esquema sin validar, el registro SE GUARDA igual y el
    seguimiento queda pendiente; no es un error."""
    entorno = _entorno(backend, tmp_path)
    sin_esquema = _vacunar(entorno, vacuna="VAC-DESCONOCIDA")
    sin_validar = _vacunar(entorno, vacuna="VAC-SIN-VALIDAR")
    assert sin_esquema.seguimiento.estado is EstadoDeSeguimiento.PENDIENTE_DE_ESQUEMA
    assert sin_esquema.seguimiento.motivos == ("ESQUEMA_NO_DEFINIDO",)
    assert sin_validar.seguimiento.motivos == ("ESQUEMA_NO_VALIDADO",)
    assert len(entorno.vacunacion.historial(VETERINARIO, "M1")) == 2


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_historial_se_conserva_y_el_seguimiento_usa_la_ultima(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _vacunar(entorno, "VAC-ANUAL", date(2024, 9, 1))
    _vacunar(entorno, "VAC-ANUAL", date(2025, 9, 1))
    ultimo = _vacunar(entorno, "vac-anual", date(2026, 9, 1))  # distinto uso de mayúsculas
    assert ultimo.seguimiento.proxima_aplicacion == date(2027, 9, 1)
    historial = entorno.vacunacion.historial(RECEPCION, "M1")
    assert [v.fecha_aplicacion.year for v in historial] == [2024, 2025, 2026]  # R-11
    (seg,) = entorno.vacunacion.seguimiento(RESPONSABLE, "M1")
    assert seg.ultima_aplicacion == date(2026, 9, 1)
    assert len(entorno.eventos.registrados) == 3


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_valida_permisos_mascota_y_datos(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    for rol in (RECEPCION, RESPONSABLE, Rol.PERSONAL_CLINICO):
        with pytest.raises(AccesoDenegado):
            entorno.vacunacion.registrar(
                rol, RegistrarVacunacion("M1", "VAC-ANUAL", date(2026, 1, 1)))
    with pytest.raises(NoEncontrado):
        _vacunar(entorno, mascota="NO-EXISTE")
    with pytest.raises(InvarianteViolada) as error:
        _vacunar(entorno, vacuna="  ")
    assert error.value.codigo == "VACUNA_VACIA"
    _vacunar(entorno, vacunacion_id="V-FIJA")
    with pytest.raises(YaExiste):
        _vacunar(entorno, vacunacion_id="V-FIJA")
    assert len(entorno.vacunacion.historial(VETERINARIO, "M1")) == 1  # lo rechazado no se guardó
    assert len(entorno.eventos.registrados) == 1


@pytest.mark.parametrize("backend", BACKENDS)
def test_un_manejador_que_falla_no_deshace_el_registro(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)

    def malo(evento):
        raise RuntimeError("falla el aviso")

    entorno.despachador.suscribir(VacunacionRegistrada, malo)
    _vacunar(entorno)
    assert len(entorno.vacunacion.historial(VETERINARIO, "M1")) == 1
    assert len(entorno.despachador.fallos) == 1


# --- consultas ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_consultas_exigen_permiso_y_mascota_existente(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    for consulta in (entorno.vacunacion.historial, entorno.vacunacion.seguimiento):
        with pytest.raises(AccesoDenegado):
            consulta(Rol.PERSONAL_CLINICO, "M1")
        with pytest.raises(NoEncontrado):
            consulta(VETERINARIO, "NO-EXISTE")
    with pytest.raises(AccesoDenegado):
        entorno.vacunacion.listar_esquemas(Rol.PERSONAL_CLINICO)
    assert entorno.vacunacion.historial(VETERINARIO, "M1") == []
    assert entorno.vacunacion.seguimiento(VETERINARIO, "M1") == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_esquemas(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    esquemas = entorno.vacunacion.listar_esquemas(RECEPCION)
    assert [e.vacuna for e in esquemas] == ["VAC-ANUAL", "VAC-REFUERZO", "VAC-SIN-VALIDAR"]
    assert [e.validado for e in esquemas] == [True, True, False]


# --- recordatorios ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_proximas_incluye_vencidas_y_las_de_la_ventana(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _segunda_mascota(entorno)
    _vacunar(entorno, "VAC-REFUERZO", date(2026, 9, 1))             # próxima 2026-10-01: vencida
    _vacunar(entorno, "VAC-REFUERZO", date(2026, 10, 10), "M2")     # próxima 2026-11-09
    _vacunar(entorno, "VAC-ANUAL", date(2026, 10, 10), "M2")        # próxima 2027-10-10: lejos
    _vacunar(entorno, "VAC-SIN-VALIDAR", date(2026, 9, 1))          # pendiente: no aparece
    hoy = date(2026, 10, 15)
    avisos = entorno.vacunacion.proximas(RECEPCION, hoy=hoy, dentro_de_dias=30)
    assert [(a.mascota_id, a.vacuna, a.proxima_aplicacion, a.vencida) for a in avisos] == [
        ("M1", "VAC-REFUERZO", date(2026, 10, 1), True),
        ("M2", "VAC-REFUERZO", date(2026, 11, 9), False),
    ]
    assert [a.propietario_id for a in avisos] == ["P1", "P2"]
    assert all(a.es_refuerzo for a in avisos)
    solo_vencidas = entorno.vacunacion.proximas(RESPONSABLE, hoy=hoy, dentro_de_dias=0)
    assert [a.mascota_id for a in solo_vencidas] == ["M1"]
    assert entorno.vacunacion.proximas(RESPONSABLE, hoy=hoy, dentro_de_dias=400)[-1].vacuna == (
        "VAC-ANUAL")


@pytest.mark.parametrize("backend", BACKENDS)
def test_proximas_valida_permiso_y_ventana(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(AccesoDenegado):
        entorno.vacunacion.proximas(Rol.PERSONAL_CLINICO, hoy=date(2026, 1, 1), dentro_de_dias=1)
    for ventana in (-1, True, 1.5, "7"):
        with pytest.raises(InvarianteViolada) as error:
            entorno.vacunacion.proximas(RECEPCION, hoy=date(2026, 1, 1), dentro_de_dias=ventana)
        assert error.value.codigo == "VENTANA_INVALIDA"
    assert entorno.vacunacion.proximas(RECEPCION, hoy=date(2026, 1, 1), dentro_de_dias=30) == []
