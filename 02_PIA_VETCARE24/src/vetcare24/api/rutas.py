"""Endpoints REST de CU-01 (citas), CU-03 (vacunación) y CU-05 (emergencias).

Cada endpoint solo traduce HTTP a un caso de uso y de vuelta: no hay reglas de negocio aquí.
El rol llega en el encabezado X-Rol (J-09); la autenticación queda fuera del dominio (ADR-04).
Nota: este módulo NO usa `from __future__ import annotations`, para que FastAPI lea los tipos.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status

from vetcare24.api.errores_http import RolDesconocido, RolNoIndicado
from vetcare24.api.esquemas import (
    AvisoOut,
    CitaIn,
    CitaOut,
    EmergenciaIn,
    EmergenciaOut,
    EmergenciaRegistradaOut,
    ErrorOut,
    EsquemaOut,
    EvaluacionOut,
    EventoOut,
    MascotaIn,
    MascotaOut,
    ModificarServiciosIn,
    PropietarioIn,
    PropietarioOut,
    RecordatorioOut,
    SeguimientoOut,
    ServicioOut,
    VacunacionIn,
    VacunacionOut,
    VacunacionRegistradaOut,
    cita_a_salida,
    emergencia_a_salida,
    esquema_a_salida,
    evaluacion_a_salida,
    mascota_a_salida,
    propietario_a_salida,
    seguimiento_a_salida,
    servicio_a_salida,
    vacunacion_a_salida,
)
from vetcare24.application.comandos import (
    AtenderEmergencia,
    ModificarCita,
    RegistrarMascota,
    RegistrarPropietario,
    RegistrarVacunacion,
    SolicitarCita,
)
from vetcare24.application.control_de_acceso import Permiso, Rol, exigir
from vetcare24.application.servicios import ReglaEvaluable, ServicioDeCitas, ServicioDeRegistro
from vetcare24.application.servicios_emergencias import ServicioDeEmergencias
from vetcare24.application.servicios_vacunacion import ServicioDeVacunacion
from vetcare24.domain.cita import Cita, EstadoCita
from vetcare24.domain.emergencia import EstadoEmergencia

router = APIRouter()

ERRORES = {
    400: {"model": ErrorOut, "description": "Solicitud mal formada o rol desconocido"},
    401: {"model": ErrorOut, "description": "Falta el encabezado X-Rol"},
    403: {"model": ErrorOut, "description": "El rol no tiene permiso"},
    404: {"model": ErrorOut, "description": "No existe el recurso"},
    409: {"model": ErrorOut,
          "description": "Transición inválida, capacidad insuficiente o recurso duplicado"},
    422: {"model": ErrorOut, "description": "Regla de negocio no cumplida"},
}


# --- dependencias ---

def rol_actual(
    x_rol: Annotated[str | None, Header(
        alias="X-Rol",
        description="Rol de quien opera: recepcion, veterinario, personal_clinico o responsable.",
    )] = None,
) -> Rol:
    if not x_rol:
        raise RolNoIndicado()
    try:
        return Rol(x_rol.strip().lower())
    except ValueError as error:
        raise RolDesconocido(x_rol) from error


def servicio_de_citas(request: Request) -> ServicioDeCitas:
    return request.app.state.citas


def servicio_de_registro(request: Request) -> ServicioDeRegistro:
    return request.app.state.registro


def servicio_de_vacunacion(request: Request) -> ServicioDeVacunacion:
    return request.app.state.vacunacion


def servicio_de_emergencias(request: Request) -> ServicioDeEmergencias:
    return request.app.state.emergencias


RolActual = Annotated[Rol, Depends(rol_actual)]
Citas = Annotated[ServicioDeCitas, Depends(servicio_de_citas)]
Registro = Annotated[ServicioDeRegistro, Depends(servicio_de_registro)]
Vacunas = Annotated[ServicioDeVacunacion, Depends(servicio_de_vacunacion)]
Emergencias = Annotated[ServicioDeEmergencias, Depends(servicio_de_emergencias)]


def _salida(cita: Cita, citas: ServicioDeCitas) -> CitaOut:
    return cita_a_salida(cita, citas.catalogo())


def _servicios(lineas) -> tuple[tuple[str, int], ...]:
    return tuple((ln.servicio_id, ln.cantidad) for ln in lineas)


# --- catálogo ---

@router.get("/servicios", response_model=list[ServicioOut], tags=["Catálogo"],
            summary="Listar el catálogo de servicios", responses=ERRORES)
def listar_servicios(rol: RolActual, registro: Registro):
    return [servicio_a_salida(s) for s in registro.listar_servicios(rol)]


# --- propietarios y mascotas ---

@router.post("/propietarios", response_model=PropietarioOut, tags=["Registro"],
             status_code=status.HTTP_201_CREATED, summary="Registrar un propietario",
             responses=ERRORES)
def registrar_propietario(datos: PropietarioIn, rol: RolActual, registro: Registro):
    propietario = registro.registrar_propietario(rol, RegistrarPropietario(
        nombre=datos.nombre, activo=datos.activo, preferente=datos.preferente,
        propietario_id=datos.propietario_id))
    return propietario_a_salida(propietario)


@router.get("/propietarios/{propietario_id}", response_model=PropietarioOut, tags=["Registro"],
            summary="Consultar un propietario", responses=ERRORES)
def obtener_propietario(propietario_id: str, rol: RolActual, registro: Registro):
    return propietario_a_salida(registro.obtener_propietario(rol, propietario_id))


@router.post("/mascotas", response_model=MascotaOut, tags=["Registro"],
             status_code=status.HTTP_201_CREATED, summary="Registrar una mascota",
             responses=ERRORES)
def registrar_mascota(datos: MascotaIn, rol: RolActual, registro: Registro):
    mascota = registro.registrar_mascota(rol, RegistrarMascota(
        propietario_id=datos.propietario_id, nombre=datos.nombre, especie=datos.especie,
        raza=datos.raza, sexo=datos.sexo, fecha_nacimiento=datos.fecha_nacimiento,
        peso_kg=datos.peso_kg, alergias=tuple(datos.alergias), mascota_id=datos.mascota_id))
    return mascota_a_salida(mascota)


@router.get("/mascotas/{mascota_id}", response_model=MascotaOut, tags=["Registro"],
            summary="Consultar una mascota", responses=ERRORES)
def obtener_mascota(mascota_id: str, rol: RolActual, registro: Registro):
    return mascota_a_salida(registro.obtener_mascota(rol, mascota_id))


# --- citas ---

@router.post("/citas", response_model=CitaOut, tags=["Citas"],
             status_code=status.HTTP_201_CREATED, summary="Solicitar una cita",
             responses=ERRORES)
def solicitar_cita(datos: CitaIn, rol: RolActual, citas: Citas):
    cita = citas.solicitar(rol, SolicitarCita(
        propietario_id=datos.propietario_id, mascota_id=datos.mascota_id,
        servicios=_servicios(datos.servicios), fecha_solicitud=datos.fecha_solicitud,
        autorizada=datos.autorizada, promocion_activa=datos.promocion_activa,
        referencia=datos.referencia, cita_id=datos.cita_id))
    return _salida(cita, citas)


@router.get("/citas", response_model=list[CitaOut], tags=["Citas"],
            summary="Listar citas (filtros opcionales)", responses=ERRORES)
def listar_citas(
    rol: RolActual, citas: Citas,
    estado: Annotated[EstadoCita | None, Query(description="Filtra por estado.")] = None,
    propietario_id: Annotated[str | None, Query(description="Filtra por propietario.")] = None,
):
    lista = citas.listar(rol, estado=estado, propietario_id=propietario_id)
    catalogo = citas.catalogo()
    return [cita_a_salida(c, catalogo) for c in lista]


@router.get("/citas/{cita_id}", response_model=CitaOut, tags=["Citas"],
            summary="Consultar una cita", responses=ERRORES)
def obtener_cita(cita_id: str, rol: RolActual, citas: Citas):
    return _salida(citas.obtener(rol, cita_id), citas)


@router.put("/citas/{cita_id}/servicios", response_model=CitaOut, tags=["Citas"],
            summary="Modificar los servicios de una cita", responses=ERRORES)
def modificar_cita(cita_id: str, datos: ModificarServiciosIn, rol: RolActual, citas: Citas):
    cita = citas.modificar(rol, ModificarCita(cita_id, _servicios(datos.servicios)))
    return _salida(cita, citas)


@router.post("/citas/{cita_id}/confirmar", response_model=CitaOut, tags=["Citas"],
             summary="Confirmar una cita (SOLICITADA → CONFIRMADA)", responses=ERRORES)
def confirmar_cita(cita_id: str, rol: RolActual, citas: Citas):
    return _salida(citas.confirmar(rol, cita_id), citas)


@router.post("/citas/{cita_id}/realizar", response_model=CitaOut, tags=["Citas"],
             summary="Realizar una cita (CONFIRMADA → REALIZADA)", responses=ERRORES)
def realizar_cita(cita_id: str, rol: RolActual, citas: Citas):
    return _salida(citas.realizar(rol, cita_id), citas)


@router.post("/citas/{cita_id}/cancelar", response_model=CitaOut, tags=["Citas"],
             summary="Cancelar una cita", responses=ERRORES)
def cancelar_cita(cita_id: str, rol: RolActual, citas: Citas):
    return _salida(citas.cancelar(rol, cita_id), citas)


# --- evaluaciones y eventos ---

@router.get("/citas/{cita_id}/evaluaciones/{regla}", response_model=EvaluacionOut,
            tags=["Evaluaciones"], summary="Evaluar una regla de elegibilidad sobre una cita",
            description="`procesamiento`: propietario activo, cita con servicios y autorizada "
                        "(D-03). `beneficio`: propietario preferente, total de al menos "
                        "1,500 MXN y sin promoción activa (extensión del paquete, D-05). "
                        "No modifica nada: responde 200 con `cumple` y los `motivos`.",
            responses=ERRORES)
def evaluar_cita(cita_id: str, regla: ReglaEvaluable, rol: RolActual, citas: Citas):
    return evaluacion_a_salida(regla.value, citas.evaluar(rol, cita_id, regla))


@router.get("/eventos", response_model=list[EventoOut], tags=["Eventos"],
            summary="Listar los eventos de dominio guardados",
            description="Eventos publicados por las citas (D-14), en el orden en que ocurrieron.",
            responses=ERRORES)
def listar_eventos(rol: RolActual, citas: Citas):
    return citas.listar_eventos(rol)


# --- vacunación (CU-03) ---

@router.post("/mascotas/{mascota_id}/vacunaciones", response_model=VacunacionRegistradaOut,
             status_code=status.HTTP_201_CREATED, tags=["Vacunación"],
             summary="Registrar la aplicación de una vacuna",
             description="Solo el veterinario. El registro se guarda SIEMPRE: no depende del "
                         "esquema de la vacuna. Junto con el registro se responde el "
                         "seguimiento (próxima aplicación y si es refuerzo); si la vacuna no "
                         "tiene un esquema definido y validado, el seguimiento queda "
                         "`pendiente_de_esquema` (no es un error). El historial no se "
                         "modifica ni se borra.",
             responses=ERRORES)
def registrar_vacunacion(mascota_id: str, datos: VacunacionIn, rol: RolActual, vacunas: Vacunas):
    resultado = vacunas.registrar(rol, RegistrarVacunacion(
        mascota_id=mascota_id, vacuna=datos.vacuna, fecha_aplicacion=datos.fecha_aplicacion,
        lote=datos.lote, vacunacion_id=datos.vacunacion_id))
    return VacunacionRegistradaOut(
        vacunacion=vacunacion_a_salida(resultado.vacunacion),
        seguimiento=seguimiento_a_salida(resultado.seguimiento))


@router.get("/mascotas/{mascota_id}/vacunaciones", response_model=list[VacunacionOut],
            tags=["Vacunación"], summary="Historial de vacunas de una mascota",
            description="De la más antigua a la más reciente.", responses=ERRORES)
def historial_de_vacunas(mascota_id: str, rol: RolActual, vacunas: Vacunas):
    return [vacunacion_a_salida(v) for v in vacunas.historial(rol, mascota_id)]


@router.get("/mascotas/{mascota_id}/vacunaciones/seguimiento",
            response_model=list[SeguimientoOut], tags=["Vacunación"],
            summary="Seguimiento de las vacunas de una mascota",
            description="Una fila por tipo de vacuna, con la próxima aplicación y si es "
                        "refuerzo. Se calcula en cada consulta a partir del historial.",
            responses=ERRORES)
def seguimiento_de_vacunas(mascota_id: str, rol: RolActual, vacunas: Vacunas):
    return [seguimiento_a_salida(s) for s in vacunas.seguimiento(rol, mascota_id)]


@router.get("/vacunas/proximas", response_model=list[RecordatorioOut], tags=["Vacunación"],
            summary="Vacunas vencidas o por vencer (para recordatorios)",
            description="De todas las mascotas: las vencidas y las que vencen en los próximos "
                        "`dias`. El BRD no define el envío de recordatorios; aquí solo se "
                        "identifica a quién avisar y qué vacuna.",
            responses=ERRORES)
def vacunas_proximas(
    rol: RolActual, vacunas: Vacunas,
    dias: Annotated[int, Query(description="Días de anticipación (0 = solo vencidas).")] = 30,
    fecha_de_referencia: Annotated[
        date | None, Query(description="Por omisión, hoy (AAAA-MM-DD).")] = None,
):
    avisos = vacunas.proximas(
        rol, hoy=fecha_de_referencia or date.today(), dentro_de_dias=dias)
    return [RecordatorioOut(
        mascota_id=a.mascota_id, propietario_id=a.propietario_id, vacuna=a.vacuna,
        proxima_aplicacion=a.proxima_aplicacion, es_refuerzo=a.es_refuerzo, vencida=a.vencida)
        for a in avisos]


@router.get("/esquemas-vacunacion", response_model=list[EsquemaOut], tags=["Vacunación"],
            summary="Esquemas de vacunación de referencia",
            description="Frecuencia y refuerzo de cada vacuna. Solo los validados se usan "
                        "para calcular el seguimiento (ADR-05).", responses=ERRORES)
def listar_esquemas(rol: RolActual, vacunas: Vacunas):
    return [esquema_a_salida(e) for e in vacunas.listar_esquemas(rol)]


# --- emergencias (CU-05) ---

@router.post("/emergencias", response_model=EmergenciaRegistradaOut,
             status_code=status.HTTP_201_CREATED, tags=["Emergencias"],
             summary="Registrar una emergencia (sin cita previa)",
             description="Solo Recepción (A-01). NO exige una cita (R-06, NB-19) y la mascota "
                         "es opcional (P3). Registrar la emergencia activa el protocolo y, "
                         "después de guardarla, se notifica al veterinario. Si el aviso falla, "
                         "la emergencia queda registrada y `notificacion` dice "
                         "`pendiente_de_notificar`.",
             responses=ERRORES)
def atender_emergencia(datos: EmergenciaIn, rol: RolActual, emergencias: Emergencias):
    resultado = emergencias.atender_emergencia(rol, AtenderEmergencia(
        motivo=datos.motivo, mascota_id=datos.mascota_id, datos_paciente=datos.datos_paciente,
        emergencia_id=datos.emergencia_id))
    return EmergenciaRegistradaOut(
        emergencia=emergencia_a_salida(resultado.emergencia),
        protocolo_activado=resultado.protocolo_activado,
        notificacion=resultado.notificacion.value)


@router.post("/emergencias/{emergencia_id}/iniciar-atencion", response_model=EmergenciaOut,
             tags=["Emergencias"], summary="Iniciar la atención (IDENTIFICADA → EN_ATENCION)",
             description="Solo el personal clínico (A-01, US20). Iniciarla dos veces responde "
                         "409 `TRANSICION_INVALIDA`.", responses=ERRORES)
def iniciar_atencion_de_emergencia(emergencia_id: str, rol: RolActual,
                                   emergencias: Emergencias):
    return emergencia_a_salida(emergencias.iniciar_atencion(rol, emergencia_id))


@router.get("/emergencias/{emergencia_id}", response_model=EmergenciaOut, tags=["Emergencias"],
            summary="Consultar una emergencia", responses=ERRORES)
def obtener_emergencia(emergencia_id: str, rol: RolActual, emergencias: Emergencias):
    return emergencia_a_salida(emergencias.obtener(rol, emergencia_id))


@router.get("/emergencias", response_model=list[EmergenciaOut], tags=["Emergencias"],
            summary="Listar emergencias (filtros opcionales)",
            description="De la más antigua a la más reciente.", responses=ERRORES)
def listar_emergencias(
    rol: RolActual, emergencias: Emergencias,
    estado: Annotated[EstadoEmergencia | None, Query(description="Filtra por estado.")] = None,
    mascota_id: Annotated[str | None, Query(description="Filtra por mascota.")] = None,
):
    return [emergencia_a_salida(e)
            for e in emergencias.listar(rol, estado=estado, mascota_id=mascota_id)]


@router.get("/mascotas/{mascota_id}/evaluaciones/atencion", response_model=EvaluacionOut,
            tags=["Evaluaciones"], summary="¿La mascota puede recibir atención?",
            description="R-06: `TieneCitaConfirmada OR TieneEmergenciaActiva`. No modifica "
                        "nada: responde 200 con `cumple` y los `motivos`.", responses=ERRORES)
def evaluar_atencion(mascota_id: str, rol: RolActual, emergencias: Emergencias):
    return evaluacion_a_salida("atencion", emergencias.evaluar_atencion(rol, mascota_id))


@router.get("/avisos-veterinario", response_model=list[AvisoOut], tags=["Emergencias"],
            summary="Avisos de emergencia enviados al veterinario",
            description="Bandeja en memoria del NotificadorDeVeterinario (el BRD no define el "
                        "canal). Se vacía al reiniciar la aplicación.", responses=ERRORES)
def avisos_al_veterinario(request: Request, rol: RolActual):
    exigir(rol, Permiso.CONSULTAR_EMERGENCIA)
    return [AvisoOut(emergencia_id=a.emergencia_id, mascota_id=a.mascota_id, motivo=a.motivo,
                     identificada_en=a.identificada_en)
            for a in request.app.state.notificador.avisos]
