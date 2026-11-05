"""Conexión y esquema (Etapa 7). Cada prueba corre en SQLite y en PostgreSQL si hay."""

import pytest

from tests.bd import BACKENDS, ERRORES_DE_BD, preparar
from vetcare24.infrastructure.base_de_datos import Dialecto, conectar
from vetcare24.infrastructure.esquema import (
    TABLAS,
    EsquemaDesactualizado,
    crear_esquema,
    eliminar_esquema,
)


def test_dialecto_adapta_los_marcadores():
    assert Dialecto("sqlite").adaptar("SELECT ? , ?") == "SELECT ? , ?"
    assert Dialecto("postgresql").adaptar("SELECT ? , ?") == "SELECT %s , %s"
    assert "AUTOINCREMENT" in Dialecto("sqlite").llave_serie
    assert "BIGSERIAL" in Dialecto("postgresql").llave_serie
    assert Dialecto("postgresql").es_postgres and not Dialecto("sqlite").es_postgres


def test_url_no_soportada():
    with pytest.raises(ValueError, match="no soportada"):
        conectar("mysql://usuario@host/base")


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_esquema_crea_todas_las_tablas_y_es_repetible(backend, tmp_path):
    url = preparar(backend, tmp_path)
    con = conectar(url)
    crear_esquema(con)  # una segunda vez no debe fallar
    for tabla in TABLAS:
        assert con.consultar(f"SELECT COUNT(*) FROM {tabla}")[0][0] == 0
    con.cerrar()


@pytest.mark.parametrize("backend", BACKENDS)
def test_eliminar_esquema_borra_las_tablas(backend, tmp_path):
    url = preparar(backend, tmp_path)
    con = conectar(url)
    eliminar_esquema(con)
    with pytest.raises(ERRORES_DE_BD):
        con.consultar("SELECT COUNT(*) FROM citas")
    con.rollback()
    con.cerrar()


@pytest.mark.parametrize("backend", BACKENDS)
def test_las_restricciones_de_la_base_rechazan_datos_imposibles(backend, tmp_path):
    url = preparar(backend, tmp_path)
    invalidos = [
        "INSERT INTO servicios VALUES ('S', 'x', -1, 1, 1)",             # precio negativo
        "INSERT INTO servicios VALUES ('S', 'x', 1, -1, 1)",             # capacidad negativa
        "INSERT INTO servicios VALUES ('S', 'x', 1, 1, 2)",              # booleano inválido
        "INSERT INTO propietarios VALUES ('P', 'x', 5, 0)",              # booleano inválido
        "INSERT INTO mascotas (mascota_id, propietario_id, nombre, especie, alergias_json)"
        " VALUES ('M', 'NO-EXISTE', 'x', 'y', '[]')",                    # propietario inexistente
    ]
    for sentencia in invalidos:
        con = conectar(url)
        with pytest.raises(ERRORES_DE_BD):
            con.ejecutar(sentencia)
        con.rollback()
        con.cerrar()


@pytest.mark.parametrize("backend", BACKENDS)
def test_rollback_deshace_y_commit_conserva(backend, tmp_path):
    url = preparar(backend, tmp_path)
    con = conectar(url)
    con.ejecutar("INSERT INTO propietarios VALUES ('P1', 'Ana', 1, 0)")
    con.rollback()
    assert con.consultar("SELECT COUNT(*) FROM propietarios")[0][0] == 0
    con.ejecutar("INSERT INTO propietarios VALUES ('P1', 'Ana', 1, 0)")
    con.commit()
    con.rollback()
    assert con.consultar("SELECT nombre FROM propietarios") == [("Ana",)]
    con.cerrar()


def test_una_base_de_la_version_anterior_se_avisa_con_un_mensaje_claro(tmp_path):
    con = conectar(f"sqlite:///{tmp_path / 'vieja.db'}")
    con.ejecutar(
        "CREATE TABLE eventos_dominio (secuencia INTEGER PRIMARY KEY AUTOINCREMENT,"
        " evento TEXT, cita_id TEXT, ocurrido_en TEXT, payload_json TEXT)")
    con.commit()
    with pytest.raises(EsquemaDesactualizado, match="docker compose down -v"):
        crear_esquema(con)
    con.cerrar()



@pytest.mark.parametrize("backend", BACKENDS)
def test_una_base_de_la_etapa_9_recibe_la_tabla_de_emergencias_sin_reiniciar(
        backend, tmp_path):
    """N-10: la Etapa 10 solo AGREGA una tabla; crear_esquema la crea y conserva los datos."""
    url = preparar(backend, tmp_path)
    con = conectar(url)
    con.ejecutar("DROP TABLE emergencias")  # así era la base de la Etapa 9
    con.ejecutar("INSERT INTO propietarios VALUES ('P1', 'Ana', 1, 0)")
    con.commit()
    crear_esquema(con)
    assert con.consultar("SELECT COUNT(*) FROM emergencias")[0][0] == 0
    assert con.consultar("SELECT COUNT(*) FROM propietarios")[0][0] == 1
    con.cerrar()


@pytest.mark.parametrize("backend", BACKENDS)
def test_eliminar_esquema_no_se_bloquea_por_una_tabla_ajena_que_apunta_a_mascotas(
        backend, tmp_path):
    url = preparar(backend, tmp_path)
    con = conectar(url)
    con.ejecutar("DROP TABLE IF EXISTS tabla_ajena")
    con.ejecutar("CREATE TABLE tabla_ajena (m TEXT REFERENCES mascotas (mascota_id))")
    con.commit()
    eliminar_esquema(con)
    with pytest.raises(ERRORES_DE_BD):
        con.consultar("SELECT COUNT(*) FROM mascotas")
    con.rollback()
    con.ejecutar("DROP TABLE IF EXISTS tabla_ajena")
    con.commit()
    con.cerrar()
