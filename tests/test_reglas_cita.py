"""Reglas de la cita (Etapa 4): casos hechos a mano y comparación con el oráculo."""

from datetime import date

import pytest

from tests import oraculo
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.reglas_cita import (
    CitaEnContexto,
    EnEstado,
    beneficio_de_referencia,
    disponibilidad_inicial,
    esta_finalizada,
    puede_cancelarse,
    puede_confirmarse,
    puede_modificarse,
    puede_procesarse,
)
from vetcare24.infrastructure.adaptador_paquete import construir_dominio
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete


def _contexto(*, lineas=(("S1", 3),), activo=True, preferente=True, autorizada=True,
              promocion=False, habilitado=True, capacidad=10, precio="500",
              estado=EstadoCita.SOLICITADA, disponible=None):
    servicio = ServicioVeterinario("S1", "Consulta", Money.mxn(precio), capacidad, habilitado)
    catalogo = {"S1": servicio}
    cita = Cita(
        cita_id="C1", propietario_id="P1", mascota_id="M1",
        lineas=[ServicioSolicitado(s, q) for s, q in lineas],
        fecha_solicitud=date(2026, 10, 2), estado=estado,
        autorizada=autorizada, promocion_activa=promocion,
    )
    propietario = Propietario("P1", "Ana", activo=activo, preferente=preferente)
    disp = disponibilidad_inicial(catalogo) if disponible is None else disponible
    return CitaEnContexto(cita, propietario, catalogo, disp)


# --- PuedeProcesarse (D-03) ---

def test_puede_procesarse_cuando_todo_es_valido():
    assert puede_procesarse().evaluar(_contexto()).cumple


@pytest.mark.parametrize("cambio, motivo", [
    ({"activo": False}, "ACTOR_INACTIVO"),
    ({"lineas": ()}, "DETALLE_VACIO"),
    ({"autorizada": False}, "NO_AUTORIZADA"),
])
def test_puede_procesarse_explica_cada_falla(cambio, motivo):
    assert puede_procesarse().evaluar(_contexto(**cambio)).motivos == (motivo,)


def test_puede_procesarse_junta_varios_motivos():
    r = puede_procesarse().evaluar(_contexto(activo=False, autorizada=False))
    assert r.motivos == ("ACTOR_INACTIVO", "NO_AUTORIZADA")


# --- PuedeConfirmarse (D-12) ---

def test_puede_confirmarse_cuando_hay_capacidad_y_servicio_habilitado():
    assert puede_confirmarse().evaluar(_contexto()).cumple


def test_confirmar_bloquea_servicio_deshabilitado():
    r = puede_confirmarse().evaluar(_contexto(habilitado=False))
    assert r.motivos == ("SERVICIO_DESHABILITADO:S1",)


def test_confirmar_bloquea_servicio_fuera_del_catalogo():
    r = puede_confirmarse().evaluar(_contexto(lineas=(("S9", 1),)))
    assert r.motivos[0] == "SERVICIO_INEXISTENTE:S9"


def test_confirmar_bloquea_si_no_cabe_en_la_capacidad():
    assert puede_confirmarse().evaluar(_contexto(capacidad=2)).motivos == (
        "CAPACIDAD_INSUFICIENTE:S1",)


def test_capacidad_usa_lo_disponible_no_la_capacidad_total():
    ctx = _contexto(capacidad=10, disponible={"S1": 2})
    assert puede_confirmarse().evaluar(ctx).motivos == ("CAPACIDAD_INSUFICIENTE:S1",)
    assert puede_confirmarse().evaluar(_contexto(capacidad=10, disponible={"S1": 3})).cumple


def test_servicio_sin_disponibilidad_registrada_cuenta_como_cero():
    assert not puede_confirmarse().evaluar(_contexto(disponible={})).cumple


def test_capacidad_suma_servicios_repetidos():
    ctx = _contexto(lineas=(("S1", 3), ("S1", 3)), capacidad=5)
    assert not puede_confirmarse().evaluar(ctx).cumple


# --- BeneficioDeReferencia (D-05) ---

def test_beneficio_con_total_exacto_en_el_umbral():
    assert beneficio_de_referencia().evaluar(_contexto(precio="500", lineas=(("S1", 3),))).cumple


def test_beneficio_bajo_el_umbral_se_niega():
    r = beneficio_de_referencia().evaluar(_contexto(precio="499.99"))
    assert r.motivos == ("TOTAL_INSUFICIENTE",)


def test_beneficio_con_promocion_activa_se_niega():
    r = beneficio_de_referencia().evaluar(_contexto(promocion=True))
    assert r.motivos == ("PROMOCION_ACTIVA",)


def test_beneficio_exige_propietario_preferente_y_umbral_configurable():
    assert beneficio_de_referencia().evaluar(_contexto(preferente=False)).motivos == (
        "NO_PREFERENTE",)
    assert beneficio_de_referencia(Money.mxn("2000")).evaluar(_contexto()).motivos == (
        "TOTAL_INSUFICIENTE",)


# --- Estados (D-07, A-06) ---

@pytest.mark.parametrize("estado, cancelable", [
    (EstadoCita.SOLICITADA, True), (EstadoCita.CONFIRMADA, True),
    (EstadoCita.REALIZADA, False), (EstadoCita.CANCELADA, False),
])
def test_cancelar_y_modificar_solo_si_no_esta_finalizada(estado, cancelable):
    ctx = _contexto(estado=estado)
    assert puede_cancelarse().es_satisfecha_por(ctx) is cancelable
    assert puede_modificarse().es_satisfecha_por(ctx) is cancelable
    assert esta_finalizada().es_satisfecha_por(ctx) is (not cancelable)


def test_cita_finalizada_explica_el_motivo():
    ctx = _contexto(estado=EstadoCita.REALIZADA)
    assert puede_cancelarse().evaluar(ctx).motivos == ("CITA_FINALIZADA",)
    assert EnEstado(EstadoCita.CONFIRMADA).evaluar(ctx).motivos == ("NO_ESTA_CONFIRMADA",)


def test_descripciones_de_las_reglas_compuestas():
    assert puede_procesarse().descripcion() == "ActorActivo AND DetalleNoVacio AND Autorizada"
    assert beneficio_de_referencia().descripcion() == (
        "PropietarioPreferente AND TotalMinimo(1500.00 MXN) AND NOT PromocionActiva")
    assert puede_cancelarse().descripcion() == "NOT (EnEstado(REALIZADA) OR EnEstado(CANCELADA))"


def test_el_contexto_exige_que_el_propietario_sea_el_de_la_cita():
    ctx = _contexto()
    with pytest.raises(InvarianteViolada) as error:
        CitaEnContexto(ctx.cita, Propietario("P2", "Otro"), ctx.catalogo)
    assert error.value.codigo == "PROPIETARIO_INCORRECTO"


# --- Contra el oráculo, con los datos reales ---

def _datos():
    paquete = cargar_paquete(load_settings().data_dir)
    return paquete, construir_dominio(paquete)


def _contexto_real(d, cita_id):
    cita = d.citas[cita_id]
    return CitaEnContexto(
        cita, d.propietarios[cita.propietario_id], d.servicios, disponibilidad_inicial(d.servicios)
    )


def test_las_specifications_coinciden_con_el_oraculo_en_los_120_casos():
    paquete, d = _datos()
    reglas = {
        "validar_operacion": puede_procesarse(),
        "evaluar_beneficio": beneficio_de_referencia(),
    }
    for caso in paquete.casos:
        esperado = oraculo.resolver_caso(paquete, caso).cumple
        obtenido = reglas[caso.tipo_prueba].es_satisfecha_por(_contexto_real(d, caso.operacion_id))
        assert obtenido == esperado, caso.caso_id


def test_los_motivos_de_confirmar_coinciden_con_el_oraculo_en_las_60_operaciones():
    paquete, d = _datos()
    disponible = {r.recurso_id: r.capacidad for r in paquete.recursos.values()}
    for op_id, op in paquete.operaciones.items():
        esperado = oraculo.bloqueos_para_confirmar(paquete, op, disponible)
        obtenido = puede_confirmarse().evaluar(_contexto_real(d, op_id)).motivos
        assert obtenido == esperado, op_id
