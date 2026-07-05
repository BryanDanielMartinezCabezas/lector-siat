"""Motor "Cargar": rellena el formulario real del SIAT simulando el teclado.

Enfoque indicado por el ingeniero-cliente: el SIN detecta y bloquea la
automatización del navegador (Selenium/WebDriver). En vez de eso, el usuario
navega él mismo hasta el formulario "Agregar Registro" del RCV, hace clic en el
primer campo, y el software escribe los datos como si fuera una persona (a nivel
del teclado del sistema, con pyautogui). El contribuyente revisa y presiona
"Adicionar". Así no hay navegador automatizado que delate el proceso.

Para que sea PREDECIBLE (el formulario valida cada campo por AJAX):
  - antes de escribir cada campo se selecciona y borra su contenido (Ctrl+A),
    así no quedan restos y el resultado no depende del estado previo;
  - hay una pausa configurable entre campos para que la validación termine
    antes de pasar al siguiente con Tab.

La lógica es independiente del backend de teclado, por lo que se puede probar
sin mover el teclado real usando `TecleadorFake`.
"""

# Secuencia de tabulación del formulario "Agregar Registro" del RCV.
# Cada paso:
#   ("campo", clave) -> escribe datos[clave]
#   ("fijo", texto)  -> escribe un literal (ej. "0" para DUI/DIM)
#   ("dia", clave)   -> escribe SOLO el día de la fecha (el mes/año los fija el
#                       período seleccionado en el SIAT, no se escriben)
# Entre paso y paso se presiona Tab. El orden se verificó contra el formulario
# real; si el SIN lo cambia, se ajusta aquí.
SECUENCIA_RCV = [
    ("campo", "nit"),            # NIT Proveedor
    ("campo", "autorizacion"),   # Código de Autorización
    ("campo", "numero_factura"), # Número Factura
    ("fijo", "0"),               # Número DUI/DIM (siempre 0)
    ("dia", "fecha"),            # Fecha: solo el día (mes/año = período del SIAT)
    ("campo", "importe"),        # Importe Total Compra
    # ICE, IEHD, IPJ, Tasas, etc. quedan en 0.00 por defecto (no se tocan).
]


class TecleadorFake:
    """Backend de prueba: registra las acciones en vez de mover el teclado."""

    def __init__(self):
        self.acciones = []

    def seleccionar_todo(self):
        self.acciones.append(("selall",))

    def borrar(self):
        self.acciones.append(("borrar",))

    def escribir(self, texto):
        self.acciones.append(("escribir", str(texto)))

    def tab(self):
        self.acciones.append(("tab",))

    def pausa(self, segundos):
        self.acciones.append(("pausa", segundos))


class TecleadorReal:
    """Backend real: escribe con pyautogui (teclado del sistema, sin navegador)."""

    def __init__(self, intervalo=0.05):
        import pyautogui
        self._pg = pyautogui
        self._pg.FAILSAFE = True  # mover el mouse a una esquina aborta todo
        self.intervalo = intervalo

    def seleccionar_todo(self):
        self._pg.hotkey("ctrl", "a")

    def borrar(self):
        self._pg.press("delete")

    def escribir(self, texto):
        self._pg.write(str(texto), interval=self.intervalo)

    def tab(self):
        self._pg.press("tab")

    def pausa(self, segundos):
        import time
        time.sleep(segundos)


def _valor_del_paso(paso, datos: dict) -> str:
    tipo = paso[0]
    if tipo == "fijo":
        return paso[1]
    if tipo == "dia":
        fecha = datos.get(paso[1]) or ""
        return fecha.split("/")[0] if fecha else ""
    return datos.get(paso[1]) or ""   # "campo"


def cargar_registro(datos: dict, tecleador, secuencia=SECUENCIA_RCV,
                    pausa=0.35) -> None:
    """Escribe un registro en el formulario enfocado, siguiendo la secuencia.

    Se asume que el cursor ya está en el primer campo (el usuario hizo clic ahí).
    """
    for i, paso in enumerate(secuencia):
        valor = _valor_del_paso(paso, datos)
        # Limpiar el campo antes de escribir -> resultado determinista.
        tecleador.seleccionar_todo()
        tecleador.borrar()
        tecleador.escribir(valor)
        tecleador.pausa(pausa)          # dejar que valide antes de avanzar
        if i < len(secuencia) - 1:
            tecleador.tab()
