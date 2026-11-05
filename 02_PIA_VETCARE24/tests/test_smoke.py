"""Pruebas de humo de la Etapa 1: el esqueleto arranca y el entorno está bien armado."""

from fastapi.testclient import TestClient

from vetcare24.api.main import create_app
from vetcare24.infrastructure.config import load_settings


def test_health_responde_ok():
    client = TestClient(create_app())
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_openapi_esta_publicado():
    client = TestClient(create_app())
    contrato = client.get("/openapi.json").json()
    assert contrato["info"]["title"] == "VetCare 24 API"
    assert "/health" in contrato["paths"]


def test_configuracion_lee_variables_de_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@h:5432/z")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    ajustes = load_settings()
    assert ajustes.database_url.endswith("/z")
    assert ajustes.data_dir == tmp_path


def test_csv_del_alumno_estan_presentes():
    ajustes = load_settings()
    esperados = {
        "actores.csv", "catalogo.csv", "operaciones.csv",
        "detalle_operaciones.csv", "casos_prueba.csv", "transiciones_prueba.csv",
    }
    assert esperados <= {p.name for p in ajustes.data_dir.glob("*.csv")}
