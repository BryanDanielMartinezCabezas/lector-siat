"""Captura de imagen en tiempo real con la cámara USB (OpenCV).

Según el informe: conexión USB directa al PC (sin transmisión inalámbrica),
visualización en vivo y captura de la foto cuando la tarjeta está en posición.
"""
import os
from datetime import datetime

import cv2


class Camara:
    def __init__(self, indice: int = 0):
        self.indice = indice
        self._cap = None

    def abrir(self) -> bool:
        self._cap = cv2.VideoCapture(self.indice, cv2.CAP_DSHOW)
        return self._cap is not None and self._cap.isOpened()

    def esta_abierta(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def leer_frame(self):
        """Devuelve el último frame (BGR) o None si no hay imagen."""
        if not self.esta_abierta():
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def capturar(self, ruta_destino: str) -> str | None:
        """Guarda el frame actual como PNG y devuelve la ruta, o None si falla."""
        frame = self.leer_frame()
        if frame is None:
            return None
        os.makedirs(os.path.dirname(ruta_destino) or ".", exist_ok=True)
        cv2.imwrite(ruta_destino, frame)
        return ruta_destino

    @staticmethod
    def nombre_captura(carpeta: str) -> str:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return os.path.join(carpeta, f"tarjeta_{marca}.png")

    def cerrar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
