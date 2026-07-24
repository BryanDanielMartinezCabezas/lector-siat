"""Localiza y clica elementos del formulario del SIAT por reconocimiento de imagen.

No controla el navegador: busca en la pantalla la imagen de referencia (capturada
en calibración) y hace clic en su centro, como lo haría una persona. Sirve para
'Cargar todos', donde el software debe pulsar 'Adicionar' y 'Nuevo Registro'.
"""
import os

ANCLAS = ("nit", "adicionar", "nuevo_registro")


class _BackendPyAutoGUI:
    def __init__(self, confianza=0.85):
        import pyautogui
        self._pg = pyautogui
        self.confianza = confianza

    def localizar_centro(self, ruta_png):
        try:
            p = self._pg.locateCenterOnScreen(ruta_png, confidence=self.confianza)
        except Exception:
            p = None
        return (int(p.x), int(p.y)) if p else None

    def clic(self, x, y):
        self._pg.click(x, y)


class Localizador:
    def __init__(self, dir_calibracion: str, backend=None):
        self.dir_calibracion = dir_calibracion
        self._backend = backend

    def _ruta(self, ancla: str) -> str:
        return os.path.join(self.dir_calibracion, f"{ancla}.png")

    def imagenes_faltantes(self) -> list[str]:
        return [a for a in ANCLAS if not os.path.exists(self._ruta(a))]

    def disponible(self) -> bool:
        return not self.imagenes_faltantes()

    def _asegurar_backend(self):
        if self._backend is None:
            self._backend = _BackendPyAutoGUI()
        return self._backend

    def clic(self, ancla: str) -> bool:
        backend = self._asegurar_backend()
        pos = backend.localizar_centro(self._ruta(ancla))
        if pos is None:
            return False
        backend.clic(*pos)
        return True
