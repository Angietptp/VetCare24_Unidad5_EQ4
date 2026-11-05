"""Implementación del NotificadorDeVeterinario (puerto de salida de CU-05).

El BRD no define el canal (correo, SMS, pantalla). Esta implementación deja el aviso en una
bandeja en memoria y en el log: suficiente para demostrar que el aviso se solicita DESPUÉS del
commit y para consultarlo por la API (`GET /avisos-veterinario`). Al reiniciar la aplicación,
la bandeja se vacía (N-08). Cambiar de canal = escribir otra clase con el mismo método.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime

from vetcare24.application.puertos import NotificadorDeVeterinario
from vetcare24.domain.emergencia import Emergencia

registro = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvisoAlVeterinario:
    emergencia_id: str
    mascota_id: str | None
    motivo: str
    identificada_en: datetime


class BandejaDeAvisos(NotificadorDeVeterinario):
    def __init__(self) -> None:
        self._avisos: list[AvisoAlVeterinario] = []
        self._candado = threading.Lock()

    def notificar(self, emergencia: Emergencia) -> None:
        aviso = AvisoAlVeterinario(
            emergencia.emergencia_id, emergencia.mascota_id, emergencia.motivo,
            emergencia.identificada_en)
        with self._candado:
            self._avisos.append(aviso)
        registro.warning("EMERGENCIA %s: %s (mascota: %s)", aviso.emergencia_id, aviso.motivo,
                         aviso.mascota_id or "sin registrar")

    @property
    def avisos(self) -> tuple[AvisoAlVeterinario, ...]:
        with self._candado:
            return tuple(self._avisos)
