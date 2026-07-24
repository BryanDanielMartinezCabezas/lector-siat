"""Hilo Qt que corre `procesar_lote` en segundo plano para no congelar la GUI."""
from PyQt6.QtCore import QThread, pyqtSignal

from src.siat.lote import procesar_lote
from src.siat.rellenador import TecleadorReal
from src.siat.localizador import Localizador


class HiloLote(QThread):
    cambio = pyqtSignal(str, str)
    terminado = pyqtSignal(dict)

    def __init__(self, libro, control, config):
        super().__init__()
        self.libro, self.control, self.config = libro, control, config

    def run(self):
        loc = Localizador(self.config.get("ruta_calibracion", "datos/calibracion"))
        r = procesar_lote(
            self.libro, TecleadorReal(float(self.config.get("carga_intervalo_tecla", 0.05))),
            loc, self.control,
            pausa_campo=float(self.config.get("carga_pausa_campo", 0.35)),
            pausa_envio=float(self.config.get("carga_pausa_envio", 0.6)),
            al_cambiar=lambda tx, e: self.cambio.emit(tx, e))
        self.terminado.emit(r)
