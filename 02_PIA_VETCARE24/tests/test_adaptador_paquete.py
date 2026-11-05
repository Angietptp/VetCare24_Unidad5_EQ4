"""El adaptador convierte los CSV al dominio; sus totales deben coincidir con el oráculo."""

import dataclasses

import pytest

from tests.evidencia_eventos import confirmar_todas_publicando, escribir_csv
from tests.oraculo import confirmar_en_secuencia, resolver_transicion, total_mxn
from vetcare24.domain.ciclo_de_vida import CicloDeVidaDeCita
from vetcare24.domain.cita import EstadoCita
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import PrecondicionNoCumplida
from vetcare24.domain.eventos import CitaAgendada
from vetcare24.infrastructure.adaptador_paquete import (
    ESPECIE_FIXTURE,
    construir_dominio,
    ejecutar_accion_del_paquete,
    id_mascota_sintetica,
)
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import ErrorDeDatos, cargar_paquete


def _datos():
    paquete = cargar_paquete(load_settings().data_dir)
    return paquete, construir_dominio(paquete)


def test_construye_todos_los_objetos():
    _, d = _datos()
    conteos = (len(d.propietarios), len(d.mascotas), len(d.servicios), len(d.citas))
    assert conteos == (40, 40, 20, 60)


def test_los_60_totales_coinciden_con_el_oraculo():
    paquete, d = _datos()
    for cita_id, cita in d.citas.items():
        assert cita.total(d.servicios).monto == total_mxn(paquete, cita_id), cita_id


def test_todas_las_citas_arrancan_solicitadas():
    _, d = _datos()
    assert {c.estado for c in d.citas.values()} == {EstadoCita.SOLICITADA}


def test_conserva_lo_que_las_reglas_rechazaran():
    paquete, d = _datos()
    assert sum(not c.lineas for c in d.citas.values()) == 2
    assert sum(not c.autorizada for c in d.citas.values()) == 7
    assert sum(not p.activo for p in d.propietarios.values()) == 5
    assert sum(not s.habilitado for s in d.servicios.values()) == 1


def test_cada_cita_tiene_una_mascota_fixture_del_mismo_propietario():
    _, d = _datos()
    for cita in d.citas.values():
        mascota = d.mascotas[cita.mascota_id]
        assert mascota.propietario_id == cita.propietario_id
        assert mascota.mascota_id == id_mascota_sintetica(cita.propietario_id)
        assert mascota.especie == ESPECIE_FIXTURE


def test_estado_desconocido_se_reporta_como_error_de_datos():
    paquete, _ = _datos()
    rota = dataclasses.replace(paquete.operaciones["VET-O001"], estado_inicial="ARCHIVADA")
    operaciones = {**paquete.operaciones, "VET-O001": rota}
    with pytest.raises(ErrorDeDatos, match="estado desconocido"):
        construir_dominio(dataclasses.replace(paquete, operaciones=operaciones))


def test_dato_que_viola_un_invariante_se_reporta_como_error_de_datos():
    paquete, _ = _datos()
    linea = dataclasses.replace(paquete.lineas["VET-O001"][0], cantidad=0)
    lineas = {**paquete.lineas, "VET-O001": (linea,)}
    with pytest.raises(ErrorDeDatos, match="no cabe en el dominio"):
        construir_dominio(dataclasses.replace(paquete, lineas=lineas))


# --- Etapa 5: acciones del paquete sobre el dominio, contra el oráculo ---

def test_las_20_transiciones_del_dominio_coinciden_con_el_oraculo():
    paquete, d = _datos()
    assert len(paquete.transiciones) == 20
    for caso in paquete.transiciones:
        esperado = resolver_transicion(paquete, caso)
        obtenido = ejecutar_accion_del_paquete(d, caso)
        assert obtenido.estado_final == esperado.estado_final, caso.caso_id
        assert obtenido.excepcion == esperado.excepcion, caso.caso_id
        assert obtenido.motivos == esperado.motivos, caso.caso_id
        assert obtenido.eventos == esperado.eventos, caso.caso_id


def test_ejecutar_una_accion_no_modifica_los_datos_originales():
    paquete, d = _datos()
    for caso in paquete.transiciones:
        ejecutar_accion_del_paquete(d, caso)
    assert {c.estado for c in d.citas.values()} == {EstadoCita.SOLICITADA}


def test_accion_desconocida_es_error_de_datos():
    paquete, d = _datos()
    caso = dataclasses.replace(paquete.transiciones[0], accion="archivar")
    with pytest.raises(ErrorDeDatos, match="acción desconocida"):
        ejecutar_accion_del_paquete(d, caso)


def test_confirmacion_en_secuencia_del_dominio_coincide_con_el_oraculo():
    """Las 60 citas en orden, con capacidad compartida (D-08)."""
    paquete, d = _datos()
    ciclo, disponibilidad = CicloDeVidaDeCita(), Disponibilidad.desde_catalogo(d.servicios)
    obtenido = {}
    for cita_id, cita in d.citas.items():
        try:
            ciclo.confirmar(cita, d.propietarios[cita.propietario_id], d.servicios, disponibilidad)
            obtenido[cita_id] = ()
        except PrecondicionNoCumplida as error:
            obtenido[cita_id] = error.motivos
    assert obtenido == confirmar_en_secuencia(paquete)
    assert sum(not m for m in obtenido.values()) == 38


# --- Etapa 6: eventos publicados al confirmar las 60 citas ---

def test_los_eventos_publicados_corresponden_a_las_citas_confirmadas():
    paquete, _ = _datos()
    confirmadas = [cita_id for cita_id, motivos in confirmar_en_secuencia(paquete).items()
                   if not motivos]
    registro = confirmar_todas_publicando()
    agendadas = registro.de_tipo(CitaAgendada)
    assert len(registro.registrados) == len(agendadas) == 38
    assert [r.evento.cita_id for r in agendadas] == confirmadas
    assert [r.secuencia for r in agendadas] == list(range(1, 39))


def test_el_total_del_evento_coincide_con_el_oraculo():
    paquete, _ = _datos()
    for registrado in confirmar_todas_publicando().registrados:
        assert registrado.evento.total.monto == total_mxn(paquete, registrado.evento.cita_id)


def test_escribe_la_evidencia_de_eventos(tmp_path):
    ruta = escribir_csv(confirmar_todas_publicando(), tmp_path)
    assert len(ruta.read_text(encoding="utf-8-sig").splitlines()) == 39
