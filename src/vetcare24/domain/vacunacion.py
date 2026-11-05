"""Vacunación (CU-03): el historial de vacunas de una mascota y los esquemas de referencia.

- `Vacunacion` es una aplicación de una vacuna a una mascota. El historial se conserva siempre
  (R-11, NB-14): solo se agregan registros, nunca se modifican ni se borran.
- `EsquemaDeVacunacion` define, por tipo de vacuna, cada cuántos días corresponde la siguiente
  aplicación y si esa siguiente aplicación es un refuerzo (R-12, R-13, NB-15, NB-16). Es un
  concepto de referencia: registrar una vacuna NO depende de él (ADR-05, opción b).
"""

from __future__ import annotations

from datetime import date, datetime

from vetcare24.domain._validacion import exigir_booleano, exigir_entero, exigir_texto
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.eventos import EventoDeDominio, VacunacionRegistrada
from vetcare24.domain.mascota import Mascota

# Límite técnico (100 años) para que una frecuencia absurda no desborde las fechas.
FRECUENCIA_MAXIMA_DIAS = 36_500


def _limpiar(texto: str) -> str:
    return " ".join(texto.split())


def normalizar_vacuna(texto: str) -> str:
    """Clave para comparar nombres de vacuna: sin espacios de más ni mayúsculas."""
    exigir_texto(texto, "VACUNA_VACIA", "La vacuna")
    return _limpiar(texto).casefold()


class Vacunacion:
    def __init__(
        self,
        *,
        vacunacion_id: str,
        mascota_id: str,
        vacuna: str,
        fecha_aplicacion: date,
        lote: str | None = None,
    ) -> None:
        exigir_texto(vacunacion_id, "ID_VACIO", "El id de la vacunación")
        exigir_texto(mascota_id, "MASCOTA_REQUERIDA", "La mascota")
        exigir_texto(vacuna, "VACUNA_VACIA", "La vacuna")
        if not isinstance(fecha_aplicacion, date) or isinstance(fecha_aplicacion, datetime):
            raise InvarianteViolada(
                "FECHA_INVALIDA", "La fecha de aplicación debe ser una fecha (sin hora)")
        if lote is not None:
            exigir_texto(lote, "LOTE_VACIO", "El lote")
        self._vacunacion_id = vacunacion_id
        self._mascota_id = mascota_id
        self._vacuna = _limpiar(vacuna)
        self._fecha_aplicacion = fecha_aplicacion
        self._lote = _limpiar(lote) if lote is not None else None
        self._eventos: list[EventoDeDominio] = []

    @classmethod
    def registrar(
        cls,
        *,
        vacunacion_id: str,
        mascota: Mascota,
        vacuna: str,
        fecha_aplicacion: date,
        ocurrido_en: datetime,
        lote: str | None = None,
    ) -> Vacunacion:
        """Registra una aplicación NUEVA y deja el evento `VacunacionRegistrada`."""
        vacunacion = cls(
            vacunacion_id=vacunacion_id, mascota_id=mascota.mascota_id, vacuna=vacuna,
            fecha_aplicacion=fecha_aplicacion, lote=lote,
        )
        vacunacion._eventos.append(VacunacionRegistrada(
            ocurrido_en=ocurrido_en,
            vacunacion_id=vacunacion.vacunacion_id,
            mascota_id=vacunacion.mascota_id,
            vacuna=vacunacion.vacuna,
            fecha_aplicacion=vacunacion.fecha_aplicacion,
            lote=vacunacion.lote,
        ))
        return vacunacion

    @property
    def vacunacion_id(self) -> str:
        return self._vacunacion_id

    @property
    def mascota_id(self) -> str:
        return self._mascota_id

    @property
    def vacuna(self) -> str:
        return self._vacuna

    @property
    def clave(self) -> str:
        return normalizar_vacuna(self._vacuna)

    @property
    def fecha_aplicacion(self) -> date:
        return self._fecha_aplicacion

    @property
    def lote(self) -> str | None:
        return self._lote

    def extraer_eventos(self) -> tuple[EventoDeDominio, ...]:
        """Entrega los eventos pendientes una sola vez (como la Cita)."""
        pendientes = tuple(self._eventos)
        self._eventos.clear()
        return pendientes

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Vacunacion) and otro._vacunacion_id == self._vacunacion_id

    def __hash__(self) -> int:
        return hash(self._vacunacion_id)

    def __repr__(self) -> str:
        return f"Vacunacion({self._vacunacion_id!r}, {self._vacuna!r}, {self._fecha_aplicacion})"


class EsquemaDeVacunacion:
    """Frecuencia y refuerzo de un tipo de vacuna. Solo se usa si está `validado` (R-12)."""

    def __init__(
        self, *, vacuna: str, frecuencia_dias: int, requiere_refuerzo: bool, validado: bool
    ) -> None:
        exigir_texto(vacuna, "VACUNA_VACIA", "La vacuna del esquema")
        exigir_entero(frecuencia_dias, minimo=1, codigo="FRECUENCIA_INVALIDA",
                      nombre="La frecuencia en días")
        if frecuencia_dias > FRECUENCIA_MAXIMA_DIAS:
            raise InvarianteViolada(
                "FRECUENCIA_INVALIDA",
                f"La frecuencia no puede pasar de {FRECUENCIA_MAXIMA_DIAS} días")
        exigir_booleano(requiere_refuerzo, "REFUERZO_INVALIDO", "requiere_refuerzo")
        exigir_booleano(validado, "VALIDADO_INVALIDO", "validado")
        self.vacuna = _limpiar(vacuna)
        self.frecuencia_dias = frecuencia_dias
        self.requiere_refuerzo = requiere_refuerzo
        self.validado = validado

    @property
    def clave(self) -> str:
        return normalizar_vacuna(self.vacuna)

    def __eq__(self, otro: object) -> bool:
        return (
            isinstance(otro, EsquemaDeVacunacion)
            and (otro.clave, otro.frecuencia_dias, otro.requiere_refuerzo, otro.validado)
            == (self.clave, self.frecuencia_dias, self.requiere_refuerzo, self.validado)
        )

    def __hash__(self) -> int:
        return hash((self.clave, self.frecuencia_dias, self.requiere_refuerzo, self.validado))

    def __repr__(self) -> str:
        return (f"EsquemaDeVacunacion({self.vacuna!r}, cada {self.frecuencia_dias} días, "
                f"refuerzo={self.requiere_refuerzo}, validado={self.validado})")
