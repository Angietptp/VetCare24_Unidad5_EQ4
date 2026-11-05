"""API (Etapa 7): traducción de errores a HTTP y contratos, sin levantar el servidor."""

from datetime import date

import pytest
from pydantic import ValidationError

from tests.bd import armar, preparar, sembrar_basico
from vetcare24.api.errores_http import (
    RolDesconocido,
    RolNoIndicado,
    error_http,
    solicitud_invalida,
    traducir,
)
from vetcare24.api.esquemas import CitaIn, MascotaIn, cita_a_salida
from vetcare24.application.comandos import SolicitarCita
from vetcare24.application.control_de_acceso import Rol
from vetcare24.application.errores import AccesoDenegado, ErrorDeAplicacion, NoEncontrado, YaExiste
from vetcare24.domain.errors import (
    ErrorDeDominio,
    InvarianteViolada,
    PrecondicionNoCumplida,
    TransicionInvalida,
)


@pytest.mark.parametrize("error, codigo_http, codigo", [
    (RolNoIndicado(), 401, "ROL_REQUERIDO"),
    (RolDesconocido("jefe"), 400, "ROL_DESCONOCIDO"),
    (AccesoDenegado("veterinario", "solicitar_cita"), 403, "ACCESO_DENEGADO"),
    (NoEncontrado("cita", "C9"), 404, "NO_ENCONTRADO"),
    (YaExiste("cita", "C1"), 409, "YA_EXISTE"),
    (TransicionInvalida("SOLICITADA", "realizar"), 409, "TRANSICION_INVALIDA"),
    (PrecondicionNoCumplida("confirmar", ("CAPACIDAD_INSUFICIENTE:S1",)), 409,
     "CAPACIDAD_INSUFICIENTE"),
    (PrecondicionNoCumplida("confirmar", ("PROPIETARIO_INACTIVO",)), 422,
     "PRECONDICION_NO_CUMPLIDA"),
    (InvarianteViolada("DETALLE_VACIO", "sin servicios"), 422, "DETALLE_VACIO"),
    (ErrorDeDominio("otra regla"), 422, "REGLA_DE_NEGOCIO"),
    (ErrorDeAplicacion("otro error"), 422, "REGLA_DE_NEGOCIO"),
])
def test_cada_error_tiene_su_codigo_http(error, codigo_http, codigo):
    http, cuerpo = traducir(error)
    assert http == codigo_http
    assert cuerpo["error"]["codigo"] == codigo
    assert set(cuerpo["error"]) == {"codigo", "mensaje", "detalles", "motivos"}


def test_los_motivos_viajan_como_codigos_para_los_programas():
    _, transicion = traducir(TransicionInvalida("SOLICITADA", "realizar"))
    assert transicion["error"]["motivos"] == ["realizar desde SOLICITADA"]
    _, capacidad = traducir(PrecondicionNoCumplida("confirmar", ("CAPACIDAD_INSUFICIENTE:S1",)))
    assert capacidad["error"]["motivos"] == ["CAPACIDAD_INSUFICIENTE:S1"]
    _, regla = traducir(PrecondicionNoCumplida("confirmar", ("ACTOR_INACTIVO", "NO_AUTORIZADA")))
    assert regla["error"]["motivos"] == ["ACTOR_INACTIVO", "NO_AUTORIZADA"]
    _, sin_motivos = traducir(NoEncontrado("cita", "C9"))
    assert sin_motivos["error"]["motivos"] == []


def test_los_errores_que_fastapi_genera_solo_tienen_el_mismo_formato():
    assert error_http(404)[0] == 404
    assert error_http(404)[1]["error"]["codigo"] == "RUTA_NO_ENCONTRADA"
    assert error_http(405)[1]["error"]["codigo"] == "METODO_NO_PERMITIDO"
    estado, cuerpo = error_http(418)
    assert estado == 418 and cuerpo["error"]["codigo"] == "ERROR_HTTP"
    assert set(cuerpo["error"]) == {"codigo", "mensaje", "detalles", "motivos"}


def test_un_json_roto_se_explica_sin_inventar_un_campo():
    _, cuerpo = solicitud_invalida([{"type": "json_invalid", "loc": ("body", 0), "msg": "x"}])
    assert cuerpo["error"]["detalles"] == [
        {"campo": "cuerpo", "mensaje": "El cuerpo de la solicitud no es un JSON válido."}]


def test_los_errores_de_vacunacion_se_dicen_en_espanol():
    estado, cuerpo = traducir(AccesoDenegado("recepcion", "registrar_vacunacion"))
    assert estado == 403
    assert cuerpo["error"]["mensaje"] == (
        "El rol Recepción no tiene permiso para registrar vacunas.")
    estado, cuerpo = traducir(YaExiste("vacunación", "V1"))
    assert (estado, cuerpo["error"]["mensaje"]) == (
        409, "Ya existe una vacunación con el identificador «V1».")
    casos = {
        "VACUNA_VACIA": "Falta indicar el nombre de la vacuna.",
        "LOTE_VACIO": "Si se indica el lote, no puede estar en blanco.",
        "FECHA_INVALIDA": "La fecha de aplicación debe ser una fecha con formato AAAA-MM-DD.",
        "VENTANA_INVALIDA": "Los días de anticipación deben ser un número entero de 0 o más.",
    }
    for codigo, frase in casos.items():
        estado, cuerpo = traducir(InvarianteViolada(codigo, "mensaje del dominio"))
        assert (estado, cuerpo["error"]["codigo"], cuerpo["error"]["mensaje"]) == (
            422, codigo, frase)


def test_un_error_que_no_es_de_negocio_no_se_traduce():
    assert traducir(RuntimeError("falla técnica")) is None


def test_una_precondicion_con_varios_motivos_los_dice_en_una_frase():
    _, cuerpo = traducir(PrecondicionNoCumplida(
        "confirmar", ("ACTOR_INACTIVO", "NO_AUTORIZADA", "SERVICIO_DESHABILITADO:S3")))
    assert cuerpo["error"]["mensaje"] == (
        "No se puede confirmar la cita: el propietario está inactivo; "
        "la cita no cuenta con autorización; el servicio S3 no está disponible por el momento.")
    assert cuerpo["error"]["detalles"] == []


@pytest.mark.parametrize("error, mensaje", [
    (RolNoIndicado(), "Falta indicar tu rol. Envía el encabezado X-Rol con uno de estos "
                      "valores: recepcion, veterinario, personal_clinico o responsable."),
    (RolDesconocido("jefe"), "El rol «jefe» no existe. Usa recepcion, veterinario, "
                             "personal_clinico o responsable."),
    (AccesoDenegado("veterinario", "solicitar_cita"),
     "El rol Veterinario no tiene permiso para solicitar citas."),
    (NoEncontrado("cita", "C9"), "No se encontró la cita «C9»."),
    (NoEncontrado("propietario", "P9"), "No se encontró el propietario «P9»."),
    (YaExiste("mascota", "M1"), "Ya existe una mascota con el identificador «M1»."),
    (YaExiste("propietario", "P1"), "Ya existe un propietario con el identificador «P1»."),
    (TransicionInvalida("CONFIRMADA", "confirmar"),
     "No se puede confirmar una cita que está confirmada."),
    (InvarianteViolada("DETALLE_VACIO", "x"), "La cita debe incluir al menos un servicio."),
    (InvarianteViolada("SERVICIO_DESHABILITADO", "S3 está deshabilitado"),
     "El servicio S3 no está disponible por el momento."),
    (InvarianteViolada("NOMBRE_VACIO", "el nombre no puede estar vacío"),
     "El nombre no puede estar vacío."),
])
def test_los_mensajes_son_frases_para_el_cliente(error, mensaje):
    assert traducir(error)[1]["error"]["mensaje"] == mensaje


def test_los_errores_de_validacion_se_dicen_en_espanol():
    http, cuerpo = solicitud_invalida([
        {"type": "missing", "loc": ("body", "especie"), "msg": "Field required"},
        {"type": "int_parsing", "loc": ("body", "servicios", 0, "cantidad"), "msg": "x"},
        {"type": "extra_forbidden", "loc": ("body", "raro"), "msg": "x"},
        {"type": "date_parsing", "loc": ("body", "fecha_solicitud"), "msg": "x"},
        {"type": "enum", "loc": ("query", "estado"), "msg": "x",
         "ctx": {"expected": "'SOLICITADA' o 'CONFIRMADA'"}},
        {"type": "algo_nuevo", "loc": ("body", "x"), "msg": "x"},
    ])
    assert http == 400 and cuerpo["error"]["codigo"] == "SOLICITUD_INVALIDA"
    assert [d["mensaje"] for d in cuerpo["error"]["detalles"]] == [
        "Falta el campo «especie».",
        "El campo «servicios.0.cantidad» debe ser un número entero.",
        "El campo «raro» no se esperaba.",
        "El campo «fecha_solicitud» debe ser una fecha con formato AAAA-MM-DD.",
        "El campo «estado» tiene un valor no permitido; debe ser uno de: "
        "'SOLICITADA' o 'CONFIRMADA'.",
        "El campo «x» tiene un valor no válido.",
    ]
    assert cuerpo["error"]["detalles"][1]["campo"] == "servicios.0.cantidad"


def test_las_entradas_rechazan_campos_desconocidos_y_tipos_incorrectos():
    base = {"propietario_id": "P1", "mascota_id": "M1", "fecha_solicitud": "2026-10-02",
            "autorizada": True, "servicios": [{"servicio_id": "S1", "cantidad": 1}]}
    assert CitaIn(**base).fecha_solicitud == date(2026, 10, 2)
    with pytest.raises(ValidationError):
        CitaIn(**base, extra=1)
    with pytest.raises(ValidationError):
        CitaIn(**{**base, "servicios": [{"servicio_id": "S1", "cantidad": "muchas"}]})
    with pytest.raises(ValidationError):
        MascotaIn(propietario_id="P1", nombre="Rex")  # falta la especie
    # tipos estrictos: no se aceptan textos ni booleanos donde va un entero o un booleano
    with pytest.raises(ValidationError):
        CitaIn(**{**base, "servicios": [{"servicio_id": "S1", "cantidad": "2"}]})
    with pytest.raises(ValidationError):
        CitaIn(**{**base, "servicios": [{"servicio_id": "S1", "cantidad": True}]})
    with pytest.raises(ValidationError):
        CitaIn(**{**base, "autorizada": "si"})


@pytest.mark.parametrize("backend", ["sqlite"])
def test_la_cita_se_serializa_con_importes_en_texto_decimal(backend, tmp_path):
    url = preparar(backend, tmp_path)
    sembrar_basico(url)
    entorno = armar(url)
    cita = entorno.citas.solicitar(Rol.RECEPCION, SolicitarCita(
        propietario_id="P1", mascota_id="M1", servicios=(("S1", 3), ("S2", 1)),
        fecha_solicitud=date(2026, 10, 2), autorizada=True, cita_id="C1"))
    with entorno.fabrica() as uow:
        catalogo = uow.servicios.todos()
    salida = cita_a_salida(cita, catalogo).model_dump(mode="json")
    assert salida["total_mxn"] == "1000.00"  # 3 x 300 + 1 x 100, sin float
    assert salida["estado"] == "SOLICITADA"
    assert salida["servicios"] == [
        {"servicio_id": "S1", "cantidad": 3}, {"servicio_id": "S2", "cantidad": 1}]
    assert salida["fecha_solicitud"] == "2026-10-02"
