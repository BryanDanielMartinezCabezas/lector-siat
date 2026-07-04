"""Captura de imagen en tiempo real con la cámara USB (OpenCV).

Según el informe: conexión USB directa al PC (sin transmisión inalámbrica),
visualización en vivo y captura de la foto cuando la tarjeta está en posición.
"""
import os
from datetime import datetime

import cv2


class Camara:
    def __init__(self, indice: int = 0, ancho: int = 1280, alto: int = 720):
        self.indice = indice
        self.ancho = ancho
        self.alto = alto
        self._cap = None

    def abrir(self) -> bool:
        self._cap = cv2.VideoCapture(self.indice, cv2.CAP_DSHOW)
        if self._cap is not None and self._cap.isOpened():
            # Pedir la mayor resolución posible: nitidez = QR y OCR legibles.
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.ancho)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto)
            return True
        return False

    def cambiar_a(self, indice: int) -> bool:
        """Cierra la cámara actual y abre otra por índice (ej. DroidCam)."""
        self.cerrar()
        self.indice = indice
        return self.abrir()

    @staticmethod
    def listar_camaras(maximo: int = 6) -> list[int]:
        """Devuelve los índices de cámaras disponibles (0..maximo-1)."""
        disponibles = []
        for i in range(maximo):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap is not None and cap.isOpened():
                disponibles.append(i)
            cap.release()
        return disponibles

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
