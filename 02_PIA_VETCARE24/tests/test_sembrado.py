"""Carga de los CSV a la base y recorrido completo con los 60 datos reales (Etapa 7)."""

import contextlib
import io
import os

import pytest

from tests.bd import BACKENDS, armar, preparar
from tests.oraculo import confirmar_en_secuencia
from vetcare24.application.comandos import SolicitarCita
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import YaExiste
from vetcare24.domain.cita import EstadoCita
from vetcare24.domain.errors import PrecondicionNoCumplida
from vetcare24.domain.eventos import CitaAgendada
from vetcare24.infrastructure import sembrado
from vetcare24.infrastructure.adaptador_paquete import construir_dominio
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import cargar_paquete
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql


def _sembrada(backend, tmp_path):
    url = preparar(backend, tmp_path)
    paquete = cargar_paquete(load_settings().data_dir)
    datos = construir_dominio(paquete)
    with UnidadDeTrabajoSql(url) as uow:
        sembrado.sembrar(uow, datos)
    return url, paquete, datos


@pytest.mark.parametrize("backend", BACKENDS)
def test_sembrar_guarda_todo_tal_cual(backend, tmp_path):
    url, _, _ = _sembrada(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        assert len(uow.servicios.todos()) == 20
        assert len(uow.propietarios.todos()) == 40
        assert uow.citas.contar() == 60
        assert sum(not c.lineas for c in uow.citas.listar()) == 2  # se conservan las inválidas
        assert uow.citas.demanda_ocupada() == {}  # nada confirmado todavía


@pytest.mark.parametrize("backend", BACKENDS)
def test_sembrar_incluye_los_esquemas_de_vacunacion_de_ejemplo(backend, tmp_path):
    url, _, _ = _sembrada(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        esquemas = uow.esquemas.todos()
    assert sorted(esquemas) == ["vac-anual", "vac-refuerzo-30d", "vac-sin-validar"]
    assert [esquemas[c].validado for c in sorted(esquemas)] == [True, True, False]


@pytest.mark.parametrize("backend", BACKENDS)
def test_sembrar_dos_veces_se_rechaza(backend, tmp_path):
    url, _, datos = _sembrada(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        with pytest.raises(YaExiste):
            sembrado.sembrar(uow, datos)


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_datos_leidos_de_la_base_coinciden_con_el_dominio_original(backend, tmp_path):
    url, _, datos = _sembrada(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        servicios = uow.servicios.todos()
        for cita_id, original in datos.citas.items():
            leida = uow.citas.obtener(cita_id)
            assert leida.total(servicios) == original.total(datos.servicios), cita_id
            assert leida.lineas == original.lineas and leida.estado is original.estado


@pytest.mark.parametrize("backend", BACKENDS)
def test_confirmar_las_60_citas_con_los_servicios_coincide_con_el_oraculo(backend, tmp_path):
    url, paquete, _ = _sembrada(backend, tmp_path)
    entorno = armar(url)
    obtenido = {}
    for cita_id in paquete.operaciones:
        try:
            entorno.citas.confirmar(Rol.RECEPCION, cita_id)
            obtenido[cita_id] = ()
        except PrecondicionNoCumplida as error:
            obtenido[cita_id] = error.motivos
    esperado = confirmar_en_secuencia(paquete)
    assert obtenido == esperado
    confirmadas = [c for c, motivos in esperado.items() if not motivos]
    assert len(confirmadas) == 38
    with entorno.fabrica() as uow:
        assert [c.cita_id for c in uow.citas.listar(estado=EstadoCita.CONFIRMADA)] == confirmadas
        guardados = uow.eventos.todos()
    assert [g["cita_id"] for g in guardados] == confirmadas  # un evento por cita, en orden
    assert len(entorno.eventos.de_tipo(CitaAgendada)) == 38


@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitar_una_cita_nueva_sobre_los_datos_cargados(backend, tmp_path):
    url, paquete, datos = _sembrada(backend, tmp_path)
    entorno = armar(url)
    actor = next(a for a in paquete.actores.values() if a.activo)
    fecha = paquete.operaciones["VET-O001"].fecha_solicitud
    cita = entorno.citas.solicitar(Rol.RECEPCION, SolicitarCita(
        propietario_id=actor.actor_id, mascota_id=f"{actor.actor_id}-MASCOTA",
        servicios=(("VET-P001", 1),), fecha_solicitud=fecha, autorizada=True))
    assert cita.estado is EstadoCita.SOLICITADA
    with entorno.fabrica() as uow:
        assert uow.citas.contar() == 61


def test_el_comando_de_sembrado_carga_una_vez_y_luego_avisa(tmp_path):
    previo = {k: os.environ.get(k) for k in ("DATABASE_URL", "DATA_DIR")}
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'sembrado.db'}"
    os.environ["DATA_DIR"] = str(load_settings().data_dir)
    try:
        primera, segunda = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(primera):
            sembrado.main()
        with contextlib.redirect_stdout(segunda):
            sembrado.main()
    finally:
        for clave, valor in previo.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor
    assert "20 servicios, 40 propietarios, 40 mascotas, 60 citas" in primera.getvalue()
    assert "ya tenía datos" in segunda.getvalue()
