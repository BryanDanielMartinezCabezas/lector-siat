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
        # Emitir `terminado` SIEMPRE (incluso si algo revienta al construir el
        # tecleador/localizador) para que _lote_termino libere la GUI.
        resumen = None
        try:
            loc = Localizador(self.config.get("ruta_calibracion", "datos/calibracion"))
            resumen = procesar_lote(
                self.libro, TecleadorReal(float(self.config.get("carga_intervalo_tecla", 0.05))),
                loc, self.control,
                pausa_campo=float(self.config.get("carga_pausa_campo", 0.35)),
                pausa_envio=float(self.config.get("carga_pausa_envio", 0.6)),
                al_cambiar=lambda tx, e: self.cambio.emit(tx, e))
        except Exception:  # noqa: BLE001 - nunca dejar la GUI congelada
            if getattr(self.control, "motivo", None) is None:
                self.control.motivo = "error"
        finally:
            if resumen is None:
                resumen = self.libro.contadores()
            self.terminado.emit(resumen)
