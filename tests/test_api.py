"""API REST (Etapa 7): CU-01 de punta a punta con el cliente HTTP de pruebas.

Cada prueba corre contra SQLite y, dentro de Docker Compose / CI, también contra PostgreSQL
(`tests/bd.py`). Se valida el contrato de D-13: 200/201 éxito, 400 solicitud mal formada,
401 falta rol, 403 sin permiso, 404 no existe, 409 transición inválida o capacidad
insuficiente, 422 regla de negocio no cumplida.
"""

import pytest
from fastapi.testclient import TestClient

from tests.bd import BACKENDS, preparar, sembrar_basico, sembrar_esquemas
from vetcare24.api.main import create_app
from vetcare24.domain.eventos import CitaAgendada

RECEPCION = {"X-Rol": "recepcion"}
VETERINARIO = {"X-Rol": "veterinario"}
RESPONSABLE = {"X-Rol": "responsable"}


def _cliente(backend, tmp_path, capacidad=5, esquemas=False):
    url = preparar(backend, tmp_path)
    sembrar_basico(url, capacidad)
    if esquemas:
        sembrar_esquemas(url)
    return TestClient(create_app(url, preparar_esquema=False))


def _cita(servicios=(("S1", 3),), **extra):
    cuerpo = {
        "propietario_id": "P1", "mascota_id": "M1", "fecha_solicitud": "2026-10-02",
        "autorizada": True,
        "servicios": [{"servicio_id": s, "cantidad": n} for s, n in servicios],
    }
    return {**cuerpo, **extra}


def _solicitar(cliente, servicios=(("S1", 3),), **extra):
    respuesta = cliente.post("/citas", json=_cita(servicios, **extra), headers=RECEPCION)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _codigo(respuesta):
    return respuesta.json()["error"]["codigo"]


# --- rol ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_sin_rol_responde_401_y_con_rol_desconocido_400(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    sin_rol = cliente.get("/servicios")
    assert sin_rol.status_code == 401 and _codigo(sin_rol) == "ROL_REQUERIDO"
    assert "encabezado X-Rol" in sin_rol.json()["error"]["mensaje"]
    desconocido = cliente.get("/servicios", headers={"X-Rol": "jefe"})
    assert desconocido.status_code == 400 and _codigo(desconocido) == "ROL_DESCONOCIDO"


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_rol_no_distingue_mayusculas(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    assert cliente.get("/servicios", headers={"X-Rol": "RECEPCION"}).status_code == 200


# --- catálogo y registro ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_el_catalogo_se_publica_con_importes_en_texto(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    respuesta = cliente.get("/servicios", headers=RESPONSABLE)
    assert respuesta.status_code == 200
    por_id = {s["servicio_id"]: s for s in respuesta.json()}
    assert set(por_id) == {"S1", "S2", "S3"}
    assert por_id["S1"]["precio_mxn"] == "300.00" and por_id["S3"]["habilitado"] is False


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_y_consultar_propietario_y_mascota(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    creado = cliente.post("/propietarios", json={"nombre": "Luis", "preferente": True},
                          headers=RECEPCION)
    assert creado.status_code == 201
    propietario_id = creado.json()["propietario_id"]
    assert creado.json()["preferente"] is True
    mascota = cliente.post("/mascotas", headers=RECEPCION, json={
        "propietario_id": propietario_id, "nombre": "Michi", "especie": "Gato",
        "peso_kg": "4.5", "alergias": ["polen"]})
    assert mascota.status_code == 201
    consulta = cliente.get(f"/mascotas/{mascota.json()['mascota_id']}", headers=VETERINARIO)
    assert consulta.status_code == 200 and consulta.json()["alergias"] == ["polen"]
    assert cliente.get(f"/propietarios/{propietario_id}",
                       headers=RESPONSABLE).json()["nombre"] == "Luis"


@pytest.mark.parametrize("backend", BACKENDS)
def test_registro_duplicado_409_y_referencia_rota_404(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    repetido = cliente.post("/propietarios", json={"nombre": "Ana", "propietario_id": "P1"},
                            headers=RECEPCION)
    assert repetido.status_code == 409 and _codigo(repetido) == "YA_EXISTE"
    huerfana = cliente.post("/mascotas", headers=RECEPCION, json={
        "propietario_id": "P9", "nombre": "Rex", "especie": "Perro"})
    assert huerfana.status_code == 404 and _codigo(huerfana) == "NO_ENCONTRADO"
    assert cliente.get("/mascotas/NO-EXISTE", headers=RECEPCION).status_code == 404


# --- ciclo de la cita ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_ciclo_completo_solicitar_confirmar_realizar(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita = _solicitar(cliente, (("S1", 3), ("S2", 1)))
    assert cita["estado"] == "SOLICITADA" and cita["total_mxn"] == "1000.00"
    cita_id = cita["cita_id"]
    confirmada = cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    assert confirmada.status_code == 200 and confirmada.json()["estado"] == "CONFIRMADA"
    realizada = cliente.post(f"/citas/{cita_id}/realizar", headers=VETERINARIO)
    assert realizada.status_code == 200 and realizada.json()["estado"] == "REALIZADA"
    consulta = cliente.get(f"/citas/{cita_id}", headers=RESPONSABLE)
    assert consulta.status_code == 200 and consulta.json()["estado"] == "REALIZADA"


@pytest.mark.parametrize("backend", BACKENDS)
def test_confirmar_publica_el_evento_de_dominio(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]
    cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    (registrado,) = cliente.app.state.eventos.de_tipo(CitaAgendada)
    assert registrado.evento.total.monto == 900


@pytest.mark.parametrize("backend", BACKENDS)
def test_cancelar_y_modificar(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]
    modificada = cliente.put(f"/citas/{cita_id}/servicios", headers=RECEPCION,
                             json={"servicios": [{"servicio_id": "S2", "cantidad": 2}]})
    assert modificada.status_code == 200 and modificada.json()["total_mxn"] == "200.00"
    cancelada = cliente.post(f"/citas/{cita_id}/cancelar", headers=RECEPCION)
    assert cancelada.status_code == 200 and cancelada.json()["estado"] == "CANCELADA"


@pytest.mark.parametrize("backend", BACKENDS)
def test_listar_citas_con_filtros(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    primera, segunda = _solicitar(cliente)["cita_id"], _solicitar(cliente)["cita_id"]
    cliente.post(f"/citas/{segunda}/confirmar", headers=RECEPCION)
    todas = cliente.get("/citas", headers=RESPONSABLE).json()
    assert {c["cita_id"] for c in todas} == {primera, segunda}
    confirmadas = cliente.get("/citas", params={"estado": "CONFIRMADA"}, headers=RESPONSABLE)
    assert [c["cita_id"] for c in confirmadas.json()] == [segunda]
    assert cliente.get("/citas", params={"propietario_id": "P9"},
                       headers=RESPONSABLE).json() == []


# --- errores ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_cada_rol_solo_hace_lo_suyo_403(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]
    cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    realizar_recepcion = cliente.post(f"/citas/{cita_id}/realizar", headers=RECEPCION)
    assert realizar_recepcion.status_code == 403
    assert realizar_recepcion.json()["error"]["mensaje"] == (
        "El rol Recepción no tiene permiso para realizar citas.")
    assert _codigo(realizar_recepcion) == "ACCESO_DENEGADO"
    solicitar_vet = cliente.post("/citas", json=_cita(), headers=VETERINARIO)
    assert solicitar_vet.status_code == 403
    confirmar_resp = cliente.post(f"/citas/{cita_id}/confirmar", headers=RESPONSABLE)
    assert confirmar_resp.status_code == 403


@pytest.mark.parametrize("backend", BACKENDS)
def test_cita_inexistente_404_y_transicion_invalida_409(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    assert cliente.get("/citas/NO-EXISTE", headers=RECEPCION).status_code == 404
    assert cliente.post("/citas/NO-EXISTE/confirmar", headers=RECEPCION).status_code == 404
    cita_id = _solicitar(cliente)["cita_id"]
    antes_de_confirmar = cliente.post(f"/citas/{cita_id}/realizar", headers=VETERINARIO)
    assert antes_de_confirmar.status_code == 409
    assert _codigo(antes_de_confirmar) == "TRANSICION_INVALIDA"
    assert antes_de_confirmar.json()["error"]["mensaje"] == (
        "No se puede realizar una cita que está solicitada. Primero debe confirmarse.")
    cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    repetida = cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    assert repetida.status_code == 409 and _codigo(repetida) == "TRANSICION_INVALIDA"


@pytest.mark.parametrize("backend", BACKENDS)
def test_capacidad_insuficiente_409_y_cancelar_la_libera(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, capacidad=5)
    c1, c2 = _solicitar(cliente)["cita_id"], _solicitar(cliente)["cita_id"]
    assert cliente.post(f"/citas/{c1}/confirmar", headers=RECEPCION).status_code == 200
    sin_cupo = cliente.post(f"/citas/{c2}/confirmar", headers=RECEPCION)
    assert sin_cupo.status_code == 409 and _codigo(sin_cupo) == "CAPACIDAD_INSUFICIENTE"
    assert sin_cupo.json()["error"]["mensaje"] == (
        "No se puede confirmar la cita: no hay capacidad suficiente para el servicio S1.")
    assert cliente.get(f"/citas/{c2}", headers=RECEPCION).json()["estado"] == "SOLICITADA"
    cliente.post(f"/citas/{c1}/cancelar", headers=RECEPCION)
    assert cliente.post(f"/citas/{c2}/confirmar", headers=RECEPCION).status_code == 200


@pytest.mark.parametrize("backend", BACKENDS)
def test_reglas_de_negocio_no_cumplidas_422(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    for servicios, codigo in [((), "DETALLE_VACIO"), ((("S3", 1),), "SERVICIO_DESHABILITADO"),
                              ((("S9", 1),), "SERVICIO_INEXISTENTE")]:
        respuesta = cliente.post("/citas", json=_cita(servicios), headers=RECEPCION)
        assert respuesta.status_code == 422 and _codigo(respuesta) == codigo
    assert cliente.get("/citas", headers=RESPONSABLE).json() == []  # no se guardó nada


@pytest.mark.parametrize("backend", BACKENDS)
def test_solicitud_mal_formada_400_con_detalle_por_campo(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    mala = _cita()
    mala["servicios"][0]["cantidad"] = "muchas"
    respuesta = cliente.post("/citas", json=mala, headers=RECEPCION)
    assert respuesta.status_code == 400 and _codigo(respuesta) == "SOLICITUD_INVALIDA"
    campos = [d["campo"] for d in respuesta.json()["error"]["detalles"]]
    assert any("cantidad" in campo for campo in campos)
    mensajes = [d["mensaje"] for d in respuesta.json()["error"]["detalles"]]
    assert any("debe ser un número entero" in m for m in mensajes)
    extra = cliente.post("/citas", json=_cita(raro=1), headers=RECEPCION)
    assert extra.status_code == 400
    estado_malo = cliente.get("/citas", params={"estado": "VOLANDO"}, headers=RESPONSABLE)
    assert estado_malo.status_code == 400


# --- OpenAPI ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_openapi_publica_los_endpoints_y_el_encabezado_de_rol(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    contrato = cliente.get("/openapi.json").json()
    esperados = {"/health", "/servicios", "/propietarios", "/propietarios/{propietario_id}",
                 "/mascotas", "/mascotas/{mascota_id}", "/citas", "/citas/{cita_id}",
                 "/citas/{cita_id}/servicios", "/citas/{cita_id}/confirmar",
                 "/citas/{cita_id}/realizar", "/citas/{cita_id}/cancelar"}
    assert esperados <= set(contrato["paths"])
    confirmar = contrato["paths"]["/citas/{cita_id}/confirmar"]["post"]
    assert any(p["name"] == "X-Rol" and p["in"] == "header" for p in confirmar["parameters"])
    assert {"200", "403", "404", "409", "422"} <= set(confirmar["responses"])
    assert contrato["paths"]["/citas"]["post"]["responses"]["201"]


def test_al_arrancar_crea_las_tablas_en_una_base_vacia(tmp_path):
    url = f"sqlite:///{tmp_path / 'nueva.db'}"  # base sin esquema
    with TestClient(create_app(url)) as cliente:  # el bloque `with` ejecuta el arranque
        respuesta = cliente.get("/servicios", headers=RECEPCION)
        assert respuesta.status_code == 200 and respuesta.json() == []
        assert cliente.get("/citas", headers=RECEPCION).json() == []


# --- evaluaciones, eventos y formato uniforme ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluaciones_responden_200_con_cumple_y_motivos(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]  # 3 x 300 = 900, propietario no preferente
    procesamiento = cliente.get(f"/citas/{cita_id}/evaluaciones/procesamiento", headers=RESPONSABLE)
    assert procesamiento.status_code == 200
    assert procesamiento.json() == {"regla": "procesamiento", "cumple": True, "motivos": []}
    beneficio = cliente.get(f"/citas/{cita_id}/evaluaciones/beneficio", headers=RECEPCION)
    assert beneficio.status_code == 200 and beneficio.json()["cumple"] is False
    assert beneficio.json()["motivos"] == ["NO_PREFERENTE", "TOTAL_INSUFICIENTE"]
    assert cliente.get(f"/citas/{cita_id}", headers=RECEPCION).json()["estado"] == "SOLICITADA"


@pytest.mark.parametrize("backend", BACKENDS)
def test_evaluaciones_errores(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]
    inexistente = cliente.get("/citas/NO-EXISTE/evaluaciones/beneficio", headers=RECEPCION)
    assert inexistente.status_code == 404 and _codigo(inexistente) == "NO_ENCONTRADO"
    regla_mala = cliente.get(f"/citas/{cita_id}/evaluaciones/inventada", headers=RECEPCION)
    assert regla_mala.status_code == 400 and _codigo(regla_mala) == "SOLICITUD_INVALIDA"
    clinico = cliente.get(f"/citas/{cita_id}/evaluaciones/beneficio",
                          headers={"X-Rol": "personal_clinico"})
    assert clinico.status_code == 403


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_eventos_se_consultan_por_http(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    cita_id = _solicitar(cliente)["cita_id"]
    assert cliente.get("/eventos", headers=RESPONSABLE).json() == []
    cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    (evento,) = cliente.get("/eventos", headers=RESPONSABLE).json()
    assert (evento["evento"], evento["cita_id"]) == ("CitaAgendada", cita_id)
    assert evento["payload"]["total"] == "900.00" and evento["secuencia"] >= 1
    assert cliente.get("/eventos", headers={"X-Rol": "personal_clinico"}).status_code == 403
    assert cliente.get("/eventos").status_code == 401


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_errores_traen_los_motivos_como_codigos(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, capacidad=5)
    inactivo = cliente.post("/propietarios", headers=RECEPCION,
                            json={"nombre": "Luis", "activo": False, "propietario_id": "P2"})
    assert inactivo.status_code == 201
    cliente.post("/mascotas", headers=RECEPCION,
                 json={"propietario_id": "P2", "nombre": "Max", "especie": "Perro",
                       "mascota_id": "M2"})
    cita_id = _solicitar(cliente, propietario_id="P2", mascota_id="M2")["cita_id"]
    rechazo = cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    assert rechazo.status_code == 422 and _codigo(rechazo) == "PRECONDICION_NO_CUMPLIDA"
    assert rechazo.json()["error"]["motivos"] == ["ACTOR_INACTIVO"]
    c1, c2 = _solicitar(cliente)["cita_id"], _solicitar(cliente)["cita_id"]
    cliente.post(f"/citas/{c1}/confirmar", headers=RECEPCION)
    sin_cupo = cliente.post(f"/citas/{c2}/confirmar", headers=RECEPCION)
    assert sin_cupo.json()["error"]["motivos"] == ["CAPACIDAD_INSUFICIENTE:S1"]
    invalida = cliente.post(f"/citas/{c2}/realizar", headers=VETERINARIO)
    assert invalida.json()["error"]["motivos"] == ["realizar desde SOLICITADA"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_toda_respuesta_de_error_tiene_el_mismo_formato(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    respuestas = [
        cliente.get("/ruta-que-no-existe"),                       # 404 de FastAPI
        cliente.post("/servicios", headers=RECEPCION),            # 405 de FastAPI
        cliente.get("/servicios"),                                # 401
        cliente.get("/citas/NO-EXISTE", headers=RECEPCION),       # 404 de negocio
        cliente.post("/citas", json={}, headers=RECEPCION),       # 400
    ]
    assert [r.status_code for r in respuestas] == [404, 405, 401, 404, 400]
    for respuesta in respuestas:
        assert set(respuesta.json()["error"]) == {"codigo", "mensaje", "detalles", "motivos"}
    assert respuestas[0].json()["error"]["codigo"] == "RUTA_NO_ENCONTRADA"
    assert respuestas[1].json()["error"]["codigo"] == "METODO_NO_PERMITIDO"


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_tipos_son_estrictos_y_un_json_roto_es_400(backend, tmp_path):
    cliente = _cliente(backend, tmp_path)
    for cambio in ({"servicios": [{"servicio_id": "S1", "cantidad": "2"}]},
                   {"servicios": [{"servicio_id": "S1", "cantidad": True}]},
                   {"autorizada": "si"}):
        respuesta = cliente.post("/citas", json=_cita(**cambio), headers=RECEPCION)
        assert respuesta.status_code == 400, cambio
    roto = cliente.post("/citas", content="{esto no es json", headers={
        **RECEPCION, "Content-Type": "application/json"})
    assert roto.status_code == 400 and _codigo(roto) == "SOLICITUD_INVALIDA"
    assert cliente.get("/citas", headers=RESPONSABLE).json() == []  # no se guardó nada


def test_el_contrato_openapi_documenta_evaluaciones_eventos_y_el_formato_de_error(tmp_path):
    contrato = create_app(f"sqlite:///{tmp_path / 'c.db'}").openapi()
    assert {"/citas/{cita_id}/evaluaciones/{regla}", "/eventos"} <= set(contrato["paths"])
    esquemas = contrato["components"]["schemas"]
    assert {"ErrorOut", "CuerpoDeError", "CitaOut", "EvaluacionOut", "EventoOut"} <= set(esquemas)
    assert "HTTPValidationError" not in esquemas
    assert set(esquemas["CuerpoDeError"]["properties"]) == {
        "codigo", "mensaje", "detalles", "motivos"}
    confirmar = contrato["paths"]["/citas/{cita_id}/confirmar"]["post"]
    assert "ErrorOut" in str(confirmar["responses"]["409"])
    assert esquemas["CitaOut"]["properties"]["total_mxn"]["type"] == "string"


# --- vacunación (CU-03) ---

def _vacuna(vacuna="VAC-REFUERZO", fecha="2026-10-01", **extra):
    return {"vacuna": vacuna, "fecha_aplicacion": fecha, **extra}


def _vacunar(cliente, mascota="M1", **cuerpo):
    respuesta = cliente.post(f"/mascotas/{mascota}/vacunaciones", json=_vacuna(**cuerpo),
                             headers=VETERINARIO)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_una_vacuna_responde_201_con_el_seguimiento(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    cuerpo = _vacunar(cliente, lote="L-7")
    assert cuerpo["vacunacion"] == {
        "vacunacion_id": cuerpo["vacunacion"]["vacunacion_id"], "mascota_id": "M1",
        "vacuna": "VAC-REFUERZO", "fecha_aplicacion": "2026-10-01", "lote": "L-7"}
    assert cuerpo["seguimiento"] == {
        "vacuna": "VAC-REFUERZO", "ultima_aplicacion": "2026-10-01", "estado": "calculado",
        "proxima_aplicacion": "2026-10-31", "es_refuerzo": True, "motivos": []}


@pytest.mark.parametrize("backend", BACKENDS)
def test_registrar_no_depende_del_esquema_y_el_seguimiento_queda_pendiente(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    sin_esquema = _vacunar(cliente, vacuna="VAC-DESCONOCIDA")
    sin_validar = _vacunar(cliente, vacuna="VAC-SIN-VALIDAR")
    assert sin_esquema["seguimiento"]["estado"] == "pendiente_de_esquema"
    assert sin_esquema["seguimiento"]["motivos"] == ["ESQUEMA_NO_DEFINIDO"]
    assert sin_esquema["seguimiento"]["proxima_aplicacion"] is None
    assert sin_validar["seguimiento"]["motivos"] == ["ESQUEMA_NO_VALIDADO"]
    historial = cliente.get("/mascotas/M1/vacunaciones", headers=RECEPCION)
    assert historial.status_code == 200 and len(historial.json()) == 2  # se guardaron las dos


@pytest.mark.parametrize("backend", BACKENDS)
def test_el_historial_se_conserva_en_orden_y_el_seguimiento_usa_la_ultima(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    _vacunar(cliente, vacuna="VAC-ANUAL", fecha="2026-09-01")
    _vacunar(cliente, vacuna="VAC-ANUAL", fecha="2024-09-01")
    _vacunar(cliente, vacuna="vac-anual", fecha="2025-09-01")
    fechas = [v["fecha_aplicacion"]
              for v in cliente.get("/mascotas/M1/vacunaciones", headers=VETERINARIO).json()]
    assert fechas == ["2024-09-01", "2025-09-01", "2026-09-01"]
    (seguimiento,) = cliente.get("/mascotas/M1/vacunaciones/seguimiento",
                                 headers=RESPONSABLE).json()
    assert seguimiento["ultima_aplicacion"] == "2026-09-01"
    assert seguimiento["proxima_aplicacion"] == "2027-09-01"


@pytest.mark.parametrize("backend", BACKENDS)
def test_vacunacion_permisos_y_rol(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    for encabezado in (RECEPCION, RESPONSABLE):
        denegado = cliente.post("/mascotas/M1/vacunaciones", json=_vacuna(), headers=encabezado)
        assert denegado.status_code == 403 and _codigo(denegado) == "ACCESO_DENEGADO"
    assert "registrar vacunas" in denegado.json()["error"]["mensaje"]
    assert cliente.post("/mascotas/M1/vacunaciones", json=_vacuna()).status_code == 401
    clinico = {"X-Rol": "personal_clinico"}
    for ruta in ("/mascotas/M1/vacunaciones", "/mascotas/M1/vacunaciones/seguimiento",
                 "/vacunas/proximas", "/esquemas-vacunacion"):
        assert cliente.get(ruta, headers=clinico).status_code == 403, ruta
        assert cliente.get(ruta, headers=RECEPCION).status_code == 200, ruta


@pytest.mark.parametrize("backend", BACKENDS)
def test_vacunacion_errores_de_negocio_y_de_formato(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    rutas = (("post", "/mascotas/NO/vacunaciones"), ("get", "/mascotas/NO/vacunaciones"),
             ("get", "/mascotas/NO/vacunaciones/seguimiento"))
    for metodo, ruta in rutas:
        extra = {"json": _vacuna()} if metodo == "post" else {}
        respuesta = getattr(cliente, metodo)(ruta, headers=VETERINARIO, **extra)
        assert respuesta.status_code == 404 and _codigo(respuesta) == "NO_ENCONTRADO", ruta
    vacia = cliente.post("/mascotas/M1/vacunaciones", json=_vacuna(vacuna="  "),
                         headers=VETERINARIO)
    assert vacia.status_code == 422 and _codigo(vacia) == "VACUNA_VACIA"
    lote = cliente.post("/mascotas/M1/vacunaciones", json=_vacuna(lote="  "), headers=VETERINARIO)
    assert lote.status_code == 422 and _codigo(lote) == "LOTE_VACIO"
    for cuerpo in ({"fecha_aplicacion": "2026-10-01"}, _vacuna(fecha="01/10/2026"),
                   _vacuna(extra=1), _vacuna(fecha=None)):
        respuesta = cliente.post("/mascotas/M1/vacunaciones", json=cuerpo, headers=VETERINARIO)
        assert respuesta.status_code == 400, cuerpo
    assert cliente.get("/mascotas/M1/vacunaciones", headers=VETERINARIO).json() == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_vacunacion_con_id_repetido_es_409(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    _vacunar(cliente, vacunacion_id="V-FIJA")
    repetida = cliente.post("/mascotas/M1/vacunaciones", json=_vacuna(vacunacion_id="V-FIJA"),
                            headers=VETERINARIO)
    assert repetida.status_code == 409 and _codigo(repetida) == "YA_EXISTE"
    assert "vacunación" in repetida.json()["error"]["mensaje"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_vacunas_proximas_para_recordatorios(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    _vacunar(cliente, vacuna="VAC-REFUERZO", fecha="2026-09-01")   # próxima 2026-10-01
    _vacunar(cliente, vacuna="VAC-ANUAL", fecha="2026-10-10")      # próxima 2027-10-10
    _vacunar(cliente, vacuna="VAC-SIN-VALIDAR", fecha="2026-09-01")  # pendiente: no aparece
    pronto = cliente.get("/vacunas/proximas",
                         params={"dias": 30, "fecha_de_referencia": "2026-10-15"},
                         headers=RECEPCION)
    assert pronto.status_code == 200
    assert pronto.json() == [{
        "mascota_id": "M1", "propietario_id": "P1", "vacuna": "VAC-REFUERZO",
        "proxima_aplicacion": "2026-10-01", "es_refuerzo": True, "vencida": True}]
    lejos = cliente.get("/vacunas/proximas",
                        params={"dias": 400, "fecha_de_referencia": "2026-10-15"},
                        headers=RECEPCION).json()
    assert [a["vacuna"] for a in lejos] == ["VAC-REFUERZO", "VAC-ANUAL"]
    assert cliente.get("/vacunas/proximas", headers=RECEPCION).status_code == 200  # hoy
    negativa = cliente.get("/vacunas/proximas", params={"dias": -1}, headers=RECEPCION)
    assert negativa.status_code == 422 and _codigo(negativa) == "VENTANA_INVALIDA"
    texto = cliente.get("/vacunas/proximas", params={"dias": "abc"}, headers=RECEPCION)
    assert texto.status_code == 400 and _codigo(texto) == "SOLICITUD_INVALIDA"


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_esquemas_de_referencia_se_consultan(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    esquemas = cliente.get("/esquemas-vacunacion", headers=VETERINARIO).json()
    assert [(e["vacuna"], e["frecuencia_dias"], e["requiere_refuerzo"], e["validado"])
            for e in esquemas] == [
        ("VAC-ANUAL", 365, False, True), ("VAC-REFUERZO", 30, True, True),
        ("VAC-SIN-VALIDAR", 90, True, False)]


@pytest.mark.parametrize("backend", BACKENDS)
def test_los_eventos_de_vacunacion_y_de_citas_conviven_en_el_listado(backend, tmp_path):
    cliente = _cliente(backend, tmp_path, esquemas=True)
    cita_id = _solicitar(cliente)["cita_id"]
    cliente.post(f"/citas/{cita_id}/confirmar", headers=RECEPCION)
    vacunacion_id = _vacunar(cliente)["vacunacion"]["vacunacion_id"]
    cita, vacuna = cliente.get("/eventos", headers=RESPONSABLE).json()
    assert (cita["evento"], cita["agregado_tipo"], cita["cita_id"]) == (
        "CitaAgendada", "Cita", cita_id)
    assert (vacuna["evento"], vacuna["agregado_tipo"], vacuna["agregado_id"],
            vacuna["cita_id"]) == ("VacunacionRegistrada", "Vacunacion", vacunacion_id, None)
    assert vacuna["payload"]["fecha_aplicacion"] == "2026-10-01"


def test_el_contrato_openapi_documenta_la_vacunacion(tmp_path):
    contrato = create_app(f"sqlite:///{tmp_path / 'c.db'}").openapi()
    rutas = contrato["paths"]
    assert {"/mascotas/{mascota_id}/vacunaciones",
            "/mascotas/{mascota_id}/vacunaciones/seguimiento",
            "/vacunas/proximas", "/esquemas-vacunacion"} <= set(rutas)
    assert rutas["/mascotas/{mascota_id}/vacunaciones"]["post"]["tags"] == ["Vacunación"]
    assert "201" in rutas["/mascotas/{mascota_id}/vacunaciones"]["post"]["responses"]
    esquemas = contrato["components"]["schemas"]
    assert {"VacunacionRegistradaOut", "SeguimientoOut", "EsquemaOut", "RecordatorioOut",
            "VacunacionIn"} <= set(esquemas)
    assert "HTTPValidationError" not in esquemas

