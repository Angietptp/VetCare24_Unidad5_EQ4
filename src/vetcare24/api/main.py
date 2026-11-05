"""Punto de entrada de la API. FastAPI genera el contrato OpenAPI automáticamente."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as ErrorHttp

from vetcare24 import __version__
from vetcare24.api.errores_http import (
    RolDesconocido,
    RolNoIndicado,
    cuerpo_de_error,
    error_http,
    solicitud_invalida,
    traducir,
)
from vetcare24.api.rutas import router
from vetcare24.application.despachador import Despachador, RegistroDeEventos
from vetcare24.application.errores import ErrorDeAplicacion
from vetcare24.application.servicios import ServicioDeCitas, ServicioDeRegistro
from vetcare24.application.servicios_emergencias import ServicioDeEmergencias
from vetcare24.application.servicios_vacunacion import ServicioDeVacunacion
from vetcare24.domain.errors import ErrorDeDominio
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.esquema import crear_esquema
from vetcare24.infrastructure.notificador import BandejaDeAvisos
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

DESCRIPCION = (
    "Lógica de negocio de la clínica veterinaria VetCare 24 (CU-01: registrar y gestionar "
    "citas; CU-03: vacunación; CU-05: emergencias sin cita). Cada solicitud indica el rol "
    "en el encabezado `X-Rol`. "
    "Errores (siempre con "
    "`error.codigo`, `error.mensaje`, `error.detalles` y `error.motivos`): 400 solicitud mal "
    "formada o rol desconocido, 401 falta rol, 403 sin permiso, 404 no existe, 409 transición "
    "inválida, capacidad insuficiente o duplicado, 422 regla de negocio no cumplida."
)


def _manejar_error_de_negocio(_: Request, error: Exception) -> JSONResponse:
    codigo, cuerpo = traducir(error) or (500, cuerpo_de_error("ERROR_INTERNO", "Error interno"))
    return JSONResponse(status_code=codigo, content=cuerpo)


def _manejar_solicitud_invalida(_: Request, error: RequestValidationError) -> JSONResponse:
    codigo, cuerpo = solicitud_invalida(list(error.errors()))  # D-13: 400 payload mal formado
    return JSONResponse(status_code=codigo, content=cuerpo)


def _manejar_error_http(_: Request, error: ErrorHttp) -> JSONResponse:
    codigo, cuerpo = error_http(error.status_code)  # 404/405 con el mismo formato que el resto
    return JSONResponse(status_code=codigo, content=cuerpo, headers=error.headers)


def create_app(database_url: str | None = None, *, preparar_esquema: bool = True) -> FastAPI:
    url = database_url or load_settings().database_url

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        if preparar_esquema:  # idempotente (J-01): crea las tablas que falten
            conexion = conectar(url)
            try:
                crear_esquema(conexion)
            finally:
                conexion.cerrar()
        yield

    app = FastAPI(
        title="VetCare 24 API",
        version=__version__,
        description=DESCRIPCION,
        lifespan=ciclo_de_vida,
    )

    def fabrica() -> UnidadDeTrabajoSql:
        return UnidadDeTrabajoSql(url)

    despachador = Despachador()
    app.state.eventos = RegistroDeEventos()
    despachador.suscribir(EventoDeDominio, app.state.eventos)
    app.state.citas = ServicioDeCitas(fabrica, despachador)
    app.state.registro = ServicioDeRegistro(fabrica)
    app.state.vacunacion = ServicioDeVacunacion(fabrica, despachador)
    app.state.notificador = BandejaDeAvisos()
    app.state.emergencias = ServicioDeEmergencias(fabrica, despachador, app.state.notificador)

    for tipo in (ErrorDeDominio, ErrorDeAplicacion, RolNoIndicado, RolDesconocido):
        app.add_exception_handler(tipo, _manejar_error_de_negocio)
    app.add_exception_handler(RequestValidationError, _manejar_solicitud_invalida)
    app.add_exception_handler(ErrorHttp, _manejar_error_http)

    @app.get("/health", tags=["Sistema"], summary="Estado del servicio")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
