"""Hilo de Qt que ejecuta el RPA sin congelar la interfaz."""
from PyQt6.QtCore import QThread, pyqtSignal

from src.siat.rpa_selenium import EjecutorRPA, Credenciales


class HiloRPA(QThread):
    cambio_estado = pyqtSignal(str, str)   # (tx_id, estado)
    terminado = pyqtSignal(dict)           # contadores finales
    error = pyqtSignal(str)

    def __init__(self, perfil, selectores, libro, credenciales: Credenciales,
                 tamano_lote=5, timeout=60, headless=False):
        super().__init__()
        self._args = (perfil, selectores, libro, credenciales)
        self._kwargs = dict(tamano_lote=tamano_lote, timeout=timeout, headless=headless)

    def run(self):
        try:
            rpa = EjecutorRPA(*self._args, **self._kwargs)
            resumen = rpa.procesar_todo(
                al_cambiar=lambda tx, estado: self.cambio_estado.emit(tx, estado))
            self.terminado.emit(resumen)
        except Exception as e:  # noqa: BLE001 - reportar cualquier fallo a la GUI
            self.error.emit(f"{type(e).__name__}: {e}")
