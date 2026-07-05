"""Motor "Cargar": rellena el formulario real del SIAT simulando el teclado.

Enfoque indicado por el ingeniero-cliente: el SIN detecta y bloquea la
automatización del navegador (Selenium/WebDriver). En vez de eso, el usuario
navega él mismo hasta el formulario "Agregar Registro" del RCV, hace clic en el
primer campo, y el software escribe los datos como si fuera una persona (a nivel
del teclado del sistema operativo, con pyautogui). El contribuyente revisa y
presiona "Adicionar". Así no hay navegador automatizado que delate el proceso.

La lógica (qué escribir y en qué orden) es independiente del backend de teclado,
por lo que se puede probar sin mover el teclado real usando `TecleadorFake`.
"""

# Secuencia de tabulación del formulario "Agregar Registro" del RCV.
# Cada paso:
#   ("campo", clave) -> escribe datos[clave] y pasa al siguiente campo (Tab)
#   ("fijo", texto)  -> escribe un literal (ej. "0" para DUI/DIM) y Tab
#   ("saltar",)      -> deja el campo con su valor por defecto (solo Tab)
# ⚠ El orden exacto debe afinarse contra el formulario real durante el dry-run;
#   por eso vive aquí como constante fácil de ajustar.
SECUENCIA_RCV = [
    ("campo", "nit"),            # NIT Proveedor
    ("campo", "autorizacion"),   # Código de Autorización
    ("campo", "numero_factura"), # Número Factura
    ("fijo", "0"),               # Número DUI/DIM (siempre 0)
    ("campo", "fecha"),          # Fecha Factura/DUI/DIM (01 del mes)
    ("campo", "importe"),        # Importe Total Compra
    # ICE, IEHD, IPJ, Tasas, etc. quedan en 0.00 por defecto (no se tocan).
]


class TecleadorFake:
    """Backend de prueba: registra las acciones en vez de mover el teclado."""

    def __init__(self):
        self.acciones = []

    def escribir(self, texto):
        self.acciones.append(("escribir", str(texto)))

    def tab(self):
        self.acciones.append(("tab",))

    def pausa(self, segundos):
        self.acciones.append(("pausa", segundos))


class TecleadorReal:
    """Backend real: escribe con pyautogui (teclado del sistema, sin navegador)."""

    def __init__(self, intervalo=0.04):
        import pyautogui
        self._pg = pyautogui
        self._pg.FAILSAFE = True  # mover el mouse a una esquina aborta todo
        self.intervalo = intervalo

    def escribir(self, texto):
        self._pg.write(str(texto), interval=self.intervalo)

    def tab(self):
        self._pg.press("tab")

    def pausa(self, segundos):
        import time
        time.sleep(segundos)


def cargar_registro(datos: dict, tecleador, secuencia=SECUENCIA_RCV,
                    pausa=0.15) -> None:
    """Escribe un registro en el formulario enfocado, siguiendo la secuencia.

    Se asume que el cursor ya está en el primer campo (el usuario hizo clic ahí).
    Entre cada campo se presiona Tab para avanzar al siguiente.
    """
    for i, paso in enumerate(secuencia):
        if paso[0] == "campo":
            valor = datos.get(paso[1]) or ""
            tecleador.escribir(valor)
        elif paso[0] == "fijo":
            tecleador.escribir(paso[1])
        # ("saltar",) no escribe nada.
        tecleador.pausa(pausa)
        # Avanzar al siguiente campo salvo después del último.
        if i < len(secuencia) - 1:
            tecleador.tab()
