# Carga por Lotes — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cargar tarjetas al formulario del SIAT en lote (o de a una) con control por teclas F8/F7/F9, sin automatizar el navegador, marcando cada tarjeta como `completado`.

**Architecture:** El llenado usa teclado (pyautogui, ya existe). El envío/reapertura entre tarjetas usa clics anclados por reconocimiento de imagen (pyautogui+OpenCV) con calibración por PC. Un orquestador corre el bucle en un hilo Qt; atajos globales (pynput) lo inician/pausan/detienen.

**Tech Stack:** Python 3.11, PyQt6, pyautogui, OpenCV (ya instalado), pynput (nuevo), openpyxl, pytest.

## Global Constraints

- Nada de automatización del navegador (Selenium/JS/DevTools). Solo teclado + clic por imagen.
- Teclas: **F8 iniciar · F7 pausar/reanudar · F9 detener**. F8 dispara el modo activo; F9 apaga cualquiera.
- Estados exactos: `ESTADOS = ("pendiente", "en_proceso", "completado", "saltado")`. Se eliminan `exitoso` y `fallido`.
- `completado` es terminal: no se re-carga (advertencia). Abortar devuelve la tarjeta en curso a `pendiente`.
- Pausas tipo humano; failsafe de pyautogui (mouse a esquina aborta).
- Los dos modos (individual armado y "Cargar todos") son mutuamente excluyentes; una sola fila armada a la vez.
- Anclas de imagen: `"nit"`, `"adicionar"`, `"nuevo_registro"`, en `datos/calibracion/<ancla>.png`.
- Código y comentarios en español.

---

### Task 1: Libro Mayor — estados nuevos, bloqueo de recarga y cambio en masa

**Files:**
- Modify: `src/libro_mayor/libro_mayor.py`
- Modify: `tests/test_libro_mayor.py`

**Interfaces:**
- Produces:
  - `ESTADOS = ("pendiente", "en_proceso", "completado", "saltado")`
  - `LibroMayor.puede_cargar(tx_id: str) -> bool` (True solo si estado == "pendiente")
  - `LibroMayor.marcar_varias(ids: list[str], estado: str) -> None`
  - `marcar(tx_id, estado, detalle="")` sigue igual (valida contra el nuevo ESTADOS).

- [ ] **Step 1: Ajustar los tests existentes que usan estados viejos + agregar los nuevos**

En `tests/test_libro_mayor.py`, cambiar toda aparición de `"exitoso"` por `"completado"` y `"fallido"` por `"saltado"` en las llamadas a `marcar`/asserts, y agregar:

```python
def test_puede_cargar_solo_si_pendiente(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    assert lm.puede_cargar("TX-000001") is True
    lm.marcar("TX-000001", "completado")
    assert lm.puede_cargar("TX-000001") is False   # completado no se recarga


def test_marcar_varias_cambia_en_masa(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for _ in range(3):
        lm.agregar(_d())
    lm.marcar_varias(["TX-000001", "TX-000003"], "saltado")
    c = lm.contadores()
    assert c["saltado"] == 2 and c["pendiente"] == 1


def test_estado_viejo_exitoso_ya_no_es_valido(tmp_path):
    import pytest
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    with pytest.raises(ValueError):
        lm.marcar("TX-000001", "exitoso")
```

- [ ] **Step 2: Correr y verificar FAIL** — `.venv/Scripts/python -m pytest tests/test_libro_mayor.py -q` → fallos por `exitoso` inválido y métodos inexistentes.

- [ ] **Step 3: Implementar** en `src/libro_mayor/libro_mayor.py`:

```python
ESTADOS = ("pendiente", "en_proceso", "completado", "saltado")
```

Y agregar los métodos (después de `marcar`):

```python
    def puede_cargar(self, tx_id: str) -> bool:
        """True solo si la transacción está pendiente (completado no se recarga)."""
        for tx in self._transacciones:
            if tx["id"] == tx_id:
                return tx["estado"] == "pendiente"
        return False

    def marcar_varias(self, ids: list[str], estado: str) -> None:
        """Cambia el estado de varias transacciones de una vez (selección múltiple)."""
        for tx_id in ids:
            self.marcar(tx_id, estado)
```

- [ ] **Step 4: Correr tests hasta PASS** — `.venv/Scripts/python -m pytest tests/test_libro_mayor.py -q`

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: libro mayor con estado completado, bloqueo de recarga y cambio en masa"`

---

### Task 2: Excel de respaldo corregido (columnas del formulario + Fecha de Registro)

**Files:**
- Modify: `src/siat/excel_rcv.py`
- Modify: `tests/test_excel_rcv.py`

**Interfaces:**
- Produces:
  - `COLUMNAS_RCV` (lista de cabeceras que coinciden con el formulario real + `"Fecha de Registro"`).
  - `generar_excel_compras(transacciones, ruta_salida, razon_social_por_defecto="", fecha_registro=None) -> int`. Si `fecha_registro` es None usa la fecha de hoy (`dd/mm/aaaa`).

- [ ] **Step 1: Reescribir el test** `tests/test_excel_rcv.py`:

```python
from datetime import date
from openpyxl import load_workbook
from src.siat.excel_rcv import generar_excel_compras, COLUMNAS_RCV


def _tx(numero="162452780", importe="10.00"):
    return {"id": "TX-000001", "estado": "completado",
            "datos": {"nit": "1020703023", "numero_factura": numero,
                      "autorizacion": "123189FFD1971B", "fecha": "01/07/2026",
                      "importe": importe, "operadora": "ENTEL"}}


def test_cabeceras_coinciden_con_formulario():
    esperadas = ["Nº", "NIT Proveedor", "Código de Autorización", "Número Factura",
                 "Número DUI/DIM", "Fecha Factura", "Importe Total Compra",
                 "Importe ICE", "Importe IEHD", "Importe IPJ", "Tasas",
                 "Otro No Sujeto a Crédito Fiscal", "Importes Exentos",
                 "Importe Compras Gravadas a Tasa Cero", "Subtotal",
                 "Descuentos Bonificaciones y Rebajas Sujetas al IVA",
                 "Importe Gift Card", "Importe Base Crédito Fiscal", "Crédito Fiscal",
                 "Tipo Compra", "Código de Control", "Fecha de Registro"]
    assert COLUMNAS_RCV == esperadas


def test_fila_y_credito_fiscal(tmp_path):
    ruta = str(tmp_path / "c.xlsx")
    assert generar_excel_compras([_tx(importe="100.00")], ruta) == 1
    ws = load_workbook(ruta).active
    fila = {ws.cell(1, i + 1).value: ws.cell(2, i + 1).value for i in range(len(COLUMNAS_RCV))}
    assert str(fila["NIT Proveedor"]) == "1020703023"
    assert float(fila["Crédito Fiscal"]) == 13.00
    assert str(fila["Número DUI/DIM"]) == "0"
    assert str(fila["Tipo Compra"]) == "INTERNO/ACTIVIDAD"


def test_fecha_de_registro_es_hoy(tmp_path):
    ruta = str(tmp_path / "c.xlsx")
    generar_excel_compras([_tx()], ruta)
    ws = load_workbook(ruta).active
    idx = COLUMNAS_RCV.index("Fecha de Registro") + 1
    assert ws.cell(2, idx).value == date.today().strftime("%d/%m/%Y")
```

- [ ] **Step 2: FAIL** — `.venv/Scripts/python -m pytest tests/test_excel_rcv.py -q`

- [ ] **Step 3: Implementar** en `src/siat/excel_rcv.py`:

```python
from datetime import date
from openpyxl import Workbook

COLUMNAS_RCV = [
    "Nº", "NIT Proveedor", "Código de Autorización", "Número Factura",
    "Número DUI/DIM", "Fecha Factura", "Importe Total Compra", "Importe ICE",
    "Importe IEHD", "Importe IPJ", "Tasas", "Otro No Sujeto a Crédito Fiscal",
    "Importes Exentos", "Importe Compras Gravadas a Tasa Cero", "Subtotal",
    "Descuentos Bonificaciones y Rebajas Sujetas al IVA", "Importe Gift Card",
    "Importe Base Crédito Fiscal", "Crédito Fiscal", "Tipo Compra",
    "Código de Control", "Fecha de Registro",
]
_ALICUOTA_IVA = 0.13


def _limpiar(v) -> str:
    return str(v if v is not None else "").strip()


def generar_excel_compras(transacciones, ruta_salida, razon_social_por_defecto="",
                          fecha_registro=None) -> int:
    hoy = fecha_registro or date.today().strftime("%d/%m/%Y")
    wb = Workbook(); ws = wb.active; ws.title = "Compras"
    ws.append(COLUMNAS_RCV)
    filas = 0
    for i, tx in enumerate(transacciones, start=1):
        d = tx.get("datos", tx)
        try:
            importe = round(float(d.get("importe") or 0), 2)
        except (TypeError, ValueError):
            importe = 0.0
        credito = round(importe * _ALICUOTA_IVA, 2)
        ws.append([
            i, _limpiar(d.get("nit")), _limpiar(d.get("autorizacion")),
            _limpiar(d.get("numero_factura")), "0", _limpiar(d.get("fecha")),
            importe, 0, 0, 0, 0, 0, 0, 0, importe, 0, 0, importe, credito,
            "INTERNO/ACTIVIDAD", "0", hoy,
        ])
        filas += 1
    wb.save(ruta_salida)
    return filas
```

- [ ] **Step 4: PASS** — `.venv/Scripts/python -m pytest tests/test_excel_rcv.py -q`
- [ ] **Step 5: Commit** — `git commit -am "feat: Excel de respaldo con columnas del formulario real y Fecha de Registro"`

---

### Task 3: Localizador por imagen (clic anclado con calibración)

**Files:**
- Create: `src/siat/localizador.py`
- Test: `tests/test_localizador.py`

**Interfaces:**
- Produces:
  - `ANCLAS = ("nit", "adicionar", "nuevo_registro")`
  - `class Localizador(dir_calibracion: str, backend=None)`:
    - `imagenes_faltantes() -> list[str]` (anclas sin PNG en el directorio)
    - `disponible() -> bool` (no falta ninguna)
    - `clic(ancla: str) -> bool` (localiza el PNG en pantalla y clica su centro; False si no lo encuentra)
  - `backend` inyectable para tests: objeto con `localizar_centro(ruta_png) -> tuple[int,int] | None` y `clic(x, y) -> None`. Si `backend=None`, usa pyautogui (import perezoso).

- [ ] **Step 1: Test con backend falso** `tests/test_localizador.py`:

```python
from src.siat.localizador import Localizador, ANCLAS


class BackendFalso:
    def __init__(self, encontrables):
        self.encontrables = encontrables   # dict ruta->(x,y) o None
        self.clics = []

    def localizar_centro(self, ruta_png):
        for clave, pos in self.encontrables.items():
            if clave in ruta_png:
                return pos
        return None

    def clic(self, x, y):
        self.clics.append((x, y))


def _crear_pngs(tmp_path, anclas):
    for a in anclas:
        (tmp_path / f"{a}.png").write_bytes(b"png")
    return str(tmp_path)


def test_imagenes_faltantes_lista_las_que_no_estan(tmp_path):
    d = _crear_pngs(tmp_path, ["nit"])
    loc = Localizador(d, backend=BackendFalso({}))
    assert set(loc.imagenes_faltantes()) == {"adicionar", "nuevo_registro"}
    assert loc.disponible() is False


def test_disponible_cuando_estan_todas(tmp_path):
    d = _crear_pngs(tmp_path, ANCLAS)
    loc = Localizador(d, backend=BackendFalso({}))
    assert loc.disponible() is True


def test_clic_localiza_y_clica(tmp_path):
    d = _crear_pngs(tmp_path, ANCLAS)
    be = BackendFalso({"adicionar": (100, 200)})
    loc = Localizador(d, backend=be)
    assert loc.clic("adicionar") is True
    assert be.clics == [(100, 200)]


def test_clic_devuelve_false_si_no_encuentra(tmp_path):
    d = _crear_pngs(tmp_path, ANCLAS)
    loc = Localizador(d, backend=BackendFalso({}))
    assert loc.clic("nit") is False
```

- [ ] **Step 2: FAIL** — `.venv/Scripts/python -m pytest tests/test_localizador.py -q`

- [ ] **Step 3: Implementar** `src/siat/localizador.py`:

```python
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
```

- [ ] **Step 4: PASS** — `.venv/Scripts/python -m pytest tests/test_localizador.py -q`
- [ ] **Step 5: Commit** — `git commit -am "feat: localizador por imagen para clics anclados (Cargar todos)"`

---

### Task 4: rellenador — enviar y reabrir el formulario

**Files:**
- Modify: `src/siat/rellenador.py`
- Modify: `tests/test_rellenador.py`

**Interfaces:**
- Consumes: `Localizador.clic(ancla)` (Task 3).
- Produces: `enviar_y_reabrir(localizador, pausa=0.6) -> bool`. Clica `adicionar`, pausa, `nuevo_registro`, pausa, `nit`, pausa. Devuelve True solo si las tres anclas se encontraron; False si alguna falló (para que el lote se detenga sin clicar a ciegas). La pausa se hace con `time.sleep` salvo que el localizador traiga un `pausar` (para tests).

- [ ] **Step 1: Test** en `tests/test_rellenador.py`:

```python
from src.siat.rellenador import enviar_y_reabrir


class LocalizadorFake:
    def __init__(self, fallar=None):
        self.fallar = fallar or set()
        self.clics = []

    def clic(self, ancla):
        self.clics.append(ancla)
        return ancla not in self.fallar


def test_enviar_y_reabrir_orden_correcto():
    loc = LocalizadorFake()
    assert enviar_y_reabrir(loc, pausa=0) is True
    assert loc.clics == ["adicionar", "nuevo_registro", "nit"]


def test_enviar_y_reabrir_falla_si_no_encuentra_boton():
    loc = LocalizadorFake(fallar={"nuevo_registro"})
    assert enviar_y_reabrir(loc, pausa=0) is False
```

- [ ] **Step 2: FAIL** — `.venv/Scripts/python -m pytest tests/test_rellenador.py::test_enviar_y_reabrir_orden_correcto -q`

- [ ] **Step 3: Implementar** — agregar al final de `src/siat/rellenador.py`:

```python
import time


def enviar_y_reabrir(localizador, pausa=0.6) -> bool:
    """Pulsa Adicionar → Nuevo Registro → NIT (por imagen). False si algo no aparece."""
    for ancla in ("adicionar", "nuevo_registro", "nit"):
        if not localizador.clic(ancla):
            return False
        if pausa:
            time.sleep(pausa)
    return True
```

- [ ] **Step 4: PASS** — `.venv/Scripts/python -m pytest tests/test_rellenador.py -q`
- [ ] **Step 5: Commit** — `git commit -am "feat: rellenador.enviar_y_reabrir (Adicionar/Nuevo Registro/NIT por imagen)"`

---

### Task 5: Orquestador del lote (bucle con aborto/pausa)

**Files:**
- Create: `src/siat/lote.py`
- Test: `tests/test_lote.py`

**Interfaces:**
- Consumes: `LibroMayor` (Task 1), `cargar_registro` y `enviar_y_reabrir` (Task 4), un tecleador (real/fake) y un localizador (real/fake).
- Produces:
  - `class ControlLote`: banderas de hilo. `pausar()`, `reanudar()`, `abortar()`, `esta_pausado()->bool`, `esta_abortado()->bool`.
  - `procesar_lote(libro, tecleador, localizador, control, secuencia=None, pausa_campo=0.35, pausa_envio=0.6, al_cambiar=None, dormir=time.sleep) -> dict`:
    recorre las `pendientes()` del libro; por cada una: si `control.esta_abortado()` corta; mientras `control.esta_pausado()` y no abortado, espera; marca `en_proceso` (callback); `cargar_registro(datos, tecleador, secuencia, pausa_campo)`; `enviar_y_reabrir(localizador, pausa_envio)`; si devuelve False, marca la tarjeta de nuevo `pendiente` y corta con `detalle`; si True marca `completado`. Devuelve contadores finales del libro. `dormir` inyectable para no dormir en tests.

- [ ] **Step 1: Test** `tests/test_lote.py`:

```python
from src.extraccion.datos_fiscales import DatosFiscales
from src.libro_mayor.libro_mayor import LibroMayor
from src.siat.lote import procesar_lote, ControlLote


class TecleadorFake:
    def seleccionar_todo(self): pass
    def borrar(self): pass
    def escribir(self, t): pass
    def tab(self): pass
    def pausa(self, s): pass


class LocalizadorFake:
    def __init__(self, fallar=None):
        self.fallar = fallar or set()
    def clic(self, ancla):
        return ancla not in self.fallar


def _libro(tmp_path, n):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for i in range(n):
        lm.agregar(DatosFiscales(nit="1020703023", numero_factura=str(100 + i),
                                 autorizacion="123189FFD1971B", fecha="01/07/2026",
                                 importe="10.00"))
    return lm


def test_procesa_todas_las_pendientes(tmp_path):
    lm = _libro(tmp_path, 3)
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(), ControlLote(),
                      pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 3 and r["pendiente"] == 0


def test_no_reprocesa_completadas(tmp_path):
    lm = _libro(tmp_path, 2)
    lm.marcar("TX-000001", "completado")
    procesar_lote(lm, TecleadorFake(), LocalizadorFake(), ControlLote(),
                  pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    # la ya completada sigue una sola vez; ambas quedan completado, ninguna duplicada
    assert lm.contadores()["completado"] == 2


def test_aborto_detiene_y_devuelve_actual_a_pendiente(tmp_path):
    lm = _libro(tmp_path, 3)
    control = ControlLote()
    # localizador que falla -> simula que no se pudo enviar la primera
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(fallar={"adicionar"}),
                      control, pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 0
    assert r["pendiente"] == 3   # la que se intentó volvió a pendiente


def test_abortar_por_control_corta_el_bucle(tmp_path):
    lm = _libro(tmp_path, 3)
    control = ControlLote(); control.abortar()
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(), control,
                      pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 0 and r["pendiente"] == 3
```

- [ ] **Step 2: FAIL** — `.venv/Scripts/python -m pytest tests/test_lote.py -q`

- [ ] **Step 3: Implementar** `src/siat/lote.py`:

```python
"""Orquesta el bucle 'Cargar todos': recorre las tarjetas pendientes, las escribe
en el SIAT y las marca completado, respetando pausa/aborto y sin reprocesar las ya
completadas.
"""
import threading
import time

from .rellenador import cargar_registro, enviar_y_reabrir, SECUENCIA_RCV


class ControlLote:
    def __init__(self):
        self._pausa = threading.Event()
        self._aborto = threading.Event()

    def pausar(self): self._pausa.set()
    def reanudar(self): self._pausa.clear()
    def abortar(self): self._aborto.set()
    def esta_pausado(self) -> bool: return self._pausa.is_set()
    def esta_abortado(self) -> bool: return self._aborto.is_set()


def procesar_lote(libro, tecleador, localizador, control, secuencia=None,
                  pausa_campo=0.35, pausa_envio=0.6, al_cambiar=None,
                  dormir=time.sleep) -> dict:
    secuencia = secuencia or SECUENCIA_RCV

    def cambiar(tx_id, estado):
        libro.marcar(tx_id, estado)
        if al_cambiar:
            al_cambiar(tx_id, estado)

    while True:
        pendientes = libro.pendientes()
        if not pendientes or control.esta_abortado():
            break
        tx = pendientes[0]
        # Esperar mientras esté en pausa (nunca a mitad de una tarjeta).
        while control.esta_pausado() and not control.esta_abortado():
            dormir(0.1)
        if control.esta_abortado():
            break
        cambiar(tx["id"], "en_proceso")
        cargar_registro(tx["datos"], tecleador, secuencia, pausa=pausa_campo)
        if enviar_y_reabrir(localizador, pausa=pausa_envio):
            cambiar(tx["id"], "completado")
        else:
            # No se pudo enviar: devolver a pendiente y cortar sin clicar a ciegas.
            cambiar(tx["id"], "pendiente")
            break
    return libro.contadores()
```

- [ ] **Step 4: PASS** — `.venv/Scripts/python -m pytest tests/test_lote.py -q`
- [ ] **Step 5: Commit** — `git commit -am "feat: orquestador del lote con pausa/aborto y sin reprocesar completadas"`

---

### Task 6: Atajos globales F8/F7/F9 (pynput)

**Files:**
- Create: `src/siat/atajos.py`
- Test: `tests/test_atajos.py`
- Modify: `requirements.txt` (agregar `pynput>=1.7`)

**Interfaces:**
- Produces:
  - `class AtajosGlobales(al_iniciar, al_pausar, al_detener, backend=None)`: `iniciar()` arranca la escucha, `detener()` la para. Mapea F8→al_iniciar, F7→al_pausar, F9→al_detener.
  - Método interno `_procesar_tecla(nombre: str)` (público para tests) que dispara el callback según `"f8"|"f7"|"f9"`.
  - `backend` inyectable (con `iniciar(on_press)`/`detener()`); si None usa `pynput.keyboard.Listener` (import perezoso).

- [ ] **Step 1: Test** `tests/test_atajos.py`:

```python
from src.siat.atajos import AtajosGlobales


def test_mapea_teclas_a_callbacks():
    eventos = []
    a = AtajosGlobales(al_iniciar=lambda: eventos.append("i"),
                       al_pausar=lambda: eventos.append("p"),
                       al_detener=lambda: eventos.append("d"),
                       backend=object())
    a._procesar_tecla("f8")
    a._procesar_tecla("f7")
    a._procesar_tecla("f9")
    assert eventos == ["i", "p", "d"]


def test_tecla_desconocida_no_hace_nada():
    a = AtajosGlobales(lambda: None, lambda: None, lambda: None, backend=object())
    a._procesar_tecla("a")  # no debe lanzar
```

- [ ] **Step 2: FAIL** — `.venv/Scripts/python -m pytest tests/test_atajos.py -q`

- [ ] **Step 3: Implementar** `src/siat/atajos.py` y agregar `pynput>=1.7` a `requirements.txt`:

```python
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
```

- [ ] **Step 4: PASS** — `.venv/Scripts/python -m pytest tests/test_atajos.py -q` y `.venv/Scripts/python -m pip install pynput`

- [ ] **Step 5: Commit** — `git commit -am "feat: atajos globales F8/F7/F9 con pynput"`

---

### Task 7: Asistente de calibración (captura de recuadro)

**Files:**
- Create: `src/gui/calibracion.py`
- Test: manual (overlay gráfico; sin test automatizado).

**Interfaces:**
- Consumes: `ANCLAS` (Task 3), PyQt6.
- Produces:
  - `class OverlayRecorte(QWidget)`: overlay a pantalla completa que muestra una captura y deja arrastrar un rectángulo; al soltar emite `recorte_listo(QRect)` y se cierra.
  - `def calibrar_anclas(parent, dir_calibracion) -> bool`: para cada ancla de `ANCLAS`, pide al usuario dejar visible el formulario, toma captura de pantalla completa (`QScreen.grabWindow(0)`), abre `OverlayRecorte`, y guarda el recorte en `dir_calibracion/<ancla>.png`. Devuelve True si se calibraron todas.

- [ ] **Step 1: Implementar** `src/gui/calibracion.py`:

```python
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
```

- [ ] **Step 2: Verificación manual** — abrir la app, entrar a calibración, capturar los 3 recortes; confirmar que aparecen en `datos/calibracion/`.
- [ ] **Step 3: Commit** — `git commit -am "feat: asistente de calibración por recorte de pantalla"`

---

### Task 8: Integración GUI + verificación final

**Files:**
- Modify: `src/gui/app.py`
- Modify: `config/config.json` (agregar `"ruta_calibracion": "datos/calibracion"`)

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Cablear estados, botón por fila (verde/rojo) y advertencia de completado.**

En `_refrescar_tabla`, el botón de la última columna refleja el armado y bloquea completado:

```python
btn = QPushButton("Cargar")
completado = tx["estado"] == "completado"
armada = (self._fila_armada == tx["id"])
if completado:
    btn.setText("✓ Completado"); btn.setEnabled(False)
elif armada:
    btn.setObjectName("btnRojo"); btn.setText("✖ Cancelar")
else:
    btn.setObjectName("btnCargarFila")
    btn.setEnabled(not invalido and not self._cargando)
btn.clicked.connect(partial(self._toggle_armar_fila, tx["id"]))
self.tabla.setCellWidget(fila, len(self.COLUMNAS) - 1, btn)
```

Añadir estilo `#btnRojo { background:#b3261e; border-color:#b3261e; color:white; }` a `_ESTILO`, y en `__init__` inicializar `self._fila_armada = None` y `self._modo_todos = False`.

Método:

```python
def _toggle_armar_fila(self, tx_id):
    if not self.libro.puede_cargar(tx_id):
        QMessageBox.warning(self, "Ya completada",
                            "Esta tarjeta ya fue cargada. No se puede volver a cargar.")
        return
    self._modo_todos = False
    self._fila_armada = None if self._fila_armada == tx_id else tx_id
    self.etiqueta_lectura.setText(
        "Ve al formulario, clic en NIT y presiona F8." if self._fila_armada
        else "Carga individual cancelada.")
    self._refrescar_tabla()
```

- [ ] **Step 2: Botones "Cargar todos" / "Pausar" y selección múltiple.**

En `_panel_tabla`, activar multi-selección y agregar botones:

```python
self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
self.tabla.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
```

```python
self.btn_todos = QPushButton("▶ Cargar todos"); self.btn_todos.setObjectName("btnPrimario")
self.btn_todos.clicked.connect(self._toggle_cargar_todos)
self.btn_pausar = QPushButton("⏸ Pausar"); self.btn_pausar.setEnabled(False)
self.btn_pausar.clicked.connect(self._toggle_pausa)
self.btn_sel_todo = QPushButton("Seleccionar todo")
self.btn_sel_todo.clicked.connect(self.tabla.selectAll)
self.btn_estado = QPushButton("Marcar saltado (sel.)")
self.btn_estado.clicked.connect(lambda: self._estado_masa("saltado"))
self.btn_calibrar = QPushButton("⚙ Calibrar")
self.btn_calibrar.clicked.connect(self._calibrar)
```

Añadirlos a la fila de acciones (junto a los existentes Ver/Excel/Borrar/Vaciar).

- [ ] **Step 3: Métodos de lote, pausa, selección en masa y calibración.**

```python
def _ids_seleccionados(self):
    ids = []
    for idx in self.tabla.selectionModel().selectedRows(1):
        ids.append(idx.data())
    return ids

def _estado_masa(self, estado):
    ids = self._ids_seleccionados()
    if not ids:
        QMessageBox.information(self, "Selección", "Selecciona una o más filas.")
        return
    self.libro.marcar_varias(ids, estado)
    self._refrescar_tabla()

def _calibrar(self):
    from src.gui.calibracion import calibrar_anclas
    ruta = self.config.get("ruta_calibracion", "datos/calibracion")
    if calibrar_anclas(self, ruta):
        QMessageBox.information(self, "Calibración", "Listo, las 3 imágenes se guardaron.")

def _toggle_cargar_todos(self):
    from src.siat.localizador import Localizador
    ruta = self.config.get("ruta_calibracion", "datos/calibracion")
    loc = Localizador(ruta)
    if not loc.disponible():
        QMessageBox.warning(self, "Falta calibrar",
                            "Primero presiona «Calibrar» (una vez por PC).")
        return
    self._fila_armada = None
    self._modo_todos = not self._modo_todos
    self.btn_todos.setText("■ Detener modo" if self._modo_todos else "▶ Cargar todos")
    self.etiqueta_lectura.setText(
        "Ve al formulario, clic en NIT y presiona F8." if self._modo_todos
        else "Modo Cargar todos apagado.")

def _toggle_pausa(self):
    if getattr(self, "_control", None) is None:
        return
    if self._control.esta_pausado():
        self._control.reanudar(); self.btn_pausar.setText("⏸ Pausar")
    else:
        self._control.pausar(); self.btn_pausar.setText("▶ Reanudar")
```

- [ ] **Step 4: Hilo del lote + wiring de F8/F7/F9.**

Crear `src/gui/hilo_lote.py`:

```python
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
```

En `VentanaPrincipal.__init__`, crear los atajos:

```python
from src.siat.atajos import AtajosGlobales
from src.siat.lote import ControlLote
self._control = None
self._atajos = AtajosGlobales(self._f8, self._toggle_pausa, self._f9)
self._atajos.iniciar()
```

Métodos F8/F9 (con `cargar_registro`/`TecleadorReal` para el individual, e `HiloLote` para todos):

```python
def _f8(self):
    if self._modo_todos:
        self._control = ControlLote()
        self.btn_pausar.setEnabled(True); self._cargando = True; self._refrescar_tabla()
        self._hilo = HiloLote(self.libro, self._control, self.config)
        self._hilo.cambio.connect(lambda *_: self._refrescar_tabla())
        self._hilo.terminado.connect(self._lote_termino)
        self._hilo.start()
    elif self._fila_armada:
        from src.siat.rellenador import cargar_registro, TecleadorReal
        tx = self._tx_por_id(self._fila_armada)
        cargar_registro(tx["datos"], TecleadorReal(
            float(self.config.get("carga_intervalo_tecla", 0.05))),
            pausa=float(self.config.get("carga_pausa_campo", 0.35)))
        self.libro.marcar(self._fila_armada, "completado")
        self.etiqueta_lectura.setText(f"✔ {self._fila_armada} escrita. Presiona Adicionar.")
        self._fila_armada = None; self._refrescar_tabla()

def _f9(self):
    if self._control is not None:
        self._control.abortar()
    self._fila_armada = None; self._modo_todos = False
    self.btn_todos.setText("▶ Cargar todos")

def _lote_termino(self, resumen):
    self._cargando = False; self._modo_todos = False; self._control = None
    self.btn_pausar.setEnabled(False); self.btn_todos.setText("▶ Cargar todos")
    self._refrescar_tabla()
    if resumen["completado"] and QMessageBox.question(
            self, "Respaldo", "¿Guardar un Excel con las tarjetas cargadas?"
            ) == QMessageBox.StandardButton.Yes:
        self._exportar_completadas()

def _exportar_completadas(self):
    comp = [t for t in self.libro.todas() if t["estado"] == "completado"]
    ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "compras_rcv.xlsx", "Excel (*.xlsx)")
    if ruta:
        generar_excel_compras(comp, ruta)
        QMessageBox.information(self, "Excel", f"Guardadas {len(comp)} tarjetas.")
```

En `closeEvent`, agregar `self._atajos.detener()` antes de cerrar la cámara.

- [ ] **Step 5: Verificación final.**

Run: `.venv/Scripts/python -m pytest -q -p no:warnings`
Expected: todos los tests en verde.

Smoke: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python -c "import json; from PyQt6.QtWidgets import QApplication; QApplication([]); from src.gui.app import VentanaPrincipal; v=VentanaPrincipal(json.load(open('config/config.json'))); v._refrescar_tabla(); print('OK')"`
Expected: `OK`.

- [ ] **Step 6: Commit** — `git commit -am "feat: GUI de carga por lotes (F8/F7/F9, cargar todos, pausa, selección múltiple, calibración)"`

---

## Self-review del plan

- **Cobertura del spec:** estados nuevos + bloqueo recarga + cambio en masa ✔ (T1); Excel corregido + Fecha de Registro ✔ (T2); localizador por imagen ✔ (T3); enviar/reabrir ✔ (T4); bucle con pausa/aborto/no-reprocesar ✔ (T5); atajos F8/F7/F9 ✔ (T6); calibración ✔ (T7); GUI (botón fila verde/rojo, cargar todos, pausa, selección múltiple, advertencia completado, prompt Excel, wiring) ✔ (T8).
- **Placeholders:** ninguno; todo el código concreto. `config.json` gana `carga_pausa_envio` (usado en T8) — agregarlo junto a `ruta_calibracion` en el Step 1 de T8.
- **Consistencia de tipos:** `ControlLote`, `procesar_lote`, `enviar_y_reabrir`, `Localizador.clic`, `AtajosGlobales`, `marcar_varias`, `puede_cargar`, `generar_excel_compras(...fecha_registro=)` usados con las mismas firmas en T1–T8.
