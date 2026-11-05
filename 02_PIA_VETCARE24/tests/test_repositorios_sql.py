"""Repositorios y unidad de trabajo (Etapa 7), en SQLite y en PostgreSQL si hay."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from tests.bd import BACKENDS, ERRORES_DE_BD, preparar, sembrar_basico
from vetcare24.application.errores import NoEncontrado
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.eventos import CitaAgendada
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

HORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _cita(cita_id="C1", lineas=(("S1", 2),), estado=EstadoCita.SOLICITADA, propietario="P1"):
    return Cita(
        cita_id=cita_id, propietario_id=propietario, mascota_id="M1",
        lineas=[ServicioSolicitado(s, q) for s, q in lineas],
        fecha_solicitud=date(2026, 10, 2), estado=estado, autorizada=True,
        promocion_activa=True, referencia="REF-1",
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_servicios_se_guardan_con_el_importe_exacto(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        uow.servicios.agregar(ServicioVeterinario("S1", "Consulta", Money.mxn("313.05"), 7))
        uow.servicios.agregar(
            ServicioVeterinario("S2", "Gratis", Money.cero(), 0, habilitado=False))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        s1 = uow.servicios.obtener("S1")
        assert (s1.descripcion, s1.precio, s1.capacidad, s1.habilitado) == (
            "Consulta", Money.mxn("313.05"), 7, True)
        assert uow.servicios.obtener("S2").habilitado is False
        assert uow.servicios.obtener("S9") is None
        assert list(uow.servicios.todos()) == ["S1", "S2"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_propietarios_se_guardan_y_listan(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        uow.propietarios.agregar(Propietario("P2", "Luis", activo=False, preferente=True))
        uow.propietarios.agregar(Propietario("P1", "Ana"))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        assert uow.propietarios.obtener("P2") == Propietario("P2", "Luis", False, True)
        assert [p.propietario_id for p in uow.propietarios.todos()] == ["P1", "P2"]
        assert uow.propietarios.obtener("P9") is None


@pytest.mark.parametrize("backend", BACKENDS)
def test_mascotas_conservan_peso_alergias_y_acentos(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    mascota = Mascota(
        mascota_id="M2", propietario_id="P1", nombre="Luna", especie="Gato", raza="Siamés",
        sexo="H", fecha_nacimiento=date(2020, 5, 17), peso_kg=Decimal("4.50"),
        alergias=["Penicilina", "Ácaros"],
    )
    with UnidadDeTrabajoSql(url) as uow:
        uow.mascotas.agregar(mascota)
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        leida = uow.mascotas.obtener("M2")
        assert (leida.raza, leida.sexo, leida.fecha_nacimiento) == (
            "Siamés", "H", date(2020, 5, 17))
        assert leida.peso_kg == Decimal("4.50") and leida.alergias == ("Penicilina", "Ácaros")
        assert [m.mascota_id for m in uow.mascotas.de_propietario("P1")] == ["M1", "M2"]
        assert uow.mascotas.obtener("M1").peso_kg is None
        assert uow.mascotas.obtener("M9") is None


@pytest.mark.parametrize("backend", BACKENDS)
def test_la_base_exige_propietario_existente_para_una_mascota(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with pytest.raises(ERRORES_DE_BD):
        with UnidadDeTrabajoSql(url) as uow:
            uow.mascotas.agregar(
                Mascota(mascota_id="M1", propietario_id="NO-EXISTE", nombre="x", especie="y"))


@pytest.mark.parametrize("backend", BACKENDS)
def test_cita_se_guarda_y_se_reconstruye_igual(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.citas.agregar(_cita(lineas=(("S1", 2), ("S2", 1), ("S1", 3))))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        cita = uow.citas.obtener("C1")
        assert cita.estado is EstadoCita.SOLICITADA
        assert [(ln.servicio_id, ln.cantidad) for ln in cita.lineas] == [
            ("S1", 2), ("S2", 1), ("S1", 3)]  # conserva el orden y los repetidos
        assert (cita.propietario_id, cita.mascota_id, cita.fecha_solicitud) == (
            "P1", "M1", date(2026, 10, 2))
        assert (cita.autorizada, cita.promocion_activa, cita.referencia) == (True, True, "REF-1")
        assert uow.citas.obtener("C9") is None and uow.citas.contar() == 1


@pytest.mark.parametrize("backend", BACKENDS)
def test_guardar_actualiza_estado_y_lineas(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.citas.agregar(_cita())
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        cita = uow.citas.obtener("C1")
        cita._establecer_estado(EstadoCita.CONFIRMADA)
        cita._reemplazar_lineas((ServicioSolicitado("S2", 4),))
        uow.citas.guardar(cita)
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        cita = uow.citas.obtener("C1")
        assert cita.estado is EstadoCita.CONFIRMADA
        assert cita.demanda_por_servicio() == {"S2": 4}


@pytest.mark.parametrize("backend", BACKENDS)
def test_guardar_una_cita_inexistente_falla(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        with pytest.raises(NoEncontrado):
            uow.citas.guardar(_cita("C9"))


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_filtra_por_estado_y_propietario(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.propietarios.agregar(Propietario("P2", "Luis"))
        uow.mascotas.agregar(
            Mascota(mascota_id="M2", propietario_id="P2", nombre="Max", especie="Perro"))
        uow.citas.agregar(_cita("C1"))
        uow.citas.agregar(_cita("C2", estado=EstadoCita.CONFIRMADA))
        otra = _cita("C3", propietario="P2")
        uow.citas.agregar(Cita(
            cita_id="C3", propietario_id="P2", mascota_id="M2", lineas=otra.lineas,
            fecha_solicitud=otra.fecha_solicitud, estado=EstadoCita.CANCELADA, autorizada=False))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:

        def ids(citas):
            return [c.cita_id for c in citas]

        assert ids(uow.citas.listar()) == ["C1", "C2", "C3"]
        assert ids(uow.citas.listar(estado=EstadoCita.CONFIRMADA)) == ["C2"]
        assert ids(uow.citas.listar(propietario_id="P2")) == ["C3"]
        assert ids(uow.citas.listar(estado=EstadoCita.SOLICITADA, propietario_id="P2")) == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_demanda_ocupada_cuenta_solo_confirmadas_y_realizadas(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    with UnidadDeTrabajoSql(url) as uow:
        uow.citas.agregar(_cita("C1", lineas=(("S1", 2),), estado=EstadoCita.CONFIRMADA))
        uow.citas.agregar(_cita("C2", lineas=(("S1", 1), ("S2", 3)), estado=EstadoCita.REALIZADA))
        uow.citas.agregar(_cita("C3", lineas=(("S1", 9),), estado=EstadoCita.SOLICITADA))
        uow.citas.agregar(_cita("C4", lineas=(("S1", 9),), estado=EstadoCita.CANCELADA))
        uow.citas.agregar(_cita("C5", lineas=(("S1", 1), ("S1", 1)), estado=EstadoCita.CONFIRMADA))
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        assert uow.citas.demanda_ocupada() == {"S1": 5, "S2": 3}


@pytest.mark.parametrize("backend", BACKENDS)
def test_eventos_se_guardan_en_orden_con_su_detalle(backend, tmp_path):
    url = preparar(backend, tmp_path)
    evento = CitaAgendada(ocurrido_en=HORA, cita_id="C1", propietario_id="P1", mascota_id="M1",
                          servicios=(("S1", 2),), total=Money.mxn("600"))
    with UnidadDeTrabajoSql(url) as uow:
        uow.eventos.agregar(evento)
        uow.eventos.agregar(evento)
        uow.commit()
    with UnidadDeTrabajoSql(url) as uow:
        guardados = uow.eventos.todos()
    assert [g["secuencia"] for g in guardados] == sorted(g["secuencia"] for g in guardados)
    assert len(guardados) == 2
    primero = guardados[0]
    assert (primero["evento"], primero["cita_id"]) == ("CitaAgendada", "C1")
    assert primero["ocurrido_en"] == "2026-10-31T12:00:00+00:00"
    assert primero["payload"]["total"] == "600.00"
    assert primero["payload"]["servicios"] == [["S1", 2]]


@pytest.mark.parametrize("backend", BACKENDS)
def test_sin_commit_no_se_guarda_nada(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with UnidadDeTrabajoSql(url) as uow:
        uow.propietarios.agregar(Propietario("P1", "Ana"))
    with UnidadDeTrabajoSql(url) as uow:
        assert uow.propietarios.todos() == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_un_error_dentro_de_la_unidad_deshace_todo(backend, tmp_path):
    url = preparar(backend, tmp_path)
    with pytest.raises(RuntimeError):
        with UnidadDeTrabajoSql(url) as uow:
            uow.propietarios.agregar(Propietario("P1", "Ana"))
            raise RuntimeError("falla a media operación")
    with UnidadDeTrabajoSql(url) as uow:
        assert uow.propietarios.todos() == []


def test_la_unidad_debe_estar_abierta_para_hacer_commit(tmp_path):
    unidad = UnidadDeTrabajoSql(f"sqlite:///{tmp_path / 'x.db'}")
    with pytest.raises(RuntimeError):
        unidad.commit()
    unidad.__exit__(None, None, None)  # cerrar algo que no se abrió no falla
