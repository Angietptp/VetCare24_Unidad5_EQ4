"""Traducción de errores a respuestas HTTP (D-13, H-07) con mensajes para el cliente.

Función pura: no depende de FastAPI, así se prueba sin levantar el servidor.
Todas las respuestas de error tienen la misma forma:
    {"error": {"codigo": "...", "mensaje": "...", "detalles": [...], "motivos": [...]}}
`codigo` es corto y estable (para programas); `mensaje` es una frase en español pensada para
mostrarse tal cual a quien usa el sistema. `detalles` señala los campos inválidos de una
solicitud mal formada. `motivos` trae los códigos de las reglas que se incumplieron (por
ejemplo ACTOR_INACTIVO), para que un programa sepa qué falló sin leer la frase.
"""

from typing import Any

from vetcare24.application.errores import (
    AccesoDenegado,
    ErrorDeAplicacion,
    NoEncontrado,
    YaExiste,
)
from vetcare24.domain.errors import (
    ErrorDeDominio,
    InvarianteViolada,
    PrecondicionNoCumplida,
    TransicionInvalida,
)

CAPACIDAD = "CAPACIDAD_INSUFICIENTE"
ROLES = "recepcion, veterinario, personal_clinico o responsable"

ROLES_LEGIBLES = {
    "recepcion": "Recepción", "veterinario": "Veterinario",
    "personal_clinico": "Personal clínico", "responsable": "Responsable",
}
PERMISOS_LEGIBLES = {
    "registrar_propietario": "registrar propietarios", "registrar_mascota": "registrar mascotas",
    "solicitar_cita": "solicitar citas", "modificar_cita": "modificar citas",
    "confirmar_cita": "confirmar citas", "cancelar_cita": "cancelar citas",
    "realizar_cita": "realizar citas", "consultar_cita": "consultar citas",
    "consultar_catalogo": "consultar el catálogo",
    "registrar_vacunacion": "registrar vacunas", "consultar_vacunacion": "consultar vacunas",
    "atender_emergencia": "registrar emergencias",
    "iniciar_atencion_emergencia": "iniciar la atención de emergencias",
    "consultar_emergencia": "consultar emergencias",
}
ARTICULOS = {
    "cita": ("la", "una"), "mascota": ("la", "una"), "vacunación": ("la", "una"),
    "emergencia": ("la", "una"),
}
ACCIONES_LEGIBLES = {"iniciar_atencion": "iniciar la atención de"}
ESTADOS_LEGIBLES = {"EN_ATENCION": "en atención"}  # por omisión: el / un
MOTIVOS = {  # motivo de la regla -> frase ("{x}" es el servicio, si lo hay)
    "CAPACIDAD_INSUFICIENTE": "no hay capacidad suficiente para el servicio {x}",
    "SERVICIO_DESHABILITADO": "el servicio {x} no está disponible por el momento",
    "SERVICIO_INEXISTENTE": "el servicio {x} no existe en el catálogo",
    "ACTOR_INACTIVO": "el propietario está inactivo",
    "NO_AUTORIZADA": "la cita no cuenta con autorización",
    "DETALLE_VACIO": "la cita no tiene servicios",
    "CITA_FINALIZADA": "la cita ya está finalizada",
    "PROPIETARIO_INCORRECTO": "la cita no pertenece a ese propietario",
    "NO_PREFERENTE": "el propietario no es cliente preferente",
    "SIN_PROMOCION": "no hay una promoción activa",
    "TOTAL_INSUFICIENTE": "el total no alcanza el mínimo requerido",
}
INVARIANTES = {  # código de la violación -> frase (se usa {x} con el id que trae el mensaje)
    "DETALLE_VACIO": "La cita debe incluir al menos un servicio.",
    "SERVICIO_INEXISTENTE": "El servicio {x} no existe en el catálogo.",
    "SERVICIO_DESHABILITADO": "El servicio {x} no está disponible por el momento.",
    "MASCOTA_AJENA": "La mascota indicada no pertenece a ese propietario.",
    "CANTIDAD_INVALIDA": "La cantidad de cada servicio debe ser de al menos 1.",
    "PESO_INVALIDO": "El peso de la mascota no es válido: debe ser un número mayor que cero.",
    "VACUNA_VACIA": "Falta indicar el nombre de la vacuna.",
    "LOTE_VACIO": "Si se indica el lote, no puede estar en blanco.",
    "FECHA_INVALIDA": "La fecha de aplicación debe ser una fecha con formato AAAA-MM-DD.",
    "VENTANA_INVALIDA": "Los días de anticipación deben ser un número entero de 0 o más.",
    "MOTIVO_VACIO": "Falta indicar el motivo.",
    "DATOS_PACIENTE_VACIOS": "Si se indican los datos del paciente, no pueden estar en blanco.",
}
PISTAS = {("SOLICITADA", "realizar"): " Primero debe confirmarse."}
TIPOS_DE_CAMPO = {  # tipo de error de validación -> cómo se dice
    "int_parsing": "debe ser un número entero", "int_type": "debe ser un número entero",
    "int_from_float": "debe ser un número entero",
    "decimal_parsing": "debe ser un número", "decimal_type": "debe ser un número",
    "date_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_type": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "bool_parsing": "debe ser verdadero o falso", "bool_type": "debe ser verdadero o falso",
    "string_type": "debe ser texto", "list_type": "debe ser una lista",
    "model_attributes_type": "debe ser un objeto", "dict_type": "debe ser un objeto",
}


class RolNoIndicado(Exception):
    """La solicitud no trae el encabezado X-Rol (J-09)."""


class RolDesconocido(Exception):
    """El valor de X-Rol no corresponde a ningún rol."""

    def __init__(self, valor: str) -> None:
        self.valor = valor
        super().__init__(f"Rol desconocido: {valor!r}")


def cuerpo_de_error(
    codigo: str, mensaje: str, detalles: list[Any] | None = None,
    motivos: tuple[str, ...] = (),
) -> dict:
    return {"error": {
        "codigo": codigo, "mensaje": mensaje, "detalles": detalles or [], "motivos": list(motivos),
    }}


# --- frases ---

def _oracion(texto: str) -> str:
    texto = texto.strip()
    texto = texto[:1].upper() + texto[1:]
    return texto if texto.endswith((".", "!", "?")) else texto + "."


def _motivo(motivo: str) -> str:
    codigo, _, servicio = motivo.partition(":")
    frase = MOTIVOS.get(codigo)
    if frase is None:
        return codigo.lower().replace("_", " ")
    return frase.format(x=servicio or "indicado")


def _invariante(error: InvarianteViolada) -> str:
    plantilla = INVARIANTES.get(error.codigo)
    if plantilla is None:
        return _oracion(error.mensaje)
    return plantilla.format(x=error.mensaje.split(" ")[0])  # el mensaje empieza con el id


def _articulo(tipo: str, indefinido: bool = False) -> str:
    definido, indef = ARTICULOS.get(tipo, ("el", "un"))
    return indef if indefinido else definido


# --- solicitudes mal formadas ---

def detalle_de_validacion(error: dict) -> dict:
    """Convierte un error de validación de FastAPI en un campo y una frase en español."""
    loc = [str(parte) for parte in error.get("loc", ())]
    if loc and loc[0] in ("body", "query", "path", "header"):
        loc = loc[1:]
    campo = ".".join(loc) or "solicitud"
    tipo = error.get("type", "")
    if tipo == "json_invalid":
        return {"campo": "cuerpo", "mensaje": "El cuerpo de la solicitud no es un JSON válido."}
    if tipo == "missing":
        frase = f"Falta el campo «{campo}»."
    elif tipo == "extra_forbidden":
        frase = f"El campo «{campo}» no se esperaba."
    elif tipo in ("enum", "literal_error"):
        permitidos = (error.get("ctx") or {}).get("expected")
        extra = f": {str(permitidos).replace(' or ', ' o ')}" if permitidos else ""
        frase = f"El campo «{campo}» tiene un valor no permitido; debe ser uno de{extra}."
    else:
        frase = f"El campo «{campo}» {TIPOS_DE_CAMPO.get(tipo, 'tiene un valor no válido')}."
    return {"campo": campo, "mensaje": frase}


def solicitud_invalida(errores: list[dict]) -> tuple[int, dict]:
    detalles = [detalle_de_validacion(e) for e in errores]
    return 400, cuerpo_de_error(
        "SOLICITUD_INVALIDA", "La solicitud no es válida. Revisa los campos indicados.", detalles)


# --- errores de negocio ---

def traducir(error: Exception) -> tuple[int, dict] | None:
    """Devuelve (código HTTP, cuerpo) para un error de negocio; None si no es de negocio."""
    if isinstance(error, RolNoIndicado):
        return 401, cuerpo_de_error(
            "ROL_REQUERIDO",
            f"Falta indicar tu rol. Envía el encabezado X-Rol con uno de estos valores: {ROLES}.")
    if isinstance(error, RolDesconocido):
        return 400, cuerpo_de_error(
            "ROL_DESCONOCIDO", f"El rol «{error.valor}» no existe. Usa {ROLES}.")
    if isinstance(error, AccesoDenegado):
        rol = ROLES_LEGIBLES.get(error.rol, error.rol)
        accion = PERMISOS_LEGIBLES.get(error.permiso, error.permiso)
        return 403, cuerpo_de_error(
            "ACCESO_DENEGADO", f"El rol {rol} no tiene permiso para {accion}.")
    if isinstance(error, NoEncontrado):
        return 404, cuerpo_de_error(
            "NO_ENCONTRADO",
            f"No se encontró {_articulo(error.tipo)} {error.tipo} «{error.identificador}».")
    if isinstance(error, YaExiste):
        return 409, cuerpo_de_error(
            "YA_EXISTE",
            f"Ya existe {_articulo(error.tipo, True)} {error.tipo} "
            f"con el identificador «{error.identificador}».")
    if isinstance(error, TransicionInvalida):
        pista = PISTAS.get((error.estado, error.accion), "")
        return 409, cuerpo_de_error(
            "TRANSICION_INVALIDA",
            f"No se puede {ACCIONES_LEGIBLES.get(error.accion, error.accion)} "
            f"{_articulo(error.entidad, True)} {error.entidad} que está "
            f"{ESTADOS_LEGIBLES.get(error.estado, error.estado.lower())}.{pista}",
            motivos=(error.motivo,))
    if isinstance(error, PrecondicionNoCumplida):
        razones = "; ".join(_motivo(m) for m in error.motivos)
        mensaje = (f"No se puede {error.accion} {_articulo(error.entidad)} {error.entidad}: "
                   f"{razones}.")
        # H-07: falta de capacidad es un conflicto (409); las demás precondiciones, 422.
        if any(m.startswith(CAPACIDAD) for m in error.motivos):
            return 409, cuerpo_de_error(CAPACIDAD, mensaje, motivos=error.motivos)
        return 422, cuerpo_de_error("PRECONDICION_NO_CUMPLIDA", mensaje, motivos=error.motivos)
    if isinstance(error, InvarianteViolada):
        return 422, cuerpo_de_error(error.codigo, _invariante(error))
    if isinstance(error, (ErrorDeDominio, ErrorDeAplicacion)):
        return 422, cuerpo_de_error("REGLA_DE_NEGOCIO", _oracion(str(error)))
    return None


def error_http(estado: int) -> tuple[int, dict]:
    """Errores que FastAPI genera solo (ruta inexistente, método no permitido) con el mismo
    formato que el resto, para que el cliente siempre lea `error.codigo`."""
    if estado == 404:
        return 404, cuerpo_de_error("RUTA_NO_ENCONTRADA", "La dirección solicitada no existe.")
    if estado == 405:
        return 405, cuerpo_de_error(
            "METODO_NO_PERMITIDO", "Ese método HTTP no está permitido en esta dirección.")
    return estado, cuerpo_de_error("ERROR_HTTP", "No se pudo atender la solicitud.")
