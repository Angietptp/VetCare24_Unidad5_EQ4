"""Dominio de Emergencia (Etapa 10, CU-05): agregado, máquina y AtencionPermitida (OR)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.emergencia import (
    ESTADOS_ACTIVOS,
    TRANSICIONES,
    AccionEmergencia,
    CicloDeVidaDeEmergencia,
    Emergencia,
    EstadoEmergencia,
)
from vetcare24.domain.errors import InvarianteViolada, TransicionInvalida
from vetcare24.domain.eventos import EmergenciaIdentificada
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.reglas_emergencia import (
    MascotaParaAtencion,
    TieneCitaConfirmada,
    TieneEmergenciaActiva,
    atencion_permitida,
)
from vetcare24.domain.specification import Evaluacion

HORA = datetime(2026, 11, 1, 22, 0, tzinfo=UTC)
REX = Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro")
IDENTIFICADA, EN_ATENCION = EstadoEmergencia.IDENTIFICADA, EstadoEmergencia.EN_ATENCION


class Reloj:
    def __init__(self) -> None:
        self.ahora = HORA

    def __call__(self) -> datetime:
        return self.ahora


def _emer(**cambios) -> Emergencia:
    datos = {"emergencia_id": "E1", "motivo": "Atropellamiento", "identificada_en": HORA}
    return Emergencia(**{**datos, **cambios})


def _cita(estado: EstadoCita, mascota: str = "M1") -> Cita:
    return Cita(cita_id=f"C-{estado.value}-{mascota}", propietario_id="P1", mascota_id=mascota,
                lineas=[ServicioSolicitado("S1", 1)], fecha_solicitud=date(2026, 10, 1),
                estado=estado, autorizada=True)


# --- agregado ---

def test_una_emergencia_sin_mascota_registrada_es_valida():
    """P3: la mascota es opcional; se guardan los datos disponibles del paciente."""
    e = _emer(datos_paciente="  Perro   mestizo, sin registro ")
    assert (e.mascota_id, e.estado, e.atendida_en) == (None, IDENTIFICADA, None)
    assert e.datos_paciente == "Perro mestizo, sin registro" and e.esta_activa


@pytest.mark.parametrize(("cambios", "codigo"), [
    ({"emergencia_id": ""}, "ID_VACIO"),
    ({"motivo": "  "}, "MOTIVO_VACIO"),
    ({"motivo": None}, "MOTIVO_VACIO"),
    ({"mascota_id": " "}, "MASCOTA_REQUERIDA"),
    ({"datos_paciente": ""}, "DATOS_PACIENTE_VACIOS"),
    ({"identificada_en": datetime(2026, 11, 1, 22)}, "FECHA_HORA_SIN_ZONA"),
    ({"estado": "IDENTIFICADA"}, "ESTADO_INVALIDO"),
    ({"estado": EN_ATENCION}, "ESTADO_INCONSISTENTE"),
    ({"atendida_en": HORA}, "ESTADO_INCONSISTENTE"),
    ({"estado": EN_ATENCION, "atendida_en": HORA - timedelta(seconds=1)},
     "ATENCION_ANTES_DE_IDENTIFICAR"),
    ({"estado": EN_ATENCION, "atendida_en": datetime(2026, 11, 2)}, "FECHA_HORA_SIN_ZONA"),
])
def test_invariantes_al_reconstituir(cambios, codigo):
    with pytest.raises(InvarianteViolada) as error:
        _emer(**cambios)
    assert error.value.codigo == codigo


def test_identidad_por_id():
    assert _emer() == _emer(motivo="otro") and _emer() != _emer(emergencia_id="E2")
    assert _emer() != "E1" and hash(_emer()) == hash(_emer(motivo="otro"))
    assert repr(_emer(mascota_id="M1")) == "Emergencia('E1', 'M1', IDENTIFICADA)"


# --- identificar (registrar) ---

def test_identificar_activa_el_protocolo_y_deja_el_evento():
    ciclo = CicloDeVidaDeEmergencia(Reloj())
    e = ciclo.identificar(emergencia_id="E1", motivo="Convulsiones", mascota=REX)
    assert (e.estado, e.mascota_id, e.identificada_en) == (IDENTIFICADA, "M1", HORA)
    (evento,) = e.extraer_eventos()
    assert evento == EmergenciaIdentificada(
        ocurrido_en=HORA, emergencia_id="E1", mascota_id="M1", motivo="Convulsiones")
    assert (evento.agregado_tipo, evento.agregado_id) == ("Emergencia", "E1")
    assert e.extraer_eventos() == ()


def test_identificar_sin_mascota_deja_el_evento_sin_mascota():
    ciclo = CicloDeVidaDeEmergencia(Reloj())
    e = ciclo.identificar(emergencia_id="E1", motivo="Golpe", datos_paciente="Gato, sin datos")
    (evento,) = e.extraer_eventos()
    assert evento.mascota_id is None and evento.a_diccionario()["mascota_id"] is None


def test_un_motivo_vacio_no_registra_ni_emite_nada():
    ciclo = CicloDeVidaDeEmergencia(Reloj())
    with pytest.raises(InvarianteViolada) as error:
        ciclo.identificar(emergencia_id="E1", motivo=" ", mascota=REX)
    assert error.value.codigo == "MOTIVO_VACIO"


# --- máquina de estados ---

def test_la_tabla_de_transiciones_es_la_unica_fuente_de_verdad():
    assert TRANSICIONES == {(IDENTIFICADA, AccionEmergencia.INICIAR_ATENCION): EN_ATENCION}
    assert ESTADOS_ACTIVOS == {IDENTIFICADA, EN_ATENCION}  # sin cierre definido (N-05)


def test_iniciar_la_atencion_registra_la_hora():
    reloj = Reloj()
    ciclo = CicloDeVidaDeEmergencia(reloj)
    e = _emer()
    reloj.ahora = HORA + timedelta(minutes=3)
    ciclo.iniciar_atencion(e)
    assert (e.estado, e.atendida_en) == (EN_ATENCION, HORA + timedelta(minutes=3))
    assert e.extraer_eventos() == ()  # D-14 no define evento para este paso (N-06)


def test_iniciar_dos_veces_es_transicion_invalida_y_no_cambia_nada():
    reloj = Reloj()
    ciclo = CicloDeVidaDeEmergencia(reloj)
    e = _emer()
    ciclo.iniciar_atencion(e)
    reloj.ahora = HORA + timedelta(hours=1)
    with pytest.raises(TransicionInvalida) as error:
        ciclo.iniciar_atencion(e)
    assert (error.value.motivo, error.value.entidad) == (
        "iniciar_atencion desde EN_ATENCION", "emergencia")
    assert e.atendida_en == HORA


def test_un_reloj_anterior_a_la_identificacion_se_rechaza_sin_cambios():
    reloj = Reloj()
    ciclo = CicloDeVidaDeEmergencia(reloj)
    e = _emer()
    reloj.ahora = HORA - timedelta(minutes=1)
    with pytest.raises(InvarianteViolada) as error:
        ciclo.iniciar_atencion(e)
    assert error.value.codigo == "ATENCION_ANTES_DE_IDENTIFICAR" and e.estado is IDENTIFICADA


# --- AtencionPermitida = TieneCitaConfirmada OR TieneEmergenciaActiva (R-06) ---

def test_la_regla_es_un_or():
    assert atencion_permitida().descripcion() == "TieneCitaConfirmada OR TieneEmergenciaActiva"


@pytest.mark.parametrize(("citas", "emergencias", "cumple", "motivos"), [
    ((), (), False, ("SIN_CITA_CONFIRMADA", "SIN_EMERGENCIA_ACTIVA")),
    ((EstadoCita.CONFIRMADA,), (), True, ()),
    ((), ("M1",), True, ()),  # R-06: sin cita, pero es emergencia
    ((EstadoCita.CONFIRMADA,), ("M1",), True, ()),
    ((EstadoCita.SOLICITADA, EstadoCita.REALIZADA, EstadoCita.CANCELADA), (), False,
     ("SIN_CITA_CONFIRMADA", "SIN_EMERGENCIA_ACTIVA")),
])
def test_atencion_permitida(citas, emergencias, cumple, motivos):
    contexto = MascotaParaAtencion.de(
        "M1", [_cita(estado) for estado in citas],
        [_emer(emergencia_id=f"E-{m}", mascota_id=m) for m in emergencias])
    assert atencion_permitida().evaluar(contexto) == Evaluacion(cumple, motivos)


def test_el_contexto_ignora_citas_y_emergencias_de_otras_mascotas():
    contexto = MascotaParaAtencion.de(
        "M1", [_cita(EstadoCita.CONFIRMADA, "M2")],
        [_emer(mascota_id="M2"), _emer(emergencia_id="E9")])  # E9: sin mascota
    assert contexto.citas == () and contexto.emergencias == ()
    assert not TieneCitaConfirmada().es_satisfecha_por(contexto)
    assert not TieneEmergenciaActiva().es_satisfecha_por(contexto)


def test_el_contexto_exige_mascota():
    with pytest.raises(InvarianteViolada):
        MascotaParaAtencion.de(" ", [], [])
