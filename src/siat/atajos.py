"""Atajos de teclado globales (funcionan aunque la app no tenga el foco).

F8 = iniciar, F7 = pausar/reanudar, F9 = detener. Usa pynput para escuchar el
teclado del sistema mientras el usuario está en el navegador del SIAT.
"""


class AtajosGlobales:
    def __init__(self, al_iniciar, al_pausar, al_detener, backend=None):
        self._callbacks = {"f8": al_iniciar, "f7": al_pausar, "f9": al_detener}
        self._backend = backend

    def _procesar_tecla(self, nombre: str) -> None:
        cb = self._callbacks.get(nombre)
        if cb:
            cb()

    def iniciar(self) -> None:
        if self._backend is None:
            from pynput import keyboard

            def on_press(tecla):
                nombre = getattr(tecla, "name", None)
                if nombre:
                    self._procesar_tecla(nombre.lower())

            self._backend = keyboard.Listener(on_press=on_press)
            self._backend.start()

    def detener(self) -> None:
        if self._backend is not None and hasattr(self._backend, "stop"):
            self._backend.stop()
