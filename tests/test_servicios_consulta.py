"""Evaluaciones, totales y eventos de consulta (Etapa 8), en SQLite y en PostgreSQL."""

from datetime import date

import pytest

from tests.bd import BACKENDS, armar, preparar, sembrar_basico
from vetcare24.application.comandos import SolicitarCita
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import AccesoDenegado, NoEncontrado
from vetcare24.application.servicios import ReglaEvaluable
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql


def _entorno(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    return armar(url)


def _cita(entorno, servicios=(("S1", 2), ("S2", 1))):
    return entorno.citas.solicitar(Rol.RECEPCION, SolicitarCita(
        propietario_id="P1", mascota_id="M1", servicios=tuple(servicios),
        fecha_solicitud=date(2026, 10, 2), autorizada=True))


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluar_procesamiento_y_beneficio(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _cita(entorno)
    procesable = entorno.citas.evaluar(Rol.RECEPCION, cita.cita_id, ReglaEvaluable.PROCESAMIENTO)
    assert procesable.cumple and procesable.motivos == ()
    beneficio = entorno.citas.evaluar(Rol.RESPONSABLE, cita.cita_id, ReglaEvaluable.BENEFICIO)
    assert not beneficio.cumple
    assert beneficio.motivos == ("NO_PREFERENTE", "TOTAL_INSUFICIENTE")  # 700 < 1500


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluar_beneficio_de_un_preferente_con_total_suficiente(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    with UnidadDeTrabajoSql(entorno.url) as uow:
        uow.propietarios.agregar(Propietario("P2", "Luis", preferente=True))
        uow.commit()
    with UnidadDeTrabajoSql(entorno.url) as uow:
        uow.mascotas.agregar(
            Mascota(mascota_id="M2", propietario_id="P2", nombre="Max", especie="Perro"))
        uow.commit()
    cita = entorno.citas.solicitar(Rol.RECEPCION, SolicitarCita(
        propietario_id="P2", mascota_id="M2", servicios=(("S1", 5),),
        fecha_solicitud=date(2026, 10, 2), autorizada=True))  # 5 x 300 = 1500 exacto
    assert entorno.citas.evaluar(Rol.RECEPCION, cita.cita_id, ReglaEvaluable.BENEFICIO).cumple


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluar_exige_permiso_y_cita_existente(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _cita(entorno)
    with pytest.raises(AccesoDenegado):
        entorno.citas.evaluar(Rol.PERSONAL_CLINICO, cita.cita_id, ReglaEvaluable.BENEFICIO)
    with pytest.raises(NoEncontrado):
        entorno.citas.evaluar(Rol.RECEPCION, "NO-EXISTE", ReglaEvaluable.BENEFICIO)


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluar_no_cambia_nada(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _cita(entorno)
    entorno.citas.evaluar(Rol.RECEPCION, cita.cita_id, ReglaEvaluable.PROCESAMIENTO)
    assert entorno.citas.obtener(Rol.RECEPCION, cita.cita_id).estado.value == "SOLICITADA"
    assert entorno.eventos.registrados == ()


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_catalogo_de_lectura_permite_calcular_importes(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _cita(entorno)                    # 2 x 300 + 1 x 100 = 700
    catalogo = entorno.citas.catalogo()
    assert sorted(catalogo) == ["S1", "S2", "S3"]
    assert cita.total(catalogo) == Money.mxn("700")


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_eventos_guardados(backend, tmp_path):
    entorno = _entorno(backend, tmp_path)
    cita = _cita(entorno)
    assert entorno.citas.listar_eventos(Rol.RESPONSABLE) == []
    entorno.citas.confirmar(Rol.RECEPCION, cita.cita_id)
    (evento,) = entorno.citas.listar_eventos(Rol.RESPONSABLE)
    assert (evento["evento"], evento["cita_id"]) == ("CitaAgendada", cita.cita_id)
    with pytest.raises(AccesoDenegado):
        entorno.citas.listar_eventos(Rol.PERSONAL_CLINICO)
