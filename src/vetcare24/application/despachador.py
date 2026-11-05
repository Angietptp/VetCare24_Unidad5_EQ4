"""Despacho de Domain Events (D-14): publicación síncrona, después de guardar los cambios.

El despachador avisa a quien se suscribió a cada tipo de evento. Un manejador que falla NO
deshace lo ya guardado ni impide que los demás se enteren: el fallo se registra en `fallos`
(y en el log) para revisarlo. Quien se suscribe a `EventoDeDominio` recibe todos los eventos.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from vetcare24.domain.eventos import EventoDeDominio

logger = logging.getLogger(__name__)

Manejador = Callable[[EventoDeDominio], None]


@dataclass(frozen=True)
class FalloDeDespacho:
    evento: EventoDeDominio
    manejador: Manejador
    error: Exception


class Despachador:
    def __init__(self) -> None:
        self._suscripciones: list[tuple[type[EventoDeDominio], Manejador]] = []
        self.fallos: list[FalloDeDespacho] = []

    def suscribir(self, tipo: type[EventoDeDominio], manejador: Manejador) -> None:
        if not (isinstance(tipo, type) and issubclass(tipo, EventoDeDominio)):
            raise TypeError("Solo se puede suscribir a un tipo de EventoDeDominio")
        self._suscripciones.append((tipo, manejador))

    def publicar(self, eventos: Iterable[EventoDeDominio]) -> None:
        for evento in eventos:
            for tipo, manejador in tuple(self._suscripciones):
                if not isinstance(evento, tipo):
                    continue
                try:
                    manejador(evento)
                except Exception as error:
                    self.fallos.append(FalloDeDespacho(evento, manejador, error))
                    logger.exception("Falló el manejador de %s", evento.nombre)


@dataclass(frozen=True)
class EventoRegistrado:
    secuencia: int
    evento: EventoDeDominio


class RegistroDeEventos:
    """Manejador que guarda todos los eventos con un número de secuencia.

    Es el antecedente de la tabla `eventos_dominio` (Etapa 7) y sirve como evidencia.
    """

    def __init__(self) -> None:
        self._registrados: list[EventoRegistrado] = []

    def __call__(self, evento: EventoDeDominio) -> None:
        self._registrados.append(EventoRegistrado(len(self._registrados) + 1, evento))

    @property
    def registrados(self) -> tuple[EventoRegistrado, ...]:
        return tuple(self._registrados)

    def de_tipo(self, tipo: type[EventoDeDominio]) -> tuple[EventoRegistrado, ...]:
        return tuple(r for r in self._registrados if isinstance(r.evento, tipo))
