"""Retroalimentación visual (LED bicolor), desacoplada del hardware.

Verde = lectura exitosa, rojo = fallo (según el informe). Hoy el LED es un
indicador en pantalla; cuando exista la cajita, se enciende el LED físico por
serial sin cambiar la lógica que lo invoca.
"""
from abc import ABC, abstractmethod
from typing import Callable


class IndicadorLed(ABC):
    @abstractmethod
    def verde(self) -> None:
        """Señala una lectura/operación exitosa."""

    @abstractmethod
    def rojo(self) -> None:
        """Señala un fallo."""


class LedVirtual(IndicadorLed):
    """LED en pantalla: notifica el estado a la GUI mediante un callback."""

    def __init__(self, al_cambiar: Callable[[str], None] | None = None):
        self._al_cambiar = al_cambiar

    def verde(self) -> None:
        if self._al_cambiar:
            self._al_cambiar("verde")

    def rojo(self) -> None:
        if self._al_cambiar:
            self._al_cambiar("rojo")


class LedHardware(IndicadorLed):
    """LED físico de la cajita vía serial (pendiente de hardware)."""

    def __init__(self, puerto: str, baudios: int = 9600):
        self.puerto = puerto
        self.baudios = baudios

    def _enviar(self, color: str) -> None:
        raise NotImplementedError(
            "El LED físico requiere la cajita y pyserial; se implementará al "
            "integrar el hardware. Por ahora use LedVirtual."
        )

    def verde(self) -> None:
        self._enviar("verde")

    def rojo(self) -> None:
        self._enviar("rojo")
