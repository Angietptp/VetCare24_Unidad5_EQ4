"""Máquina de estados de la Cita (Etapa 5)."""

from datetime import date

import pytest

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.ciclo_de_vida import TRANSICIONES, Accion, CicloDeVidaDeCita
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import InvarianteViolada, PrecondicionNoCumplida, TransicionInvalida
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.reglas_cita import CitaEnContexto, puede_cancelarse, puede_modificarse

CICLO = CicloDeVidaDeCita()
PROPIETARIO = Propietario("P1", "Ana")


def _catalogo(capacidad=5, habilitado=True):
    return {
        "S1": ServicioVeterinario("S1", "Consulta", Money.mxn("300"), capacidad, habilitado),
        "S2": ServicioVeterinario("S2", "Vacuna", Money.mxn("100"), capacidad),
    }


def _cita(lineas=(("S1", 2),), estado=EstadoCita.SOLICITADA, autorizada=True, cita_id="C1"):
    return Cita(
        cita_id=cita_id, propietario_id="P1", mascota_id="M1",
        lineas=[ServicioSolicitado(s, q) for s, q in lineas],
        fecha_solicitud=date(2026, 10, 2), estado=estado, autorizada=autorizada,
    )


def _confirmar(cita, catalogo=None, disponibilidad=None, propietario=PROPIETARIO):
    catalogo = catalogo or _catalogo()
    disponibilidad = disponibilidad or Disponibilidad.desde_catalogo(catalogo)
    CICLO.confirmar(cita, propietario, catalogo, disponibilidad)
    return disponibilidad


# --- la tabla de transiciones ---

def test_la_tabla_define_exactamente_las_transiciones_del_diseno():
    assert dict(TRANSICIONES) == {
        (EstadoCita.SOLICITADA, Accion.CONFIRMAR): EstadoCita.CONFIRMADA,
        (EstadoCita.CONFIRMADA, Accion.REALIZAR): EstadoCita.REALIZADA,
        (EstadoCita.SOLICITADA, Accion.CANCELAR): EstadoCita.CANCELADA,
        (EstadoCita.CONFIRMADA, Accion.CANCELAR): EstadoCita.CANCELADA,
        (EstadoCita.SOLICITADA, Accion.MODIFICAR): EstadoCita.SOLICITADA,
        (EstadoCita.CONFIRMADA, Accion.MODIFICAR): EstadoCita.CONFIRMADA,
    }


def test_las_specifications_de_estado_coinciden_con_la_tabla():
    """Una sola verdad: cancelar y modificar valen exactamente donde la tabla lo permite."""
    for estado in EstadoCita:
        ctx = CitaEnContexto(_cita(estado=estado), PROPIETARIO, _catalogo())
        cancelable = (estado, Accion.CANCELAR) in TRANSICIONES
        modificable = (estado, Accion.MODIFICAR) in TRANSICIONES
        assert puede_cancelarse().es_satisfecha_por(ctx) == cancelable
        assert puede_modificarse().es_satisfecha_por(ctx) == modificable


def test_toda_combinacion_fuera_de_la_tabla_es_invalida():
    catalogo = _catalogo()
    for estado in EstadoCita:
        for accion in Accion:
            if (estado, accion) in TRANSICIONES:
                continue
            cita = _cita(estado=estado)
            disp = Disponibilidad.desde_catalogo(catalogo)
            nuevas = [ServicioSolicitado("S1", 1)]
            llamadas = {
                Accion.CONFIRMAR: lambda c=cita, d=disp: CICLO.confirmar(
                    c, PROPIETARIO, catalogo, d),
                Accion.REALIZAR: lambda c=cita: CICLO.realizar(c),
                Accion.CANCELAR: lambda c=cita, d=disp: CICLO.cancelar(c, d),
                Accion.MODIFICAR: lambda c=cita, d=disp, n=nuevas: CICLO.modificar(
                    c, n, catalogo, d),
            }
            with pytest.raises(TransicionInvalida) as error:
                llamadas[accion]()
            assert error.value.motivo == f"{accion.value} desde {estado.value}"
            assert cita.estado is estado


# --- confirmar ---

def test_confirmar_cambia_el_estado_y_consume_capacidad():
    cita = _cita(lineas=(("S1", 2), ("S2", 1)))
    disp = _confirmar(cita)
    assert cita.estado is EstadoCita.CONFIRMADA
    assert (disp.disponible("S1"), disp.disponible("S2")) == (3, 4)


def test_confirmar_con_actor_inactivo_no_cambia_nada():
    cita = _cita()
    disp = Disponibilidad.desde_catalogo(_catalogo())
    with pytest.raises(PrecondicionNoCumplida) as error:
        CICLO.confirmar(cita, Propietario("P1", "Ana", activo=False), _catalogo(), disp)
    assert error.value.motivos == ("ACTOR_INACTIVO",)
    assert error.value.accion == "confirmar"
    assert cita.estado is EstadoCita.SOLICITADA and disp.disponible("S1") == 5


def test_confirmar_sin_autorizacion_o_sin_detalle():
    with pytest.raises(PrecondicionNoCumplida) as error:
        _confirmar(_cita(autorizada=False))
    assert error.value.motivos == ("NO_AUTORIZADA",)
    with pytest.raises(PrecondicionNoCumplida) as error:
        _confirmar(_cita(lineas=()))
    assert error.value.motivos == ("DETALLE_VACIO",)


def test_confirmar_servicio_deshabilitado():
    with pytest.raises(PrecondicionNoCumplida) as error:
        _confirmar(_cita(), catalogo=_catalogo(habilitado=False))
    assert error.value.motivos == ("SERVICIO_DESHABILITADO:S1",)


def test_la_capacidad_es_acumulada_la_segunda_cita_ya_no_cabe():
    catalogo = _catalogo(capacidad=5)
    disp = Disponibilidad.desde_catalogo(catalogo)
    primera = _cita(lineas=(("S1", 3),), cita_id="C1")
    segunda = _cita(lineas=(("S1", 3),), cita_id="C2")
    CICLO.confirmar(primera, PROPIETARIO, catalogo, disp)
    with pytest.raises(PrecondicionNoCumplida) as error:
        CICLO.confirmar(segunda, PROPIETARIO, catalogo, disp)
    assert error.value.motivos == ("CAPACIDAD_INSUFICIENTE:S1",)
    assert segunda.estado is EstadoCita.SOLICITADA and disp.disponible("S1") == 2


def test_cabe_justo_en_la_capacidad():
    catalogo = _catalogo(capacidad=5)
    disp = Disponibilidad.desde_catalogo(catalogo)
    CICLO.confirmar(_cita(lineas=(("S1", 5),)), PROPIETARIO, catalogo, disp)
    assert disp.disponible("S1") == 0


def test_el_propietario_debe_ser_el_de_la_cita():
    with pytest.raises(InvarianteViolada) as error:
        _confirmar(_cita(), propietario=Propietario("P2", "Otro"))
    assert error.value.codigo == "PROPIETARIO_INCORRECTO"


# --- D-12: primero la validez de la transición, luego las condiciones ---

def test_si_la_transicion_es_invalida_no_se_evaluan_las_condiciones():
    cita = _cita(estado=EstadoCita.CONFIRMADA)
    with pytest.raises(TransicionInvalida):
        CICLO.confirmar(cita, Propietario("P1", "Ana", activo=False), _catalogo(),
                        Disponibilidad.desde_catalogo(_catalogo()))


def test_repetir_la_aprobacion_se_rechaza_y_no_consume_dos_veces():
    cita = _cita()
    disp = _confirmar(cita)
    with pytest.raises(TransicionInvalida):
        CICLO.confirmar(cita, PROPIETARIO, _catalogo(), disp)
    assert disp.disponible("S1") == 3 and cita.estado is EstadoCita.CONFIRMADA


# --- realizar y cancelar ---

def test_realizar_no_libera_la_capacidad():
    cita = _cita()
    disp = _confirmar(cita)
    CICLO.realizar(cita)
    assert cita.estado is EstadoCita.REALIZADA and disp.disponible("S1") == 3


def test_cancelar_desde_confirmada_libera_la_capacidad():
    cita = _cita()
    disp = _confirmar(cita)
    CICLO.cancelar(cita, disp)
    assert cita.estado is EstadoCita.CANCELADA and disp.disponible("S1") == 5


def test_cancelar_desde_solicitada_no_toca_la_capacidad():
    cita = _cita()
    disp = Disponibilidad.desde_catalogo(_catalogo())
    CICLO.cancelar(cita, disp)
    assert cita.estado is EstadoCita.CANCELADA and disp.disponible("S1") == 5


def test_cancelar_no_depende_de_que_el_propietario_siga_activo():
    """D-12: cancelar solo exige el estado correcto."""
    cita = _cita()
    CICLO.cancelar(cita, Disponibilidad.desde_catalogo(_catalogo()))
    assert cita.estado is EstadoCita.CANCELADA


def test_los_estados_terminales_no_tienen_salida():
    for terminal in (EstadoCita.REALIZADA, EstadoCita.CANCELADA):
        cita = _cita(estado=terminal)
        with pytest.raises(TransicionInvalida):
            CICLO.cancelar(cita, Disponibilidad.desde_catalogo(_catalogo()))
        with pytest.raises(TransicionInvalida):
            CICLO.realizar(cita)


def test_ciclo_completo_confirmar_realizar():
    cita = _cita()
    _confirmar(cita)
    CICLO.realizar(cita)
    assert cita.estado is EstadoCita.REALIZADA


# --- modificar (A-06) ---

def test_modificar_solicitada_cambia_las_lineas_sin_tocar_capacidad():
    cita = _cita()
    disp = Disponibilidad.desde_catalogo(_catalogo())
    CICLO.modificar(cita, [ServicioSolicitado("S2", 4)], _catalogo(), disp)
    assert cita.estado is EstadoCita.SOLICITADA
    assert cita.demanda_por_servicio() == {"S2": 4} and disp.disponible("S2") == 5


def test_modificar_confirmada_reajusta_la_capacidad():
    cita = _cita(lineas=(("S1", 2),))
    disp = _confirmar(cita)
    CICLO.modificar(cita, [ServicioSolicitado("S1", 4), ServicioSolicitado("S2", 1)],
                    _catalogo(), disp)
    assert cita.estado is EstadoCita.CONFIRMADA
    assert (disp.disponible("S1"), disp.disponible("S2")) == (1, 4)


def test_modificar_confirmada_sin_capacidad_no_cambia_nada():
    catalogo = _catalogo(capacidad=5)
    disp = Disponibilidad.desde_catalogo(catalogo)
    cita = _cita(lineas=(("S1", 2),))
    CICLO.confirmar(cita, PROPIETARIO, catalogo, disp)
    otra = _cita(lineas=(("S1", 2),), cita_id="C2")
    CICLO.confirmar(otra, PROPIETARIO, catalogo, disp)  # quedan 1 unidad
    with pytest.raises(PrecondicionNoCumplida) as error:
        CICLO.modificar(cita, [ServicioSolicitado("S1", 5)], catalogo, disp)
    assert error.value.motivos == ("CAPACIDAD_INSUFICIENTE:S1",)
    assert cita.demanda_por_servicio() == {"S1": 2} and disp.disponible("S1") == 1


def test_modificar_aplica_las_reglas_de_lineas_nuevas():
    cita = _cita()
    disp = Disponibilidad.desde_catalogo(_catalogo())
    casos = [([], "DETALLE_VACIO"), ([ServicioSolicitado("S9", 1)], "SERVICIO_INEXISTENTE")]
    for lineas, codigo in casos:
        with pytest.raises(InvarianteViolada) as error:
            CICLO.modificar(cita, lineas, _catalogo(), disp)
        assert error.value.codigo == codigo
    with pytest.raises(InvarianteViolada) as error:
        CICLO.modificar(cita, [ServicioSolicitado("S1", 1)], _catalogo(habilitado=False), disp)
    assert error.value.codigo == "SERVICIO_DESHABILITADO"
    assert cita.demanda_por_servicio() == {"S1": 2}


def test_modificar_cita_finalizada_es_transicion_invalida():
    with pytest.raises(TransicionInvalida):
        CICLO.modificar(_cita(estado=EstadoCita.REALIZADA), [ServicioSolicitado("S1", 1)],
                        _catalogo(), Disponibilidad.desde_catalogo(_catalogo()))
