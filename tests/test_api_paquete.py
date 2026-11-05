"""Los datos del profesor a través de la API (Etapa 8), en SQLite y en PostgreSQL si hay."""

import pytest
from fastapi.testclient import TestClient

from tests.api_paquete import (
    comparar_casos,
    comparar_confirmaciones,
    comparar_transiciones,
    ejecutar_casos,
    ejecutar_confirmaciones,
    ejecutar_transiciones,
)
from tests.bd import BACKENDS, preparar
from vetcare24.api.main import create_app
from vetcare24.infrastructure.adaptador_paquete import construir_dominio
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql
from vetcare24.infrastructure.sembrado import sembrar


def _api_sembrada(backend, tmp_path):
    url = preparar(backend, tmp_path)
    paquete = cargar_paquete(load_settings().data_dir)
    with UnidadDeTrabajoSql(url) as uow:
        sembrar(uow, construir_dominio(paquete))
    return TestClient(create_app(url, preparar_esquema=False)), paquete


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_120_casos_por_la_api_coinciden_con_el_oraculo(backend, tmp_path):
    cliente, paquete = _api_sembrada(backend, tmp_path)
    resultados = ejecutar_casos(cliente, paquete)
    assert len(resultados) == 120
    assert comparar_casos(resultados, paquete) == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_las_20_transiciones_por_la_api_coinciden_con_el_oraculo(backend, tmp_path):
    cliente, paquete = _api_sembrada(backend, tmp_path)
    resultados = ejecutar_transiciones(cliente, paquete)
    assert len(resultados) == 20
    assert comparar_transiciones(resultados, paquete) == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_confirmar_las_60_citas_por_la_api_coincide_con_el_oraculo(backend, tmp_path):
    cliente, paquete = _api_sembrada(backend, tmp_path)
    obtenido = ejecutar_confirmaciones(cliente, paquete)
    assert comparar_confirmaciones(obtenido, paquete) == []
    assert sum(status == 200 for status, _ in obtenido.values()) == 38
    assert {status for status, _ in obtenido.values()} == {200, 422}


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_estados_http_de_las_transiciones_son_los_del_contrato(backend, tmp_path):
    cliente, paquete = _api_sembrada(backend, tmp_path)
    estados = [r.status_final for r in ejecutar_transiciones(cliente, paquete)]
    assert sorted(estados) == [200] * 6 + [409] * 6 + [422] * 8
