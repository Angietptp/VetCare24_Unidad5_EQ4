"""API de Emergencias (Etapa 10, CU-05), en SQLite y en PostgreSQL si hay."""

import pytest
from fastapi.testclient import TestClient

from tests.api_emergencias import ESCENARIOS, ejecutar, sembrar_mascotas
from tests.bd import BACKENDS, preparar, sembrar_basico
from vetcare24.api.main import create_app

RECEPCION = {"X-Rol": "recepcion"}
VET = {"X-Rol": "veterinario"}
CLINICO = {"X-Rol": "personal_clinico"}


def _cliente(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    sembrar_mascotas(url)
    return TestClient(create_app(url, preparar_esquema=False))


def _registrar(cliente, **cuerpo):
    respuesta = cliente.post("/emergencias", json={"motivo": "Convulsiones", **cuerpo},
                             headers=RECEPCION)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _error(respuesta):
    return respuesta.json()["error"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_20_escenarios_del_recorrido_coinciden(backend, tmp_path):
    resultados = ejecutar(_cliente(backend, tmp_path))
    assert len(resultados) == len(ESCENARIOS) == 20
    fallas = [(r.escenario.id, r.http_obtenido, r.resultado_obtenido)
              for r in resultados if not r.coincide]
    assert fallas == []
    codigos = sorted({r.http_obtenido for r in resultados})
    assert codigos == [200, 201, 400, 401, 403, 404, 409, 422]  # todo el contrato D-13


def test_los_ids_de_escenario_son_unicos():
    assert len({e.id for e in ESCENARIOS}) == len(ESCENARIOS)


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_responde_201_con_protocolo_y_notificacion(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cuerpo = _registrar(cliente, mascota_id="M1", motivo="  Golpe   de calor ")
    e = cuerpo["emergencia"]
    assert (e["estado"], e["mascota_id"], e["motivo"]) == ("IDENTIFICADA", "M1", "Golpe de calor")
    assert e["emergencia_id"].startswith("EMER-") and e["atendida_en"] is None
    assert e["identificada_en"].endswith(("Z", "+00:00"))
    assert (cuerpo["protocolo_activado"], cuerpo["notificacion"]) == (True, "notificado")
    (aviso,) = cliente.get("/avisos-veterinario", headers=VET).json()
    assert (aviso["emergencia_id"], aviso["motivo"]) == (e["emergencia_id"], "Golpe de calor")


@pytest.mark.parametrize("backend", BACKENDS)
def test_si_el_aviso_falla_responde_201_pendiente_de_notificar(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)

    def canal_caido(_emergencia):
        raise ConnectionError("sin canal")

    cliente.app.state.notificador.notificar = canal_caido
    cuerpo = _registrar(cliente)
    assert cuerpo["notificacion"] == "pendiente_de_notificar"
    guardada = cliente.get(f"/emergencias/{cuerpo['emergencia']['emergencia_id']}",
                           headers=VET)
    assert guardada.status_code == 200  # el registro se conserva


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_mensajes_de_error_hablan_de_la_emergencia(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    e = _registrar(cliente)["emergencia"]
    ruta = f"/emergencias/{e['emergencia_id']}/iniciar-atencion"
    cliente.post(ruta, headers=CLINICO)
    otra_vez = cliente.post(ruta, headers=CLINICO)
    assert _error(otra_vez)["mensaje"] == \
        "No se puede iniciar la atención de una emergencia que está en atención."
    assert _error(otra_vez)["motivos"] == ["iniciar_atencion desde EN_ATENCION"]
    assert _error(cliente.post("/emergencias", json={"motivo": "x"}, headers=VET))[
        "mensaje"] == "El rol Veterinario no tiene permiso para registrar emergencias."
    assert _error(cliente.get("/emergencias/EMER-NO", headers=VET))["mensaje"] == \
        "No se encontró la emergencia «EMER-NO»."
    assert _error(cliente.post("/emergencias", json={"motivo": ""}, headers=RECEPCION))[
        "mensaje"] == "Falta indicar el motivo."
    blanco = cliente.post("/emergencias", json={"motivo": "x", "datos_paciente": " "},
                          headers=RECEPCION)
    assert (blanco.status_code, _error(blanco)["codigo"]) == (422, "DATOS_PACIENTE_VACIOS")


@pytest.mark.parametrize("backend", BACKENDS)
def test_las_citas_conservan_sus_mensajes(backend, tmp_path):
    """La entidad nueva en TransicionInvalida no cambia los mensajes de las citas (K-04)."""
    cliente = _cliente(backend, tmp_path)
    cita = cliente.post("/citas", headers=RECEPCION, json={
        "propietario_id": "P1", "mascota_id": "M1", "fecha_solicitud": "2026-10-02",
        "autorizada": True, "servicios": [{"servicio_id": "S1", "cantidad": 1}]}).json()
    respuesta = cliente.post(f"/citas/{cita['cita_id']}/realizar", headers=VET)
    assert _error(respuesta)["mensaje"] == \
        "No se puede realizar una cita que está solicitada. Primero debe confirmarse."


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_tipos_son_estrictos(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    numero = cliente.post("/emergencias", json={"motivo": 5}, headers=RECEPCION)
    assert numero.status_code == 400
    assert _error(numero)["detalles"] == [
        {"campo": "motivo", "mensaje": "El campo «motivo» debe ser texto."}]
    extra = cliente.post("/emergencias", json={"motivo": "x", "cita_id": "C1"},
                         headers=RECEPCION)  # no se acepta un id de cita (R-06)
    assert extra.status_code == 400 and _error(extra)["detalles"][0]["campo"] == "cita_id"


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluacion_de_atencion_con_cita_confirmada(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    url = "/mascotas/M2/evaluaciones/atencion"
    assert cliente.get(url, headers=VET).json()["cumple"] is False
    cita = cliente.post("/citas", headers=RECEPCION, json={
        "propietario_id": "P1", "mascota_id": "M2", "fecha_solicitud": "2026-10-02",
        "autorizada": True, "servicios": [{"servicio_id": "S1", "cantidad": 1}]}).json()
    cliente.post(f"/citas/{cita['cita_id']}/confirmar", headers=RECEPCION)
    assert cliente.get(url, headers=VET).json() == {
        "regla": "atencion", "cumple": True, "motivos": []}
    assert cliente.get("/mascotas/NO/evaluaciones/atencion", headers=VET).status_code == 404


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_por_mascota_y_permisos_de_consulta(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    _registrar(cliente, mascota_id="M1")
    _registrar(cliente, mascota_id="M2")
    por_mascota = cliente.get("/emergencias?mascota_id=M2", headers=CLINICO).json()
    assert [e["mascota_id"] for e in por_mascota] == ["M2"]
    for rol in ("recepcion", "veterinario", "personal_clinico", "responsable"):
        assert cliente.get("/emergencias", headers={"X-Rol": rol}).status_code == 200
        assert cliente.get("/avisos-veterinario", headers={"X-Rol": rol}).status_code == 200
    assert cliente.get("/emergencias?mascota_id=NO", headers=CLINICO).status_code == 404
    assert cliente.get("/avisos-veterinario").status_code == 401


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_eventos_de_emergencia_conviven_con_los_de_citas(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita = cliente.post("/citas", headers=RECEPCION, json={
        "propietario_id": "P1", "mascota_id": "M1", "fecha_solicitud": "2026-10-02",
        "autorizada": True, "servicios": [{"servicio_id": "S1", "cantidad": 1}]}).json()
    cliente.post(f"/citas/{cita['cita_id']}/confirmar", headers=RECEPCION)
    e = _registrar(cliente)["emergencia"]
    eventos = cliente.get("/eventos", headers=VET).json()
    assert [(x["evento"], x["agregado_tipo"], x["cita_id"]) for x in eventos] == [
        ("CitaAgendada", "Cita", cita["cita_id"]),
        ("EmergenciaIdentificada", "Emergencia", None)]
    assert eventos[1]["payload"]["emergencia_id"] == e["emergencia_id"]


def test_el_contrato_openapi_documenta_las_emergencias(tmp_path):
    contrato = TestClient(create_app(f"sqlite:///{tmp_path / 'a.db'}")).get(
        "/openapi.json").json()
    rutas = contrato["paths"]
    assert {"post", "get"} <= set(rutas["/emergencias"])
    assert {"post"} <= set(rutas["/emergencias/{emergencia_id}/iniciar-atencion"])
    assert {"get"} <= set(rutas["/emergencias/{emergencia_id}"])
    assert {"get"} <= set(rutas["/mascotas/{mascota_id}/evaluaciones/atencion"])
    assert {"get"} <= set(rutas["/avisos-veterinario"])
    registrar = rutas["/emergencias"]["post"]
    assert {"201", "400", "401", "403", "404", "409", "422"} <= set(registrar["responses"])
    entrada = contrato["components"]["schemas"]["EmergenciaIn"]
    assert entrada["required"] == ["motivo"]  # sin cita y con mascota opcional
    assert "CU-05" in contrato["info"]["description"]
