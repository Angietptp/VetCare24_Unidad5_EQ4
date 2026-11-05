"""Casos de uso de Vacunación (CU-03).

Registrar una vacuna NUNCA depende del esquema (ADR-05, opción b): el registro se guarda
siempre; el seguimiento (próxima aplicación y refuerzo) se calcula aparte y, si el esquema no
está definido y validado, queda como "pendiente de esquema" en lugar de ser un error.
El seguimiento no se guarda: se calcula cada vez a partir del historial.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from vetcare24.application.comandos import RegistrarVacunacion
from vetcare24.application.control_de_acceso import Permiso, Rol, exigir
from vetcare24.application.despachador import Despachador
from vetcare24.application.errores import NoEncontrado, YaExiste
from vetcare24.application.servicios import FabricaDeUnidades, nuevo_id
from vetcare24.domain.ciclo_de_vida import ahora_utc
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.seguimiento_vacunacion import (
    SeguimientoDeVacuna,
    ServicioDeSeguimientoDeVacunacion,
)
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion, normalizar_vacuna


@dataclass(frozen=True)
class ResultadoDeVacunacion:
    vacunacion: Vacunacion
    seguimiento: SeguimientoDeVacuna


@dataclass(frozen=True)
class RecordatorioDeVacuna:
    """Una vacuna vencida o por vencer, lista para avisar al propietario (NB-17, A-05).
    El envío no está definido en el BRD: aquí solo se identifica quién y qué."""

    mascota_id: str
    propietario_id: str
    vacuna: str
    proxima_aplicacion: date
    es_refuerzo: bool
    vencida: bool


class ServicioDeVacunacion:
    def __init__(
        self,
        fabrica: FabricaDeUnidades,
        despachador: Despachador,
        seguimiento: ServicioDeSeguimientoDeVacunacion | None = None,
        reloj: Callable[[], datetime] = ahora_utc,
        generar_id: Callable[[str], str] = nuevo_id,
    ) -> None:
        self._fabrica = fabrica
        self._despachador = despachador
        self._seguimiento = seguimiento or ServicioDeSeguimientoDeVacunacion()
        self._reloj = reloj
        self._generar_id = generar_id

    def registrar(self, rol: Rol, comando: RegistrarVacunacion) -> ResultadoDeVacunacion:
        exigir(rol, Permiso.REGISTRAR_VACUNACION)
        with self._fabrica() as uow:
            mascota = uow.mascotas.obtener(comando.mascota_id)
            if mascota is None:
                raise NoEncontrado("mascota", comando.mascota_id)
            if comando.vacunacion_id and uow.vacunaciones.obtener(comando.vacunacion_id):
                raise YaExiste("vacunación", comando.vacunacion_id)
            vacunacion = Vacunacion.registrar(
                vacunacion_id=comando.vacunacion_id or self._generar_id("VAC"),
                mascota=mascota, vacuna=comando.vacuna,
                fecha_aplicacion=comando.fecha_aplicacion, lote=comando.lote,
                ocurrido_en=self._reloj(),
            )
            uow.vacunaciones.agregar(vacunacion)  # solo se agrega: el historial se conserva
            eventos = vacunacion.extraer_eventos()
            for evento in eventos:
                uow.eventos.agregar(evento)
            historial = uow.vacunaciones.de_mascota(mascota.mascota_id)
            esquemas = uow.esquemas.todos()
            uow.commit()
        self._despachador.publicar(eventos)
        propio = next(
            s for s in self._seguimiento.seguimiento(historial, esquemas)
            if normalizar_vacuna(s.vacuna) == vacunacion.clave
        )
        return ResultadoDeVacunacion(vacunacion, propio)

    def historial(self, rol: Rol, mascota_id: str) -> list[Vacunacion]:
        exigir(rol, Permiso.CONSULTAR_VACUNACION)
        with self._fabrica() as uow:
            if uow.mascotas.obtener(mascota_id) is None:
                raise NoEncontrado("mascota", mascota_id)
            return uow.vacunaciones.de_mascota(mascota_id)

    def seguimiento(self, rol: Rol, mascota_id: str) -> list[SeguimientoDeVacuna]:
        exigir(rol, Permiso.CONSULTAR_VACUNACION)
        with self._fabrica() as uow:
            if uow.mascotas.obtener(mascota_id) is None:
                raise NoEncontrado("mascota", mascota_id)
            historial = uow.vacunaciones.de_mascota(mascota_id)
            esquemas = uow.esquemas.todos()
        return self._seguimiento.seguimiento(historial, esquemas)

    def proximas(
        self, rol: Rol, *, hoy: date, dentro_de_dias: int
    ) -> list[RecordatorioDeVacuna]:
        """Vacunas vencidas o que vencen en los próximos `dentro_de_dias` días, de todas las
        mascotas (para generar recordatorios)."""
        exigir(rol, Permiso.CONSULTAR_VACUNACION)
        if isinstance(dentro_de_dias, bool) or not isinstance(dentro_de_dias, int) \
                or dentro_de_dias < 0:
            raise InvarianteViolada(
                "VENTANA_INVALIDA", "Los días de anticipación deben ser un entero de 0 o más")
        with self._fabrica() as uow:
            esquemas = uow.esquemas.todos()
            por_mascota: dict[str, list[Vacunacion]] = {}
            for vacunacion in uow.vacunaciones.todas():
                por_mascota.setdefault(vacunacion.mascota_id, []).append(vacunacion)
            propietarios: dict[str, str] = {}
            for mascota_id in por_mascota:
                mascota = uow.mascotas.obtener(mascota_id)
                if mascota is not None:
                    propietarios[mascota_id] = mascota.propietario_id
        avisos = []
        for mascota_id, historial in por_mascota.items():
            for s in self._seguimiento.seguimiento(historial, esquemas):
                proxima = s.proxima_aplicacion
                if proxima is None or not self._seguimiento.vence_pronto(s, hoy, dentro_de_dias):
                    continue
                avisos.append(RecordatorioDeVacuna(
                    mascota_id, propietarios[mascota_id], s.vacuna, proxima,
                    bool(s.es_refuerzo), proxima < hoy))
        return sorted(avisos, key=lambda a: (a.proxima_aplicacion, a.mascota_id, a.vacuna))

    def listar_esquemas(self, rol: Rol) -> list[EsquemaDeVacunacion]:
        exigir(rol, Permiso.CONSULTAR_VACUNACION)
        with self._fabrica() as uow:
            return sorted(uow.esquemas.todos().values(), key=lambda e: e.clave)
