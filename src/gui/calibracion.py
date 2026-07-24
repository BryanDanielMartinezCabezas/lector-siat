"""Asistente de calibración: captura las imágenes de referencia (NIT, Adicionar,
Nuevo Registro) que usa el Localizador. Una vez por PC, con el navegador al 100%."""
import os

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QWidget, QApplication, QMessageBox

from src.siat.localizador import ANCLAS

_ETIQUETAS = {"nit": "campo NIT Proveedor", "adicionar": "botón Adicionar",
              "nuevo_registro": "botón Nuevo Registro"}


class OverlayRecorte(QWidget):
    recorte_listo = pyqtSignal(QRect)

    def __init__(self, captura: QPixmap):
        super().__init__(flags=Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self._captura = captura
        self._ini = None
        self._fin = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.showFullScreen()

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._captura)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self._ini and self._fin:
            r = QRect(self._ini, self._fin).normalized()
            p.drawPixmap(r, self._captura, r)
            p.setPen(QColor("#0e7ac0"))
            p.drawRect(r)

    def mousePressEvent(self, e): self._ini = e.pos(); self._fin = e.pos()
    def mouseMoveEvent(self, e): self._fin = e.pos(); self.update()

    def mouseReleaseEvent(self, e):
        self._fin = e.pos()
        self.recorte_listo.emit(QRect(self._ini, self._fin).normalized())
        self.close()


def calibrar_anclas(parent, dir_calibracion: str) -> bool:
    os.makedirs(dir_calibracion, exist_ok=True)
    for ancla in ANCLAS:
        QMessageBox.information(
            parent, "Calibración",
            f"Deja visible el {_ETIQUETAS[ancla]} en el navegador (100% zoom) y "
            "acepta. Luego arrastra un recuadro SOLO sobre ese elemento.")
        pantalla = QApplication.primaryScreen()
        captura = pantalla.grabWindow(0)
        overlay = OverlayRecorte(captura)
        rect = {}
        overlay.recorte_listo.connect(lambda r: rect.update({"r": r}))
        loop_ok = _ejecutar_overlay(overlay)
        if not loop_ok or "r" not in rect or rect["r"].width() < 4:
            return False
        captura.copy(rect["r"]).save(os.path.join(dir_calibracion, f"{ancla}.png"))
    return True


def _ejecutar_overlay(overlay) -> bool:
    from PyQt6.QtCore import QEventLoop
    loop = QEventLoop()
    overlay.destroyed.connect(loop.quit)
    loop.exec()
    return True
