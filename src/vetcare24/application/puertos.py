"""Puertos: lo que la aplicación necesita de la persistencia, sin saber cómo se hace.

La capa de aplicación depende de estas interfaces; la infraestructura las implementa
(infrastructure/repositorios_sql.py). Así los casos de uso no conocen SQL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita
from vetcare24.domain.emergencia import Emergencia, EstadoEmergencia
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion


class RepositorioDeServicios(ABC):
    @abstractmethod
    def agregar(self, servicio: ServicioVeterinario) -> None: ...

    @abstractmethod
    def obtener(self, servicio_id: str) -> ServicioVeterinario | None: ...

    @abstractmethod
    def todos(self) -> dict[str, ServicioVeterinario]: ...


class RepositorioDePropietarios(ABC):
    @abstractmethod
    def agregar(self, propietario: Propietario) -> None: ...

    @abstractmethod
    def obtener(self, propietario_id: str) -> Propietario | None: ...

    @abstractmethod
    def todos(self) -> list[Propietario]: ...


class RepositorioDeMascotas(ABC):
    @abstractmethod
    def agregar(self, mascota: Mascota) -> None: ...

    @abstractmethod
    def obtener(self, mascota_id: str) -> Mascota | None: ...

    @abstractmethod
    def de_propietario(self, propietario_id: str) -> list[Mascota]: ...


class RepositorioDeCitas(ABC):
    @abstractmethod
    def agregar(self, cita: Cita) -> None: ...

    @abstractmethod
    def guardar(self, cita: Cita) -> None:
        """Guarda el estado y las líneas actuales de una cita que ya existe."""

    @abstractmethod
    def obtener(self, cita_id: str) -> Cita | None: ...

    @abstractmethod
    def listar(
        self, *, estado: EstadoCita | None = None, propietario_id: str | None = None
    ) -> list[Cita]: ...

    @abstractmethod
    def demanda_ocupada(self) -> dict[str, int]:
        """Unidades por servicio que ya consumen las citas CONFIRMADA y REALIZADA (D-08)."""

    @abstractmethod
    def contar(self) -> int: ...


class RepositorioDeVacunaciones(ABC):
    """Solo agrega y lee: el historial se conserva siempre (R-11, NB-14)."""

    @abstractmethod
    def agregar(self, vacunacion: Vacunacion) -> None: ...

    @abstractmethod
    def obtener(self, vacunacion_id: str) -> Vacunacion | None: ...

    @abstractmethod
    def de_mascota(self, mascota_id: str) -> list[Vacunacion]:
        """Historial de una mascota, de la más antigua a la más reciente."""

    @abstractmethod
    def todas(self) -> list[Vacunacion]: ...


class RepositorioDeEsquemas(ABC):
    """Catálogo de esquemas de vacunación (solo lectura para los casos de uso, ADR-05)."""

    @abstractmethod
    def agregar(self, esquema: EsquemaDeVacunacion) -> None: ...

    @abstractmethod
    def todos(self) -> dict[str, EsquemaDeVacunacion]:
        """Los esquemas por clave normalizada de la vacuna."""


class RepositorioDeEmergencias(ABC):
    """Guarda la emergencia aunque no exista cita (NB-19). No depende de RepositorioDeCitas."""

    @abstractmethod
    def agregar(self, emergencia: Emergencia) -> None: ...

    @abstractmethod
    def guardar(self, emergencia: Emergencia) -> None:
        """Guarda el estado actual de una emergencia que ya existe."""

    @abstractmethod
    def obtener(self, emergencia_id: str) -> Emergencia | None: ...

    @abstractmethod
    def listar(
        self, *, estado: EstadoEmergencia | None = None, mascota_id: str | None = None
    ) -> list[Emergencia]: ...


class RepositorioDeEventos(ABC):
    @abstractmethod
    def agregar(self, evento: EventoDeDominio) -> None: ...

    @abstractmethod
    def todos(self) -> list[dict[str, Any]]: ...


class UnidadDeTrabajo(ABC):
    """Una operación completa: todo se guarda junto con `commit()`, o no se guarda nada."""

    servicios: RepositorioDeServicios
    propietarios: RepositorioDePropietarios
    mascotas: RepositorioDeMascotas
    citas: RepositorioDeCitas
    vacunaciones: RepositorioDeVacunaciones
    esquemas: RepositorioDeEsquemas
    emergencias: RepositorioDeEmergencias
    eventos: RepositorioDeEventos

    @abstractmethod
    def __enter__(self) -> UnidadDeTrabajo: ...

    @abstractmethod
    def __exit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...


class NotificadorDeVeterinario(ABC):
    """Interfaz de SALIDA de CU-05 (informe): avisa al veterinario de una emergencia.
    El canal concreto no está definido en el BRD; la infraestructura decide cómo."""

    @abstractmethod
    def notificar(self, emergencia: Emergencia) -> None:
        """Avisa al veterinario. Lanza una excepción si el aviso no se pudo entregar."""
