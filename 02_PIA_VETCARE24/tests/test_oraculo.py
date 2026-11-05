"""Pruebas del oráculo (Etapa 2): se prueba primero el instrumento con el que se medirá."""

from datetime import date
from decimal import Decimal

import pytest

from tests import oraculo
from tests.oraculo import ReglaDesconocida, evaluar_regla, resolver_transicion, total_mxn
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import (
    Actor,
    Linea,
    Operacion,
    PaqueteDatos,
    Recurso,
    TransicionPrueba,
    cargar_paquete,
)

REGLA_1 = "validar cliente activo AND detalle no vacio AND autorizacion"
REGLA_2 = "VIP AND total >=1500 AND NOT promocion"


def _paquete(
    *, activo=True, preferente=True, autorizado=True, promocion=False,
    habilitado=True, capacidad=10, lineas=(("VET-P001", 3),), precio="500.00",
) -> PaqueteDatos:
    """Un paquete mínimo hecho a mano, con una sola operación VET-O001."""
    return PaqueteDatos(
        actores={"A": Actor("A", "Tutor", preferente, activo, "Monterrey")},
        recursos={"VET-P001": Recurso("VET-P001", "Consulta", Decimal(precio), capacidad,
                                      habilitado)},
        operaciones={"VET-O001": Operacion("VET-O001", "A", "SOLICITADA", date(2026, 10, 2),
                                           promocion, autorizado, "REF")},
        lineas={"VET-O001": tuple(Linea("VET-O001", r, q) for r, q in lineas)} if lineas else {},
        casos=(),
        transiciones=(),
    )


def _transicion(paquete, accion):
    caso = TransicionPrueba("S", "VET-O001", accion, "SOLICITADA", "")
    return resolver_transicion(paquete, caso)


def _cumple(regla, paquete):
    return evaluar_regla(regla, paquete, paquete.operaciones["VET-O001"])[0]


# --- total e importes ---

def test_total_usa_decimal_exacto():
    p = _paquete(precio="10.10", lineas=(("VET-P001", 3),))
    assert total_mxn(p, "VET-O001") == Decimal("30.30")
    assert total_mxn(p, "VET-O001").as_tuple().exponent == -2


def test_total_de_operacion_sin_lineas_es_cero():
    assert total_mxn(_paquete(lineas=()), "VET-O001") == Decimal("0.00")


# --- evaluación del texto de las reglas ---

def test_regla_1_cumple_cuando_todo_es_valido():
    assert _cumple(REGLA_1, _paquete())


@pytest.mark.parametrize("cambio", [{"activo": False}, {"autorizado": False}, {"lineas": ()}])
def test_regla_1_falla_si_falta_una_condicion(cambio):
    assert not _cumple(REGLA_1, _paquete(**cambio))


def test_regla_2_umbral_incluyente_en_1500():
    p = _paquete(precio="500.00", lineas=(("VET-P001", 3),))  # total exacto 1500.00
    assert _cumple(REGLA_2, p)


def test_regla_2_bajo_el_umbral_no_cumple():
    assert not _cumple(REGLA_2, _paquete(precio="499.99", lineas=(("VET-P001", 3),)))


def test_regla_2_promocion_activa_la_bloquea():
    assert not _cumple(REGLA_2, _paquete(promocion=True))


def test_regla_2_requiere_actor_preferente():
    assert not _cumple(REGLA_2, _paquete(preferente=False))


def test_precedencia_not_and_or():
    texto = "VIP OR cliente activo AND NOT promocion"
    assert _cumple(texto, _paquete(preferente=False, activo=True, promocion=False))
    assert not _cumple(texto, _paquete(preferente=False, activo=True, promocion=True))
    assert _cumple(texto, _paquete(preferente=True, activo=False, promocion=True))


def test_reporta_las_condiciones_fallidas():
    p = _paquete(activo=False)
    _, fallidas = evaluar_regla(REGLA_1, p, p.operaciones["VET-O001"])
    assert fallidas == ("cliente activo",)


def test_regla_desconocida_no_se_inventa():
    p = _paquete()
    with pytest.raises(ReglaDesconocida):
        evaluar_regla("cliente activo AND mascota vacunada", p, p.operaciones["VET-O001"])


# --- máquina de estados de referencia ---

def test_aprobar_confirma():
    r = _transicion(_paquete(), "aprobar")
    assert (r.estado_final, r.eventos, r.excepcion) == ("CONFIRMADA", ("CitaAgendada",), None)


def test_completar_confirma_y_realiza():
    r = _transicion(_paquete(), "completar")
    assert r.estado_final == "REALIZADA"
    assert r.eventos == ("CitaAgendada", "CitaRealizada")


def test_cancelar_desde_solicitada():
    r = _transicion(_paquete(), "cancelar")
    assert (r.estado_final, r.eventos) == ("CANCELADA", ("CitaCancelada",))


def test_repetir_aprobacion_rechaza_la_segunda():
    r = _transicion(_paquete(), "repetir_aprobacion")
    assert r.estado_final == "CONFIRMADA"
    assert r.excepcion == "TransicionInvalida"
    assert r.eventos == ("CitaAgendada",)


def test_saltar_estado_es_invalido():
    r = _transicion(_paquete(), "saltar_estado")
    assert (r.estado_final, r.excepcion, r.eventos) == ("SOLICITADA", "TransicionInvalida", ())


def test_confirmar_con_actor_inactivo_se_bloquea():
    r = _transicion(_paquete(activo=False), "aprobar")
    assert r.excepcion == "PrecondicionNoCumplida"
    assert r.motivos == ("ACTOR_INACTIVO",)
    assert r.estado_final == "SOLICITADA"


def test_confirmar_con_servicio_deshabilitado_se_bloquea():
    r = _transicion(_paquete(habilitado=False), "aprobar")
    assert r.motivos == ("SERVICIO_DESHABILITADO:VET-P001",)


def test_confirmar_sin_capacidad_se_bloquea():
    r = _transicion(_paquete(capacidad=2, lineas=(("VET-P001", 3),)), "aprobar")
    assert r.motivos == ("CAPACIDAD_INSUFICIENTE:VET-P001",)


def test_cancelar_no_depende_de_que_el_actor_siga_activo():
    """D-12: cancelar solo exige el estado correcto."""
    r = _transicion(_paquete(activo=False), "cancelar")
    assert r.estado_final == "CANCELADA"


def test_accion_desconocida():
    with pytest.raises(ValueError, match="Acción desconocida"):
        _transicion(_paquete(), "archivar")


# --- sobre los datos reales ---

def test_resultados_sobre_los_120_casos_reales():
    p = cargar_paquete(load_settings().data_dir)
    resultados = [oraculo.resolver_caso(p, c) for c in p.casos]
    assert len(resultados) == 120
    por_tipo = {}
    for r in resultados:
        por_tipo.setdefault(r.tipo_prueba, []).append(r.cumple)
    assert sum(por_tipo["validar_operacion"]) == 43
    assert sum(por_tipo["evaluar_beneficio"]) == 9


def test_resultados_sobre_las_20_transiciones_reales():
    p = cargar_paquete(load_settings().data_dir)
    resultados = [resolver_transicion(p, t) for t in p.transiciones]
    conteo = {}
    for r in resultados:
        clave = r.excepcion or "OK"
        conteo[clave] = conteo.get(clave, 0) + 1
    assert conteo == {"OK": 6, "TransicionInvalida": 6, "PrecondicionNoCumplida": 8}


def test_genera_la_evidencia_en_csv(tmp_path):
    p = cargar_paquete(load_settings().data_dir)
    ruta_casos, ruta_trans = oraculo.generar_evidencia(p, tmp_path)
    assert len(ruta_casos.read_text(encoding="utf-8-sig").splitlines()) == 121
    assert len(ruta_trans.read_text(encoding="utf-8-sig").splitlines()) == 21
