"""Disparo de la captura, desacoplado del hardware.

La lógica del software no sabe si la orden de capturar viene de una tecla, un
botón de la GUI o del sensor infrarrojo de la cajita. Hoy se usa el disparador
manual; cuando Adrián entregue la cajita, se cambia por DisparadorSensorIR sin
tocar el resto del sistema.
"""
from abc import ABC, abstractmethod
from typing import Callable


class Disparador(ABC):
    @abstractmethod
    def armar(self, callback: Callable[[], None]) -> None:
        """Registra la función a ejecutar cuando ocurra un disparo."""


class DisparadorManual(Disparador):
    """Disparo por tecla o botón de la GUI: la app llama a disparar()."""

    def __init__(self):
        self._callback: Callable[[], None] | None = None

    def armar(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def disparar(self) -> None:
        if self._callback is not None:
            self._callback()


class DisparadorSensorIR(Disparador):
    """Disparo por sensor infrarrojo vía puerto serial (pendiente de hardware).

    Cuando la cajita esté lista, este disparador leerá la línea "TRIGGER" que el
    microcontrolador envía por serial al detectar la tarjeta al final del carril.
    """

    def __init__(self, puerto: str, baudios: int = 9600):
        self.puerto = puerto
        self.baudios = baudios

    def armar(self, callback: Callable[[], None]) -> None:
        raise NotImplementedError(
            "El disparador por sensor IR requiere la cajita física y la librería "
            "pyserial. Se implementará al integrar el hardware de Adrián; por "
            "ahora use DisparadorManual."
        )
