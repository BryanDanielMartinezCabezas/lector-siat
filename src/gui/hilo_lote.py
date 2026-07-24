"""Hilo Qt del Modo automático: corre el bucle por teclado (sin calibración) en
segundo plano para no congelar la GUI."""
from PyQt6.QtCore import QThread, pyqtSignal

from src.siat.lote import procesar_lote_teclado
from src.siat.rellenador import TecleadorReal


class HiloLote(QThread):
    cambio = pyqtSignal(str, str)
    terminado = pyqtSignal(dict)

    def __init__(self, libro, control, config):
        super().__init__()
        self.libro, self.control, self.config = libro, control, config

    def run(self):
        # Emitir `terminado` SIEMPRE (aunque algo reviente) para liberar la GUI.
        resumen = None
        try:
            resumen = procesar_lote_teclado(
                self.libro,
                TecleadorReal(float(self.config.get("carga_intervalo_tecla", 0.05))),
                self.control,
                pausa_campo=float(self.config.get("carga_pausa_campo", 0.35)),
                tabs_hasta_adicionar=int(self.config.get("tabs_hasta_adicionar", 16)),
                tecla_enviar=self.config.get("tecla_adicionar", "space"),
                tabs_regreso=int(self.config.get("tabs_regreso", 3)),
                pausa_tras_envio=float(self.config.get("pausa_tras_adicionar", 4.0)),
                al_cambiar=lambda tx, e: self.cambio.emit(tx, e))
        except Exception:  # noqa: BLE001 - nunca dejar la GUI congelada
            if getattr(self.control, "motivo", None) is None:
                self.control.motivo = "error"
        finally:
            if resumen is None:
                resumen = self.libro.contadores()
            self.terminado.emit(resumen)
