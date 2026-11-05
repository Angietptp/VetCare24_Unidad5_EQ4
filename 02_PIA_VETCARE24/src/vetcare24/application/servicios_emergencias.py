"""Casos de uso de Emergencias (CU-05, US20, NB-19, R-06).

`atender_emergencia` (nombre del informe) registra la emergencia SIN exigir cita, activa el
protocolo y, DESPUÉS de confirmar el registro, notifica al veterinario. Si la notificación
falla, el registro NO se deshace: el resultado indica "pendiente de notificar" (informe, CU-05).
El personal clínico inicia después la atención (A-01).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from vetcare24.application.comandos import AtenderEmergencia
from vetcare24.application.control_de_acceso import Permiso, Rol, exigir
from vetcare24.application.despachador import Despachador
from vetcare24.application.errores import NoEncontrado, YaExiste
from vetcare24.application.puertos import NotificadorDeVeterinario
from vetcare24.application.servicios import FabricaDeUnidades, nuevo_id
from vetcare24.domain.ciclo_de_vida import ahora_utc
from vetcare24.domain.cita import EstadoCita
from vetcare24.domain.emergencia import CicloDeVidaDeEmergencia, Emergencia, EstadoEmergencia
from vetcare24.domain.reglas_emergencia import MascotaParaAtencion, atencion_permitida
from vetcare24.domain.specification import Evaluacion

registro = logging.getLogger(__name__)
TIPO = "emergencia"


class EstadoDeNotificacion(StrEnum):
    NOTIFICADO = "notificado"
    PENDIENTE = "pendiente_de_notificar"


@dataclass(frozen=True)
class ResultadoDeEmergencia:
    """Informe: identificador, protocolo activado y resultado de la notificación."""

    emergencia: Emergencia
    notificacion: EstadoDeNotificacion

    @property
    def protocolo_activado(self) -> bool:
        return True  # registrar la emergencia ES activar el protocolo (BPMN, N-03)


class ServicioDeEmergencias:
    def __init__(
        self,
        fabrica: FabricaDeUnidades,
        despachador: Despachador,
        notificador: NotificadorDeVeterinario,
        reloj: Callable[[], datetime] = ahora_utc,
        generar_id: Callable[[str], str] = nuevo_id,
    ) -> None:
        self._fabrica = fabrica
        self._despachador = despachador
        self._notificador = notificador
        self._ciclo = CicloDeVidaDeEmergencia(reloj)
        self._generar_id = generar_id
        self._atencion_permitida = atencion_permitida()

    def atender_emergencia(self, rol: Rol, comando: AtenderEmergencia) -> ResultadoDeEmergencia:
        exigir(rol, Permiso.ATENDER_EMERGENCIA)  # antes de abrir la transacción (informe)
        with self._fabrica() as uow:
            mascota = None
            if comando.mascota_id is not None:
                mascota = uow.mascotas.obtener(comando.mascota_id)
                if mascota is None:
                    raise NoEncontrado("mascota", comando.mascota_id)
            if comando.emergencia_id and uow.emergencias.obtener(comando.emergencia_id):
                raise YaExiste(TIPO, comando.emergencia_id)
            emergencia = self._ciclo.identificar(  # no se consulta ninguna cita (R-06)
                emergencia_id=comando.emergencia_id or self._generar_id("EMER"),
                motivo=comando.motivo, mascota=mascota, datos_paciente=comando.datos_paciente)
            uow.emergencias.agregar(emergencia)
            eventos = emergencia.extraer_eventos()
            for evento in eventos:
                uow.eventos.agregar(evento)
            uow.commit()
        self._despachador.publicar(eventos)
        return ResultadoDeEmergencia(emergencia, self._notificar(emergencia))

    def _notificar(self, emergencia: Emergencia) -> EstadoDeNotificacion:
        """Después del commit (informe): un fallo aquí no deshace el registro."""
        try:
            self._notificador.notificar(emergencia)
        except Exception:
            registro.exception("No se pudo notificar al veterinario de %s",
                               emergencia.emergencia_id)
            return EstadoDeNotificacion.PENDIENTE
        return EstadoDeNotificacion.NOTIFICADO

    def iniciar_atencion(self, rol: Rol, emergencia_id: str) -> Emergencia:
        exigir(rol, Permiso.INICIAR_ATENCION_EMERGENCIA)
        with self._fabrica() as uow:
            emergencia = uow.emergencias.obtener(emergencia_id)
            if emergencia is None:
                raise NoEncontrado(TIPO, emergencia_id)
            self._ciclo.iniciar_atencion(emergencia)
            uow.emergencias.guardar(emergencia)
            uow.commit()
        return emergencia  # D-14 no define un evento para este paso (N-06)

    def obtener(self, rol: Rol, emergencia_id: str) -> Emergencia:
        exigir(rol, Permiso.CONSULTAR_EMERGENCIA)
        with self._fabrica() as uow:
            emergencia = uow.emergencias.obtener(emergencia_id)
        if emergencia is None:
            raise NoEncontrado(TIPO, emergencia_id)
        return emergencia

    def listar(
        self, rol: Rol, *, estado: EstadoEmergencia | None = None, mascota_id: str | None = None,
    ) -> list[Emergencia]:
        exigir(rol, Permiso.CONSULTAR_EMERGENCIA)
        with self._fabrica() as uow:
            if mascota_id is not None and uow.mascotas.obtener(mascota_id) is None:
                raise NoEncontrado("mascota", mascota_id)
            return uow.emergencias.listar(estado=estado, mascota_id=mascota_id)

    def evaluar_atencion(self, rol: Rol, mascota_id: str) -> Evaluacion:
        """R-06: ¿la mascota puede recibir atención? TieneCitaConfirmada OR
        TieneEmergenciaActiva. Solo consulta (no cambia nada)."""
        exigir(rol, Permiso.CONSULTAR_EMERGENCIA)
        with self._fabrica() as uow:
            if uow.mascotas.obtener(mascota_id) is None:
                raise NoEncontrado("mascota", mascota_id)
            contexto = MascotaParaAtencion.de(
                mascota_id, uow.citas.listar(estado=EstadoCita.CONFIRMADA),
                uow.emergencias.listar(mascota_id=mascota_id))
        return self._atencion_permitida.evaluar(contexto)
