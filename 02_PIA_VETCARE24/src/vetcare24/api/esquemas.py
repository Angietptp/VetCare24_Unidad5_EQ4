"""Contratos de entrada y salida de la API (se publican en OpenAPI).

Solo describen la forma de los datos; las reglas de negocio viven en el dominio.
Los importes viajan como texto decimal ("300.00") para no perder precisión (D-02).
"""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita
from vetcare24.domain.emergencia import Emergencia
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.seguimiento_vacunacion import SeguimientoDeVacuna
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")  # un campo desconocido es un error de solicitud


# --- entradas ---

class PropietarioIn(Entrada):
    nombre: str
    activo: StrictBool = True
    preferente: StrictBool = False
    propietario_id: str | None = Field(None, description="Opcional; si falta se genera.")


class MascotaIn(Entrada):
    propietario_id: str
    nombre: str
    especie: str
    raza: str | None = None
    sexo: str | None = None
    fecha_nacimiento: date | None = None
    peso_kg: Decimal | None = None
    alergias: list[str] = Field(default_factory=list)
    mascota_id: str | None = Field(None, description="Opcional; si falta se genera.")


class LineaIn(Entrada):
    servicio_id: str
    cantidad: StrictInt = Field(description="Unidades solicitadas (mínimo 1).")


class CitaIn(Entrada):
    propietario_id: str
    mascota_id: str
    servicios: list[LineaIn]
    fecha_solicitud: date
    autorizada: StrictBool
    promocion_activa: StrictBool = False
    referencia: str | None = None
    cita_id: str | None = Field(None, description="Opcional; si falta se genera.")


class ModificarServiciosIn(Entrada):
    servicios: list[LineaIn]


# --- salidas ---

class ServicioOut(BaseModel):
    servicio_id: str
    descripcion: str
    precio_mxn: str = Field(examples=["313.00"], description="Pesos mexicanos, como texto.")
    capacidad: int
    habilitado: bool


class PropietarioOut(BaseModel):
    propietario_id: str
    nombre: str
    activo: bool
    preferente: bool


class MascotaOut(BaseModel):
    mascota_id: str
    propietario_id: str
    nombre: str
    especie: str
    raza: str | None
    sexo: str | None
    fecha_nacimiento: date | None
    peso_kg: str | None
    alergias: list[str]


class LineaOut(BaseModel):
    servicio_id: str
    cantidad: int


class CitaOut(BaseModel):
    cita_id: str
    propietario_id: str
    mascota_id: str
    estado: str
    servicios: list[LineaOut]
    fecha_solicitud: date
    autorizada: bool
    promocion_activa: bool
    referencia: str | None
    total_mxn: str = Field(examples=["7587.00"], description="Suma de precio x cantidad.")


class DetalleDeCampo(BaseModel):
    campo: str = Field(examples=["servicios.0.cantidad"])
    mensaje: str = Field(examples=["El campo «servicios.0.cantidad» debe ser un número entero."])


class CuerpoDeError(BaseModel):
    codigo: str = Field(examples=["TRANSICION_INVALIDA"], description="Estable, para programas.")
    mensaje: str = Field(description="Frase en español lista para mostrarse.")
    detalles: list[DetalleDeCampo] = Field(
        default_factory=list, description="Campos inválidos de una solicitud mal formada.")
    motivos: list[str] = Field(
        default_factory=list, description="Códigos de las reglas incumplidas.",
        examples=[["ACTOR_INACTIVO"]])


class ErrorOut(BaseModel):
    """Forma común de todos los errores: {"error": {codigo, mensaje, detalles, motivos}}."""

    error: CuerpoDeError


class EvaluacionOut(BaseModel):
    regla: str = Field(examples=["procesamiento"])
    cumple: bool
    motivos: list[str] = Field(description="Códigos de lo que no se cumple (vacío si cumple).")


class EventoOut(BaseModel):
    secuencia: int
    evento: str = Field(examples=["CitaAgendada"])
    agregado_tipo: str = Field(examples=["Cita"], description="Qué agregado emitió el evento.")
    agregado_id: str
    cita_id: str | None = Field(description="El mismo id, solo si el evento es de una cita.")
    ocurrido_en: str
    payload: dict[str, Any]


class VacunacionIn(Entrada):
    vacuna: str = Field(examples=["VAC-ANUAL"])
    fecha_aplicacion: date = Field(description="Cuándo se aplicó (AAAA-MM-DD).")
    lote: str | None = None
    vacunacion_id: str | None = Field(
        None, description="Opcional; si no se indica, el sistema lo genera.")


class VacunacionOut(BaseModel):
    vacunacion_id: str
    mascota_id: str
    vacuna: str
    fecha_aplicacion: date
    lote: str | None


class SeguimientoOut(BaseModel):
    vacuna: str
    ultima_aplicacion: date
    estado: str = Field(
        examples=["calculado"],
        description="`calculado`, o `pendiente_de_esquema` si la vacuna no tiene un esquema "
                    "definido y validado (no es un error).")
    proxima_aplicacion: date | None = Field(description="Solo si el estado es `calculado`.")
    es_refuerzo: bool | None = Field(description="Si la siguiente aplicación es un refuerzo.")
    motivos: list[str] = Field(examples=[["ESQUEMA_NO_VALIDADO"]])


class VacunacionRegistradaOut(BaseModel):
    vacunacion: VacunacionOut
    seguimiento: SeguimientoOut


class EsquemaOut(BaseModel):
    vacuna: str
    frecuencia_dias: int = Field(description="Días hasta la siguiente aplicación.")
    requiere_refuerzo: bool
    validado: bool = Field(description="Solo un esquema validado se usa para calcular.")


class RecordatorioOut(BaseModel):
    mascota_id: str
    propietario_id: str
    vacuna: str
    proxima_aplicacion: date
    es_refuerzo: bool
    vencida: bool


class EmergenciaIn(Entrada):
    motivo: str = Field(examples=["Atropellamiento; sangrado en pata trasera"])
    mascota_id: str | None = Field(
        None, description="Opcional (P3): la mascota puede no estar registrada.")
    datos_paciente: str | None = Field(
        None, examples=["Perro mestizo, ~10 kg, sin registro; lo trae un vecino"],
        description="Datos disponibles del paciente y su propietario, en texto libre.")
    emergencia_id: str | None = Field(
        None, description="Opcional; si no se indica, el sistema lo genera.")


class EmergenciaOut(BaseModel):
    emergencia_id: str
    mascota_id: str | None
    motivo: str
    datos_paciente: str | None
    estado: str = Field(examples=["IDENTIFICADA"], description="`IDENTIFICADA` o `EN_ATENCION`.")
    identificada_en: datetime = Field(description="Fecha y hora con zona horaria.")
    atendida_en: datetime | None = Field(description="Solo si el estado es `EN_ATENCION`.")


class EmergenciaRegistradaOut(BaseModel):
    emergencia: EmergenciaOut
    protocolo_activado: bool
    notificacion: str = Field(
        examples=["notificado"],
        description="`notificado`, o `pendiente_de_notificar` si el aviso al veterinario "
                    "falló. El registro se conserva en ambos casos.")


class AvisoOut(BaseModel):
    emergencia_id: str
    mascota_id: str | None
    motivo: str
    identificada_en: datetime


# --- conversión del dominio a salida ---


def evaluacion_a_salida(regla: str, resultado: Any) -> EvaluacionOut:
    return EvaluacionOut(
        regla=regla, cumple=resultado.cumple, motivos=list(resultado.motivos))

def servicio_a_salida(servicio: ServicioVeterinario) -> ServicioOut:
    return ServicioOut(
        servicio_id=servicio.servicio_id, descripcion=servicio.descripcion,
        precio_mxn=str(servicio.precio.monto), capacidad=servicio.capacidad,
        habilitado=servicio.habilitado)


def propietario_a_salida(p: Propietario) -> PropietarioOut:
    return PropietarioOut(
        propietario_id=p.propietario_id, nombre=p.nombre, activo=p.activo,
        preferente=p.preferente)


def mascota_a_salida(m: Mascota) -> MascotaOut:
    return MascotaOut(
        mascota_id=m.mascota_id, propietario_id=m.propietario_id, nombre=m.nombre,
        especie=m.especie, raza=m.raza, sexo=m.sexo, fecha_nacimiento=m.fecha_nacimiento,
        peso_kg=str(m.peso_kg) if m.peso_kg is not None else None,
        alergias=list(m.alergias))


def cita_a_salida(cita: Cita, catalogo: Mapping[str, ServicioVeterinario]) -> CitaOut:
    return CitaOut(
        cita_id=cita.cita_id, propietario_id=cita.propietario_id, mascota_id=cita.mascota_id,
        estado=cita.estado.value,
        servicios=[LineaOut(servicio_id=ln.servicio_id, cantidad=ln.cantidad)
                   for ln in cita.lineas],
        fecha_solicitud=cita.fecha_solicitud, autorizada=cita.autorizada,
        promocion_activa=cita.promocion_activa, referencia=cita.referencia,
        total_mxn=str(cita.total(catalogo).monto))


def vacunacion_a_salida(v: Vacunacion) -> VacunacionOut:
    return VacunacionOut(
        vacunacion_id=v.vacunacion_id, mascota_id=v.mascota_id, vacuna=v.vacuna,
        fecha_aplicacion=v.fecha_aplicacion, lote=v.lote)


def seguimiento_a_salida(s: SeguimientoDeVacuna) -> SeguimientoOut:
    return SeguimientoOut(
        vacuna=s.vacuna, ultima_aplicacion=s.ultima_aplicacion, estado=s.estado.value,
        proxima_aplicacion=s.proxima_aplicacion, es_refuerzo=s.es_refuerzo,
        motivos=list(s.motivos))


def esquema_a_salida(e: EsquemaDeVacunacion) -> EsquemaOut:
    return EsquemaOut(
        vacuna=e.vacuna, frecuencia_dias=e.frecuencia_dias,
        requiere_refuerzo=e.requiere_refuerzo, validado=e.validado)



def emergencia_a_salida(e: Emergencia) -> EmergenciaOut:
    return EmergenciaOut(
        emergencia_id=e.emergencia_id, mascota_id=e.mascota_id, motivo=e.motivo,
        datos_paciente=e.datos_paciente, estado=e.estado.value,
        identificada_en=e.identificada_en, atendida_en=e.atendida_en)
