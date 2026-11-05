"""Casos de uso y persistencia de Emergencias (Etapa 10, CU-05), en SQLite y PostgreSQL si hay.

Los nombres `test_emergencia_sin_cita_se_registra` y `test_notifica_veterinario_tras_confirmar`
son los que propone la matriz de trazabilidad del informe (NB-19).
"""

from datetime import timedelta

import pytest

from tests.bd import BACKENDS, ERRORES_DE_BD, HORA, armar, preparar, sembrar_basico
from vetcare24.application.comandos import AtenderEmergencia, SolicitarCita
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import AccesoDenegado, NoEncontrado, YaExiste
from vetcare24.application.servicios_emergencias import EstadoDeNotificacion
from vetcare24.domain.emergencia import Emergencia, EstadoEmergencia
from vetcare24.domain.errors import InvarianteViolada, TransicionInvalida
from vetcare24.domain.eventos import EmergenciaIdentificada
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

RECEPCION, CLINICO = Rol.RECEPCION, Rol.PERSONAL_CLINICO
IDENTIFICADA, EN_ATENCION = EstadoEmergencia.IDENTIFICADA, EstadoEmergencia.EN_ATENCION


def _entorno(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    return armar(url)


def _registrar(entorno, motivo="Atropellamiento", **extra):
    return entorno.emergencias.atender_emergencia(RECEPCION, AtenderEmergencia(
        motivo=motivo, **extra))


# --- registrar (atenderEmergencia, CU-05) ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_emergencia_sin_cita_se_registra(backend, tmp_path):
    """NB-19, R-06: la mascota no tiene ninguna cita y la emergencia se registra igual."""
    entorno = _entorno(backend, tmp_path)
    with entorno.fabrica() as uow:
        assert uow.citas.contar() == 0
    resultado = _registrar(entorno, mascota_id="M1")
    e = resultado.emergencia
    assert (e.emergencia_id, e.mascota_id, e.estado, e.identificada_en) == (
        "EMER-001", "M1", IDENTIFICADA, HORA)
    assert resultado.protocolo_activado
    guardada = entorno.emergencias.obtener(RECEPCION, "EMER-001")
    assert (guardada.motivo, guardada.estado) == ("Atropellamiento", IDENTIFICADA)


@pytest.mark.parametrize("backend", BACKENDS)
def test_emergencia_sin_mascota_registrada(backend, tmp_path):
    """P3: mascota opcional; se guardan los datos disponibles del paciente."""
    entorno = _entorno(backend, tmp_path)
    e = _registrar(entorno, datos_paciente="Gato atigrado, lo trae un vecino").emergencia
    guardada = entorno.emergencias.obtener(Rol.VETERINARIO, e.emergencia_id)
    assert guardada.mascota_id is None
    assert guardada.datos_paciente == "Gato atigrado, lo trae un vecino"


@pytest.mark.parametrize("backend", BACKENDS)
def test_notifica_veterinario_tras_confirmar(backend, tmp_path):
    """Informe (CU-05): la notificación se solicita DESPUÉS de confirmar el registro: cuando
    el notificador corre, otra conexión ya ve la emergencia guardada."""
    entorno = _entorno(backend, tmp_path)
    resultado = _registrar(entorno, mascota_id="M1")
    assert resultado.notificacion is EstadoDeNotificacion.NOTIFICADO
    assert entorno.notificador.avisos == [("EMER-001", True)]


@pytest.mark.parametrize("backend", BACKENDS)
def test_si_la_notificacion_falla_el_registro_se_conserva(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    entorno.notificador.falla = True
    resultado = _registrar(entorno, mascota_id="M1")
    assert resultado.notificacion is EstadoDeNotificacion.PENDIENTE
    assert entorno.emergencias.obtener(RECEPCION, "EMER-001").estado is IDENTIFICADA
    assert len(entorno.eventos.registrados) == 1  # el evento sí se publicó


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_evento_se_guarda_y_se_publica(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _registrar(entorno, mascota_id="M1")
    (registrado,) = entorno.eventos.registrados
    assert isinstance(registrado.evento, EmergenciaIdentificada)
    with entorno.fabrica() as uow:
        (guardado,) = uow.eventos.todos()
    assert (guardado["evento"], guardado["agregado_tipo"], guardado["agregado_id"]) == (
        "EmergenciaIdentificada", "Emergencia", "EMER-001")
    assert guardado["cita_id"] is None
    assert guardado["payload"]["mascota_id"] == "M1"


@pytest.mark.parametrize("backend", BACKENDS)
def test_mascota_inexistente_es_no_encontrado_y_no_guarda_ni_notifica(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(NoEncontrado) as error:
        _registrar(entorno, mascota_id="NO-EXISTE")
    assert error.value.tipo == "mascota"
    assert entorno.emergencias.listar(RECEPCION) == []
    assert entorno.notificador.avisos == [] and entorno.eventos.registrados == ()


@pytest.mark.parametrize("backend", BACKENDS)
def test_motivo_vacio_no_guarda_nada(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(InvarianteViolada) as error:
        _registrar(entorno, motivo="  ")
    assert error.value.codigo == "MOTIVO_VACIO"
    assert entorno.emergencias.listar(RECEPCION) == [] and entorno.notificador.avisos == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_id_repetido_es_ya_existe(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _registrar(entorno, emergencia_id="E-A")
    with pytest.raises(YaExiste):
        _registrar(entorno, emergencia_id="E-A")


@pytest.mark.parametrize("backend", BACKENDS)
def test_se_pueden_registrar_varias_emergencias_de_la_misma_mascota(backend, tmp_path):
    """No hay regla que lo impida (N-05): ni el BRD ni el informe limitan las emergencias."""
    entorno = _entorno(backend, tmp_path)
    _registrar(entorno, mascota_id="M1")
    _registrar(entorno, mascota_id="M1", motivo="Otra")
    assert len(entorno.emergencias.listar(RECEPCION, mascota_id="M1")) == 2


# --- iniciar la atención (personal clínico) ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_el_personal_clinico_inicia_la_atencion(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _registrar(entorno, mascota_id="M1")
    entorno.reloj.avanzar(minutes=4)
    e = entorno.emergencias.iniciar_atencion(CLINICO, "EMER-001")
    assert (e.estado, e.atendida_en) == (EN_ATENCION, HORA + timedelta(minutes=4))
    guardada = entorno.emergencias.obtener(CLINICO, "EMER-001")
    assert (guardada.estado, guardada.atendida_en) == (EN_ATENCION, HORA + timedelta(minutes=4))
    with pytest.raises(TransicionInvalida):
        entorno.emergencias.iniciar_atencion(CLINICO, "EMER-001")
    with pytest.raises(NoEncontrado):
        entorno.emergencias.iniciar_atencion(CLINICO, "EMER-XXX")


# --- consultar ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_con_filtros(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _registrar(entorno, mascota_id="M1")
    entorno.reloj.avanzar(minutes=1)
    _registrar(entorno, datos_paciente="sin registro")
    entorno.emergencias.iniciar_atencion(CLINICO, "EMER-001")
    listar = entorno.emergencias.listar
    assert [e.emergencia_id for e in listar(Rol.RESPONSABLE)] == ["EMER-001", "EMER-002"]
    assert [e.emergencia_id for e in listar(CLINICO, estado=IDENTIFICADA)] == ["EMER-002"]
    assert [e.emergencia_id for e in listar(Rol.VETERINARIO, mascota_id="M1")] == ["EMER-001"]
    with pytest.raises(NoEncontrado):
        listar(CLINICO, mascota_id="NO-EXISTE")
    with pytest.raises(NoEncontrado):
        entorno.emergencias.obtener(CLINICO, "EMER-XXX")


# --- AtencionPermitida por el caso de uso (R-06) ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_atencion_permitida_por_cita_confirmada_o_por_emergencia(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    evaluar = entorno.emergencias.evaluar_atencion
    sin_nada = evaluar(Rol.VETERINARIO, "M1")
    assert not sin_nada.cumple
    assert sin_nada.motivos == ("SIN_CITA_CONFIRMADA", "SIN_EMERGENCIA_ACTIVA")
    cita = entorno.citas.solicitar(RECEPCION, SolicitarCita(
        propietario_id="P1", mascota_id="M1", servicios=(("S1", 1),),
        fecha_solicitud=HORA.date(), autorizada=True))
    assert not evaluar(Rol.VETERINARIO, "M1").cumple  # SOLICITADA aún no cuenta
    entorno.citas.confirmar(RECEPCION, cita.cita_id)
    assert evaluar(Rol.VETERINARIO, "M1").cumple  # por la cita confirmada
    entorno.citas.cancelar(RECEPCION, cita.cita_id)
    assert not evaluar(Rol.VETERINARIO, "M1").cumple
    _registrar(entorno, mascota_id="M1")
    assert evaluar(CLINICO, "M1").cumple  # R-06: sin cita, por ser emergencia
    with pytest.raises(NoEncontrado):
        evaluar(CLINICO, "NO-EXISTE")


# --- permisos (N-07) ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_cada_rol_solo_hace_lo_suyo(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    servicio = entorno.emergencias
    for rol in (Rol.VETERINARIO, CLINICO, Rol.RESPONSABLE):
        with pytest.raises(AccesoDenegado):
            servicio.atender_emergencia(rol, AtenderEmergencia(motivo="x"))
    _registrar(entorno)
    for rol in (RECEPCION, Rol.VETERINARIO, Rol.RESPONSABLE):
        with pytest.raises(AccesoDenegado):
            servicio.iniciar_atencion(rol, "EMER-001")
    assert entorno.notificador.avisos == [("EMER-001", True)]  # los rechazos no avisan
    assert servicio.obtener(Rol.RESPONSABLE, "EMER-001").estado is IDENTIFICADA


# --- la base repite las invariantes ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_la_base_rechaza_datos_imposibles(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    base = ("INSERT INTO emergencias (emergencia_id, mascota_id, motivo, estado,"
            " identificada_en, atendida_en) VALUES ")
    for valores in (
        "('EX', NULL, 'a', 'EN_ATENCION', '2026-01-01T00:00:00+00:00', NULL)",
        "('EX', NULL, 'a', 'CERRADA', '2026-01-01T00:00:00+00:00', NULL)",
        "('EX', NULL, '', 'IDENTIFICADA', '2026-01-01T00:00:00+00:00', NULL)",
        "('EX', 'FANTASMA', 'a', 'IDENTIFICADA', '2026-01-01T00:00:00+00:00', NULL)",
    ):
        with entorno.fabrica() as uow, pytest.raises(ERRORES_DE_BD):
            uow._conexion.ejecutar(base + valores)


@pytest.mark.parametrize("backend", BACKENDS)
def test_guardar_una_que_no_existe_es_no_encontrado(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with UnidadDeTrabajoSql(entorno.url) as uow, pytest.raises(NoEncontrado):
        uow.emergencias.guardar(
            Emergencia(emergencia_id="E404", motivo="a", identificada_en=HORA))
