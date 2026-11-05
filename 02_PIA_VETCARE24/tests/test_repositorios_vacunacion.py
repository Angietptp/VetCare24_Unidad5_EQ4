"""Repositorios de vacunación y eventos de varios agregados (Etapa 9)."""

from datetime import UTC, date, datetime

import pytest

from tests.bd import BACKENDS, ERRORES_DE_BD, preparar, sembrar_basico
from vetcare24.domain.eventos import CitaAgendada, EventoDeDominio, VacunacionRegistrada
from vetcare24.domain.money import Money
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

HORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _v(vacunacion_id, vacuna="Rabia", fecha=date(2026, 10, 1), lote=None, mascota="M1"):
    return Vacunacion(vacunacion_id=vacunacion_id, mascota_id=mascota, vacuna=vacuna,
                      fecha_aplicacion=fecha, lote=lote)


@pytest.mark.parametrize("backend", BACKENDS)
def test_vacunaciones_se_guardan_y_se_leen_iguales(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.vacunaciones.agregar(_v("V1", "Triple  Felina", date(2026, 10, 1), "L-ñ1"))
        uow.vacunaciones.agregar(_v("V2"))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        v1 = uow.vacunaciones.obtener("V1")
        assert (v1.vacuna, v1.clave, v1.fecha_aplicacion, v1.lote) == (
            "Triple Felina", "triple felina", date(2026, 10, 1), "L-ñ1")
        assert uow.vacunaciones.obtener("V2").lote is None
        assert uow.vacunaciones.obtener("NO") is None


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_historial_sale_ordenado_por_fecha_y_luego_por_id(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.vacunaciones.agregar(_v("V3", fecha=date(2026, 10, 5)))
        uow.vacunaciones.agregar(_v("V2", fecha=date(2026, 10, 1)))
        uow.vacunaciones.agregar(_v("V1", fecha=date(2026, 10, 1)))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        assert [v.vacunacion_id for v in uow.vacunaciones.de_mascota("M1")] == ["V1", "V2", "V3"]
        assert uow.vacunaciones.de_mascota("M9") == []
        assert [v.vacunacion_id for v in uow.vacunaciones.todas()] == ["V1", "V2", "V3"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_la_base_exige_una_mascota_existente_y_ids_unicos(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with pytest.raises(ERRORES_DE_BD):
        with UnidadDeTrabajoSql(url) as uow:
            uow.vacunaciones.agregar(_v("V1", mascota="NO-EXISTE"))
    with UnidadDeTrabajoSql(url) as uow:
        uow.vacunaciones.agregar(_v("V1"))
        uow.commit()
    with pytest.raises(ERRORES_DE_BD):
        with UnidadDeTrabajoSql(url) as uow:
            uow.vacunaciones.agregar(_v("V1"))


@pytest.mark.parametrize("backend", BACKENDS)
def test_esquemas_se_guardan_por_clave_normalizada(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="Rabia", frecuencia_dias=365, requiere_refuerzo=False, validado=True))
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="Triple Felina", frecuencia_dias=30, requiere_refuerzo=True, validado=False))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        esquemas = uow.esquemas.todos()
    assert list(esquemas) == ["rabia", "triple felina"]
    assert (esquemas["rabia"].frecuencia_dias, esquemas["rabia"].validado) == (365, True)
    assert esquemas["triple felina"].requiere_refuerzo is True
    assert esquemas["triple felina"].vacuna == "Triple Felina"


@pytest.mark.parametrize("backend", BACKENDS)
def test_no_se_repite_el_esquema_de_una_vacuna_aunque_cambien_las_mayusculas(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="Rabia", frecuencia_dias=365, requiere_refuerzo=False, validado=True))
        uow.commit()
    with pytest.raises(ERRORES_DE_BD):
        with UnidadDeTrabajoSql(url) as uow:
            uow.esquemas.agregar(EsquemaDeVacunacion(
                vacuna="RABIA", frecuencia_dias=30, requiere_refuerzo=True, validado=True))


@pytest.mark.parametrize("backend", BACKENDS)
def test_la_base_rechaza_una_frecuencia_imposible(backend, tmp_path):
    url = preparar(backend, tmp_path)
    con = conectar(url)
    with pytest.raises(ERRORES_DE_BD):
        con.ejecutar("INSERT INTO esquemas_vacunacion VALUES ('rabia', 'Rabia', 0, 0, 1)")
    con.rollback()
    con.cerrar()


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_eventos_de_distintos_agregados_conviven_en_orden(backend, tmp_path):
    url = preparar(backend, tmp_path)
    cita = CitaAgendada(ocurrido_en=HORA, cita_id="C1", propietario_id="P1", mascota_id="M1",
                        servicios=(("S1", 1),), total=Money.mxn("10"))
    vacuna = VacunacionRegistrada(
        ocurrido_en=HORA, vacunacion_id="V1", mascota_id="M1", vacuna="Rabia",
        fecha_aplicacion=date(2026, 10, 1), lote=None)
    with UnidadDeTrabajoSql(url) as uow:
        uow.eventos.agregar(cita)
        uow.eventos.agregar(vacuna)
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        primero, segundo = uow.eventos.todos()
    assert (primero["agregado_tipo"], primero["agregado_id"], primero["cita_id"]) == (
        "Cita", "C1", "C1")
    assert (segundo["agregado_tipo"], segundo["agregado_id"], segundo["cita_id"]) == (
        "Vacunacion", "V1", None)
    assert segundo["evento"] == "VacunacionRegistrada"
    assert segundo["payload"]["fecha_aplicacion"] == "2026-10-01"
    assert segundo["secuencia"] > primero["secuencia"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_un_evento_sin_agregado_se_rechaza(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        with pytest.raises(ValueError, match="no declara el agregado"):
            uow.eventos.agregar(EventoDeDominio(ocurrido_en=HORA))
