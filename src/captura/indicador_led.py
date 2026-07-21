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
    """LED físico de la cajita vía serial (pyserial)."""

    def __init__(self, puerto: str, baudios: int = 115200):
        self.puerto = puerto
        self.baudios = baudios
        self._ser = None
        self._conectar()

    def _conectar(self) -> None:
        if not self.puerto:
            return
        try:
            import serial
            self._ser = serial.Serial(self.puerto, self.baudios, timeout=1)
            print(f"🔌 Conectado a la cajita LED en {self.puerto} a {self.baudios} baudios.")
        except Exception as e:
            print(f"⚠️ No se pudo conectar a la cajita LED en {self.puerto}: {e}")
            self._ser = None

    def _enviar(self, comando: str) -> None:
        if self._ser is None or not self._ser.is_open:
            self._conectar()
            
        if self._ser and self._ser.is_open:
            try:
                self._ser.write(comando.encode('utf-8'))
                self._ser.flush()
            except Exception as e:
                print(f"⚠️ Error al enviar comando '{comando}' a la cajita: {e}")
                self._ser = None

    def verde(self) -> None:
        self._enviar("V")

    def rojo(self) -> None:
        self._enviar("R")

    def apagar(self) -> None:
        self._enviar("O")

    def __del__(self):
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass


class LedMixto(IndicadorLed):
    """Combina la retroalimentación visual en pantalla (LedVirtual) y física (LedHardware)."""

    def __init__(self, virtual: LedVirtual, hardware: LedHardware | None):
        self.virtual = virtual
        self.hardware = hardware

    def verde(self) -> None:
        self.virtual.verde()
        if self.hardware:
            self.hardware.verde()

    def rojo(self) -> None:
        self.virtual.rojo()
        if self.hardware:
            self.hardware.rojo()
