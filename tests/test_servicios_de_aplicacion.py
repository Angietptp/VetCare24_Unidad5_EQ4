"""Casos de uso de la aplicación (Etapa 7): permisos, persistencia, eventos y capacidad."""

from datetime import date

import pytest

from tests.bd import BACKENDS, armar, preparar, sembrar_basico
from vetcare24.application.comandos import (
    ModificarCita,
    RegistrarMascota,
    RegistrarPropietario,
    SolicitarCita,
)
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import AccesoDenegado, NoEncontrado, YaExiste
from vetcare24.domain.cita import EstadoCita
from vetcare24.domain.errors import InvarianteViolada, PrecondicionNoCumplida, TransicionInvalida
from vetcare24.domain.eventos import CitaAgendada, CitaCancelada, CitaModificada, CitaRealizada

FECHA = date(2026, 10, 2)
RECEPCION, VETERINARIO = Rol.RECEPCION, Rol.VETERINARIO


def _entorno(backend, tmp_path, capacidad=5):
    url = preparar(backend, tmp_path)
    sembrar_basico(url, capacidad)
    return armar(url)


def _solicitar(entorno, servicios=(("S1", 3),), cita_id=None):
    return entorno.citas.solicitar(RECEPCION, SolicitarCita(
        propietario_id="P1", mascota_id="M1", servicios=tuple(servicios),
        fecha_solicitud=FECHA, autorizada=True, cita_id=cita_id))


def _estado_guardado(entorno, cita_id):
    with entorno.fabrica() as uow:
        return uow.citas.obtener(cita_id).estado


def _eventos_guardados(entorno):
    with entorno.fabrica() as uow:
        return [e["evento"] for e in uow.eventos.todos()]


# --- registro ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_propietario_y_mascota(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    propietario = entorno.registro.registrar_propietario(
        RECEPCION, RegistrarPropietario("Luis", preferente=True))
    assert propietario.propietario_id == "PROP-001" and propietario.preferente
    mascota = entorno.registro.registrar_mascota(RECEPCION, RegistrarMascota(
        propietario_id="PROP-001", nombre="Max", especie="Perro", peso_kg="12.5",
        alergias=("Polen",)))
    assert mascota.mascota_id == "MASC-002"
    assert entorno.registro.obtener_propietario(RECEPCION, "PROP-001").nombre == "Luis"
    leida = entorno.registro.obtener_mascota(RECEPCION, "MASC-002")
    assert leida.alergias == ("Polen",)
    assert [s.servicio_id for s in entorno.registro.listar_servicios(RECEPCION)] == [
        "S1", "S2", "S3"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_registro_rechaza_duplicados_y_referencias_rotas(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(YaExiste):
        entorno.registro.registrar_propietario(
            RECEPCION, RegistrarPropietario("Otra Ana", propietario_id="P1"))
    with pytest.raises(NoEncontrado):
        entorno.registro.registrar_mascota(RECEPCION, RegistrarMascota(
            propietario_id="P9", nombre="x", especie="y"))
    with pytest.raises(YaExiste):
        entorno.registro.registrar_mascota(RECEPCION, RegistrarMascota(
            propietario_id="P1", nombre="x", especie="y", mascota_id="M1"))
    for consulta in (entorno.registro.obtener_propietario, entorno.registro.obtener_mascota):
        with pytest.raises(NoEncontrado):
            consulta(RECEPCION, "NO-EXISTE")


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_registro_respeta_los_permisos(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(AccesoDenegado):
        entorno.registro.registrar_propietario(VETERINARIO, RegistrarPropietario("Luis"))
    with pytest.raises(AccesoDenegado):
        entorno.registro.registrar_mascota(
            Rol.RESPONSABLE, RegistrarMascota(propietario_id="P1", nombre="x", especie="y"))
    with pytest.raises(AccesoDenegado):
        entorno.registro.listar_servicios(Rol.PERSONAL_CLINICO)


# --- solicitar ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitar_guarda_la_cita_solicitada_sin_eventos(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _solicitar(entorno)
    assert cita.cita_id == "CITA-001" and cita.estado is EstadoCita.SOLICITADA
    assert _estado_guardado(entorno, "CITA-001") is EstadoCita.SOLICITADA
    assert _eventos_guardados(entorno) == [] and entorno.eventos.registrados == ()


@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitar_rechaza_lo_que_el_dominio_no_permite_y_no_guarda_nada(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    for servicios, codigo in [((), "DETALLE_VACIO"), ((("S3", 1),), "SERVICIO_DESHABILITADO"),
                              ((("S9", 1),), "SERVICIO_INEXISTENTE")]:
        with pytest.raises(InvarianteViolada) as error:
            _solicitar(entorno, servicios)
        assert error.value.codigo == codigo
    with entorno.fabrica() as uow:
        assert uow.citas.contar() == 0


@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitar_valida_propietario_mascota_y_duplicados(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(NoEncontrado):
        entorno.citas.solicitar(RECEPCION, SolicitarCita(
            propietario_id="P9", mascota_id="M1", servicios=(("S1", 1),),
            fecha_solicitud=FECHA, autorizada=True))
    with pytest.raises(NoEncontrado):
        entorno.citas.solicitar(RECEPCION, SolicitarCita(
            propietario_id="P1", mascota_id="M9", servicios=(("S1", 1),),
            fecha_solicitud=FECHA, autorizada=True))
    _solicitar(entorno, cita_id="C-FIJA")
    with pytest.raises(YaExiste):
        _solicitar(entorno, cita_id="C-FIJA")


@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitar_rechaza_mascota_de_otro_propietario(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    entorno.registro.registrar_propietario(
        RECEPCION, RegistrarPropietario("Luis", propietario_id="P2"))
    with pytest.raises(InvarianteViolada) as error:
        entorno.citas.solicitar(RECEPCION, SolicitarCita(
            propietario_id="P2", mascota_id="M1", servicios=(("S1", 1),),
            fecha_solicitud=FECHA, autorizada=True))
    assert error.value.codigo == "MASCOTA_AJENA"


# --- permisos ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_cada_rol_solo_hace_lo_suyo(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with pytest.raises(AccesoDenegado):
        entorno.citas.solicitar(VETERINARIO, SolicitarCita(
            propietario_id="P1", mascota_id="M1", servicios=(("S1", 1),),
            fecha_solicitud=FECHA, autorizada=True))
    _solicitar(entorno)
    with pytest.raises(AccesoDenegado):
        entorno.citas.confirmar(VETERINARIO, "CITA-001")
    entorno.citas.confirmar(RECEPCION, "CITA-001")
    with pytest.raises(AccesoDenegado):
        entorno.citas.realizar(RECEPCION, "CITA-001")
    with pytest.raises(AccesoDenegado):
        entorno.citas.cancelar(VETERINARIO, "CITA-001")
    with pytest.raises(AccesoDenegado):
        entorno.citas.modificar(Rol.RESPONSABLE, ModificarCita("CITA-001", (("S1", 1),)))
    assert entorno.citas.obtener(Rol.RESPONSABLE, "CITA-001").estado is EstadoCita.CONFIRMADA
    with pytest.raises(AccesoDenegado):
        entorno.citas.obtener(Rol.PERSONAL_CLINICO, "CITA-001")
    with pytest.raises(AccesoDenegado):
        entorno.citas.listar(Rol.PERSONAL_CLINICO)


# --- confirmar, realizar, cancelar, modificar ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_confirmar_guarda_el_estado_y_el_evento_y_lo_publica(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _solicitar(entorno)
    cita = entorno.citas.confirmar(RECEPCION, "CITA-001")
    assert cita.estado is EstadoCita.CONFIRMADA
    assert _estado_guardado(entorno, "CITA-001") is EstadoCita.CONFIRMADA
    assert _eventos_guardados(entorno) == ["CitaAgendada"]
    (registrado,) = entorno.eventos.registrados
    assert isinstance(registrado.evento, CitaAgendada)
    assert registrado.evento.total.monto == 900


@pytest.mark.parametrize("backend", BACKENDS)
def test_la_capacidad_es_acumulada_entre_peticiones_y_cancelar_la_libera(backend, tmp_path):
    entorno = _entorno(backend, tmp_path, capacidad=5)
    _solicitar(entorno, (("S1", 3),), cita_id="C1")
    _solicitar(entorno, (("S1", 3),), cita_id="C2")
    entorno.citas.confirmar(RECEPCION, "C1")
    with pytest.raises(PrecondicionNoCumplida) as error:
        entorno.citas.confirmar(RECEPCION, "C2")
    assert error.value.motivos == ("CAPACIDAD_INSUFICIENTE:S1",)
    assert _estado_guardado(entorno, "C2") is EstadoCita.SOLICITADA
    assert _eventos_guardados(entorno) == ["CitaAgendada"]  # el rechazo no dejó rastro
    entorno.citas.cancelar(RECEPCION, "C1")
    entorno.citas.confirmar(RECEPCION, "C2")  # ahora sí cabe
    assert _eventos_guardados(entorno) == ["CitaAgendada", "CitaCancelada", "CitaAgendada"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_realizar_conserva_el_consumo_de_capacidad(backend, tmp_path):
    entorno = _entorno(backend, tmp_path, capacidad=5)
    _solicitar(entorno, (("S1", 3),), cita_id="C1")
    _solicitar(entorno, (("S1", 3),), cita_id="C2")
    entorno.citas.confirmar(RECEPCION, "C1")
    cita = entorno.citas.realizar(VETERINARIO, "C1")
    assert cita.estado is EstadoCita.REALIZADA
    assert isinstance(entorno.eventos.registrados[-1].evento, CitaRealizada)
    with pytest.raises(PrecondicionNoCumplida):
        entorno.citas.confirmar(RECEPCION, "C2")


@pytest.mark.parametrize("backend", BACKENDS)
def test_cancelar_desde_solicitada_y_desde_confirmada(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _solicitar(entorno, cita_id="C1")
    _solicitar(entorno, cita_id="C2")
    entorno.citas.cancelar(RECEPCION, "C1")
    entorno.citas.confirmar(RECEPCION, "C2")
    entorno.citas.cancelar(RECEPCION, "C2")
    anteriores = [r.evento.estado_anterior for r in entorno.eventos.de_tipo(CitaCancelada)]
    assert anteriores == ["SOLICITADA", "CONFIRMADA"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_modificar_reajusta_las_lineas_y_la_capacidad(backend, tmp_path):
    entorno = _entorno(backend, tmp_path, capacidad=5)
    _solicitar(entorno, (("S1", 3),), cita_id="C1")
    entorno.citas.confirmar(RECEPCION, "C1")
    entorno.citas.modificar(RECEPCION, ModificarCita("C1", (("S1", 5), ("S2", 1))))
    with entorno.fabrica() as uow:
        assert uow.citas.obtener("C1").demanda_por_servicio() == {"S1": 5, "S2": 1}
        assert uow.citas.demanda_ocupada() == {"S1": 5, "S2": 1}
    (evento,) = entorno.eventos.de_tipo(CitaModificada)[0:1]
    assert evento.evento.servicios_anteriores == (("S1", 3),)
    with pytest.raises(PrecondicionNoCumplida):
        entorno.citas.modificar(RECEPCION, ModificarCita("C1", (("S1", 6),)))
    with pytest.raises(InvarianteViolada):
        entorno.citas.modificar(RECEPCION, ModificarCita("C1", ()))


@pytest.mark.parametrize("backend", BACKENDS)
def test_transiciones_invalidas_y_citas_inexistentes(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _solicitar(entorno)
    with pytest.raises(TransicionInvalida):
        entorno.citas.realizar(VETERINARIO, "CITA-001")
    entorno.citas.confirmar(RECEPCION, "CITA-001")
    with pytest.raises(TransicionInvalida):
        entorno.citas.confirmar(RECEPCION, "CITA-001")
    for accion in (lambda: entorno.citas.confirmar(RECEPCION, "NO-EXISTE"),
                   lambda: entorno.citas.obtener(RECEPCION, "NO-EXISTE")):
        with pytest.raises(NoEncontrado):
            accion()
    assert _eventos_guardados(entorno) == ["CitaAgendada"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_un_manejador_que_falla_no_deshace_lo_guardado(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)

    def malo(evento):
        raise RuntimeError("falla el aviso")

    entorno.despachador.suscribir(CitaAgendada, malo)
    _solicitar(entorno)
    cita = entorno.citas.confirmar(RECEPCION, "CITA-001")
    assert cita.estado is EstadoCita.CONFIRMADA
    assert _estado_guardado(entorno, "CITA-001") is EstadoCita.CONFIRMADA
    assert len(entorno.despachador.fallos) == 1


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_citas_con_filtros(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    _solicitar(entorno, cita_id="C1")
    _solicitar(entorno, cita_id="C2")
    entorno.citas.confirmar(RECEPCION, "C2")
    todas = entorno.citas.listar(Rol.RESPONSABLE)
    assert [c.cita_id for c in todas] == ["C1", "C2"]
    confirmadas = entorno.citas.listar(RECEPCION, estado=EstadoCita.CONFIRMADA)
    assert [c.cita_id for c in confirmadas] == ["C2"]
    assert entorno.citas.listar(RECEPCION, propietario_id="P9") == []
