# Lector SIAT — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Software de escritorio que lee tarjetas prepago (Entel/Tigo/Viva) con cámara USB, extrae datos fiscales (QR→OCR), los gestiona en un Libro Mayor JSON resiliente y los registra en el RCV del SIAT vía Selenium (individual) o Excel (masivo), probado contra un mock fiel del portal real.

**Architecture:** Módulos desacoplados en `src/` (captura, extracción, libro_mayor, siat, gui) que se comunican por el dataclass `DatosFiscales` y la clase `LibroMayor`. El RPA lee URLs/selectores de `config/selectores_siat.json` (perfiles `mock`/`real`). Mock Flask replica el portal real capturado con Playwright en `referencia_siat/`.

**Tech Stack:** Python 3.11+, OpenCV, pyzbar, PaddleOCR, Selenium 4, Flask, openpyxl, PyQt6, pytest.

## Global Constraints

- **Principio rector:** nos acoplamos a la página del SIAT, nunca al revés. Todo selector/template del mock nace de una captura Playwright del portal real (`referencia_siat/`).
- Estados del Libro Mayor, exactos: `pendiente`, `en_proceso`, `exitoso`, `fallido`, `saltado`.
- Lote RPA = 5 transacciones; timeout de confirmación = 60 s; ante fallo: marcar `fallido` y **detener todo**.
- Escritura del JSON siempre atómica (tmp + `os.replace`).
- NITs operadoras: Entel `1020703023`, Tigo `272902028`, Viva `1025260015`.
- Selenium: solo esperas explícitas (`WebDriverWait`), jamás `time.sleep` fijo para sincronizar.
- Código y comentarios en español (proyecto académico boliviano).
- Login real (perfil `real`, capturado 2026-07-04): form `#kc-form-login`, campos `#nitCur`, `#email`, `#password`, botón `#kc-login`. El mock DEBE usar estos mismos ids.

---

### Task 1: Scaffolding del proyecto

**Files:**
- Create: `requirements.txt`, `.gitignore`, `pytest.ini`, `config/config.json`, `config/selectores_siat.json`, `src/__init__.py`, `src/extraccion/__init__.py`, `src/captura/__init__.py`, `src/libro_mayor/__init__.py`, `src/siat/__init__.py`, `src/gui/__init__.py`, `tests/__init__.py`, `datos/capturas/.gitkeep`
- Copy: `../recuperado/paddle_ocr/*` → `modelos_ocr/`

**Interfaces:**
- Produces: layout de paquetes importable (`from src.extraccion import ...`), configs que consumen Tasks 6–9.

- [ ] **Step 1: Crear archivos de configuración y estructura**

`requirements.txt`:
```
opencv-python>=4.9
pyzbar>=0.1.9
paddleocr>=2.7,<3
paddlepaddle>=2.6
selenium>=4.20
flask>=3.0
openpyxl>=3.1
PyQt6>=6.6
pytest>=8.0
qrcode[pil]>=7.4
pillow>=10.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
datos/libro_mayor.json
datos/capturas/*.png
*.xlsx
```

`config/config.json`:
```json
{
  "camara_indice": 0,
  "tamano_lote": 5,
  "timeout_confirmacion_seg": 60,
  "perfil_siat": "mock",
  "ruta_libro_mayor": "datos/libro_mayor.json",
  "ruta_capturas": "datos/capturas",
  "ruta_modelos_ocr": "modelos_ocr"
}
```

`config/selectores_siat.json` (perfil `real`: login capturado con Playwright; el resto se llenará el día del dry-run inspeccionando el portal logueado — el mock usa los MISMOS ids que ya conocemos del real):
```json
{
  "mock": {
    "url_login": "http://127.0.0.1:5001/",
    "url_registro_compra": "http://127.0.0.1:5001/rcv/compras/registro",
    "login": {"nit": "#nitCur", "email": "#email", "password": "#password", "boton": "#kc-login"},
    "compra": {
      "nit_proveedor": "#nitProveedor",
      "codigo_autorizacion": "#codigoAutorizacion",
      "numero_factura": "#numeroFactura",
      "fecha": "#fechaFactura",
      "importe": "#importeTotal",
      "tipo_compra": "#tipoCompra",
      "codigo_control": "#codigoControl",
      "boton_registrar": "#btnRegistrar",
      "mensaje_exito": ".mensaje-exito",
      "mensaje_error": ".mensaje-error"
    }
  },
  "real": {
    "url_login": "https://siat.impuestos.gob.bo/",
    "url_registro_compra": "PENDIENTE_CAPTURAR_LOGUEADO",
    "login": {"nit": "#nitCur", "email": "#email", "password": "#password", "boton": "#kc-login"},
    "compra": {"_nota": "capturar con Playwright en el dry-run; mismas claves que mock"}
  }
}
```

- [ ] **Step 2: Copiar modelos OCR**

```bash
mkdir -p modelos_ocr && cp -r "../recuperado/paddle_ocr/." modelos_ocr/
```

- [ ] **Step 3: Verificar** — `python -c "import src"` sin error (crear todos los `__init__.py` vacíos).

- [ ] **Step 4: Commit** — `git add -A && git commit -m "chore: scaffolding del proyecto lector-siat"`

---

### Task 2: `DatosFiscales` + extractor fiscal (port del motor v4 de Bolifactura)

**Files:**
- Create: `src/extraccion/datos_fiscales.py`, `src/extraccion/extractor_fiscal.py`
- Test: `tests/test_extractor_fiscal.py`

**Interfaces:**
- Produces:
  - `DatosFiscales` (dataclass): campos `nit: str|None`, `numero_factura: str|None`, `autorizacion: str|None`, `fecha: str|None` (dd/mm/aaaa), `importe: str|None` (decimal con punto), `operadora: str|None` ("ENTEL"|"TIGO"|"VIVA"|None), `origen: str` ("qr"|"ocr"|"manual").
  - `extraer_de_lineas(lineas: list[str]) -> DatosFiscales`
  - `detectar_operadora(texto: str) -> str|None`
  - Constante `NITS_OPERADORAS: dict[str, str]` = {"1020703023": "ENTEL", "272902028": "TIGO", "1025260015": "VIVA"}

- [ ] **Step 1: Escribir tests que fallan** — `tests/test_extractor_fiscal.py` con fixtures de texto OCR realistas (basadas en el motor Dart de Bolifactura):

```python
from src.extraccion.extractor_fiscal import extraer_de_lineas, detectar_operadora

LINEAS_ENTEL = [
    "ENTEL S.A.", "NIT: 1020703023", "FACTURA N°:", "000.104.827",
    "AUTORIZACION: 300400500600", "FECHA LIMITE DE EMISION: 31/12/2026",
    "IMPORTE Bs. 10.00", "TARJETA PREPAGO",
]
LINEAS_TIGO = [
    "TELECEL S.A. - TIGO", "N.I.T. 272902028", "NRO = 778588",
    "Telf: 800-17-2000", "FECHA: 05/03/2026", "MONTO A PAGAR Bs 20,00",
]
LINEAS_VIVA = [
    "NUEVATEL PCS DE BOLIVIA S.A.", "NIT 1025260015", "FACTURA N°_:",
    "598786", "26 de abril de 2026", "TOTAL BS: 15.00",
]

def test_entel_extrae_todos_los_campos():
    d = extraer_de_lineas(LINEAS_ENTEL)
    assert d.nit == "1020703023"
    assert d.numero_factura == "104827"      # normaliza puntos y ceros a la izquierda
    assert d.fecha == "31/12/2026"
    assert d.importe == "10.00"
    assert d.operadora == "ENTEL"

def test_tigo_ignora_telefono_y_extrae():
    d = extraer_de_lineas(LINEAS_TIGO)
    assert d.nit == "272902028"
    assert d.numero_factura == "778588"
    assert d.fecha == "05/03/2026"
    assert d.importe == "20.00"              # normaliza coma decimal
    assert d.operadora == "TIGO"

def test_viva_numero_en_linea_siguiente_y_fecha_larga():
    d = extraer_de_lineas(LINEAS_VIVA)
    assert d.nit == "1025260015"
    assert d.numero_factura == "598786"
    assert d.fecha == "26/04/2026"
    assert d.importe == "15.00"
    assert d.operadora == "VIVA"

def test_no_confunde_telefono_con_nit():
    d = extraer_de_lineas(["TELF: 800-17-2000", "SIN MAS DATOS"])
    assert d.nit is None

def test_detectar_operadora_por_texto():
    assert detectar_operadora("recarga TIGO bolivia") == "TIGO"
    assert detectar_operadora("nada que ver") is None
```

- [ ] **Step 2: Correr y verificar FAIL** — `pytest tests/test_extractor_fiscal.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implementar** — `src/extraccion/datos_fiscales.py`:

```python
from dataclasses import dataclass, field

@dataclass
class DatosFiscales:
    nit: str | None = None
    numero_factura: str | None = None
    autorizacion: str | None = None
    fecha: str | None = None       # dd/mm/aaaa
    importe: str | None = None     # "10.00"
    operadora: str | None = None   # ENTEL | TIGO | VIVA
    origen: str = "ocr"            # qr | ocr | manual

    def campos_faltantes(self) -> list[str]:
        obligatorios = {"nit": self.nit, "numero_factura": self.numero_factura,
                        "fecha": self.fecha, "importe": self.importe}
        return [k for k, v in obligatorios.items() if not v]
```

`src/extraccion/extractor_fiscal.py` — port fiel de las heurísticas v4 de `ocr_service.dart` (regex NIT/fecha/monto/factura, etiquetas robustas, anti-teléfono/lote/orden, fecha larga española, normalización de puntos y comas, número en línea siguiente). Puntos clave del port:

```python
import re
from .datos_fiscales import DatosFiscales

NITS_OPERADORAS = {"1020703023": "ENTEL", "272902028": "TIGO", "1025260015": "VIVA"}

RE_NIT = re.compile(r"\b\d{7,11}\b")
RE_NIT_ETIQUETA = re.compile(r"N\.?I\.?T\.?\s*[:=]?\s*(\d{7,11})", re.I)
RE_FECHA = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
RE_FECHA_LARGA = re.compile(
    r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})\b", re.I)
MESES = {"enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
         "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"}
RE_MONTO_BS = re.compile(r"(?:Bs\.?|BS\.?)\s*:?\s*([\d]+(?:[.,]\d{1,2})?)", re.I)
RE_ETIQUETA_FACTURA = re.compile(
    r"FACTURA\s*N[°ºO]?[_:\s]*|NRO\.?\s*[=:]\s*|N[°º]\s*FACTURA|NUMERO\s*DE\s*FACTURA", re.I)
RE_TELEFONO = re.compile(r"TEL\.?F?\.?|TELEFONO|TELÉFONO", re.I)

def detectar_operadora(texto: str) -> str | None: ...
def _es_telefono(linea: str) -> bool: ...
def _extraer_nit(linea: str) -> str | None: ...
def _extraer_fecha(linea: str) -> str | None: ...       # corta + larga + año de 2 dígitos
def _extraer_monto(linea: str) -> str | None: ...       # normaliza "20,00"->"20.00"
def _normalizar_numero_factura(crudo: str) -> str: ...  # quita puntos y ceros izq.
def extraer_de_lineas(lineas: list[str]) -> DatosFiscales: ...
# Recorre líneas con ventana (anterior/actual/siguiente) igual que el motor Dart:
# NIT solo antes de la línea del NIT-cliente; etiqueta de factura acepta número
# en la misma línea o la siguiente; montos priorizan etiquetas IMPORTE/MONTO/TOTAL.
```

(El cuerpo completo se escribe en la implementación siguiendo `recuperado/motor_ocr_referencia/ocr_service.dart` funciones `_extractNitDesdeLinea`, `_extractFecha`, `_extractMonto`, `_esEtiquetaFacturaRobusta`, `_normalizarNumeroFactura`, `_esNumeroIgnorable`, `_detectarTarjetaPrepago`.)

- [ ] **Step 4: Correr tests hasta PASS** — `pytest tests/test_extractor_fiscal.py -v`.

- [ ] **Step 5: Commit** — `git commit -m "feat: extractor fiscal (port del motor v4 de Bolifactura)"`

---

### Task 3: Validador

**Files:**
- Create: `src/extraccion/validador.py`
- Test: `tests/test_validador.py`

**Interfaces:**
- Consumes: `DatosFiscales`, `NITS_OPERADORAS`.
- Produces: `validar(datos: DatosFiscales) -> list[str]` (lista de errores en español; vacía = válido).

- [ ] **Step 1: Tests que fallan**

```python
from src.extraccion.datos_fiscales import DatosFiscales
from src.extraccion.validador import validar

def _datos_ok():
    return DatosFiscales(nit="1020703023", numero_factura="104827",
                         autorizacion="300400500600", fecha="31/12/2026",
                         importe="10.00", operadora="ENTEL")

def test_datos_completos_sin_errores():
    assert validar(_datos_ok()) == []

def test_nit_corto_es_error():
    d = _datos_ok(); d.nit = "12345"
    assert any("NIT" in e for e in validar(d))

def test_nit_desconocido_advierte_operadora():
    d = _datos_ok(); d.nit = "9999999999"; d.operadora = None
    assert any("operadora" in e.lower() for e in validar(d))

def test_fecha_invalida():
    d = _datos_ok(); d.fecha = "45/13/2026"
    assert any("fecha" in e.lower() for e in validar(d))

def test_importe_cero_o_negativo():
    d = _datos_ok(); d.importe = "0"
    assert any("importe" in e.lower() for e in validar(d))
```

- [ ] **Step 2: FAIL** → **Step 3: Implementar** (`datetime.strptime` para fecha, `float()` para importe, largo 7-11 para NIT, advertencia si NIT ∉ NITS_OPERADORAS) → **Step 4: PASS** → **Step 5: Commit** `feat: validador de datos fiscales`.

---

### Task 4: Lector QR

**Files:**
- Create: `src/extraccion/qr_lector.py`
- Test: `tests/test_qr_lector.py`

**Interfaces:**
- Consumes: `DatosFiscales`, `NITS_OPERADORAS`.
- Produces: `leer_qr(imagen_bgr) -> DatosFiscales | None` (None si no hay QR legible); `parsear_contenido_qr(texto: str) -> DatosFiscales | None` (según informe: NIT + autorización "de forma seguida"; también acepta URLs del SIAT con querystring `nit=...&aut=...`).

- [ ] **Step 1: Tests que fallan** (generan QR sintético con `qrcode` + numpy/cv2):

```python
import numpy as np, qrcode, cv2
from src.extraccion.qr_lector import leer_qr, parsear_contenido_qr

def _img_qr(payload: str):
    pil = qrcode.make(payload).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def test_parsea_nit_y_autorizacion_seguidos():
    d = parsear_contenido_qr("1020703023300400500600")
    assert d.nit == "1020703023" and d.autorizacion == "300400500600"
    assert d.operadora == "ENTEL" and d.origen == "qr"

def test_parsea_url_siat_con_parametros():
    d = parsear_contenido_qr("https://siat.impuestos.gob.bo/consulta/QR?nit=272902028&numFactura=778588&aut=112233")
    assert d.nit == "272902028" and d.numero_factura == "778588"

def test_leer_qr_desde_imagen():
    d = leer_qr(_img_qr("1020703023300400500600"))
    assert d is not None and d.nit == "1020703023"

def test_imagen_sin_qr_devuelve_none():
    assert leer_qr(np.zeros((100, 100, 3), dtype=np.uint8)) is None
```

- [ ] **Step 2: FAIL** → **Step 3: Implementar** (pyzbar `decode`; si falla, fallback `cv2.QRCodeDetector`; parseo: si empieza con NIT de operadora conocida → separar prefijo; si es URL → querystring) → **Step 4: PASS** → **Step 5: Commit** `feat: lector y parser de QR`.

---

### Task 5: Motor OCR (wrapper PaddleOCR)

**Files:**
- Create: `src/extraccion/ocr_motor.py`
- Test: `tests/test_ocr_motor.py` (integración, `@pytest.mark.skipif` si no están los modelos)

**Interfaces:**
- Produces: `class OcrMotor: def __init__(self, ruta_modelos: str)` (carga perezosa) y `def leer_lineas(self, imagen_bgr) -> list[str]`.

- [ ] **Step 1: Test de integración** (imagen sintética con texto "NIT: 1020703023" dibujado con PIL; skip si `modelos_ocr/` vacío o paddle no instalado). **Step 2: FAIL** → **Step 3: Implementar** (PaddleOCR con `det_model_dir`/`rec_model_dir`/`rec_char_dict_path` apuntando a `modelos_ocr/` — igual que `recuperado/paddle_ocr/probar.py`) → **Step 4: PASS/SKIP** → **Step 5: Commit** `feat: motor OCR con PaddleOCR local`.

---

### Task 6: Libro Mayor

**Files:**
- Create: `src/libro_mayor/libro_mayor.py`
- Test: `tests/test_libro_mayor.py`

**Interfaces:**
- Consumes: `DatosFiscales`.
- Produces:
  - `ESTADOS = ("pendiente", "en_proceso", "exitoso", "fallido", "saltado")`
  - `class LibroMayor(ruta: str)`: `agregar(datos: DatosFiscales) -> str` (id `TX-000001`), `pendientes() -> list[dict]`, `todas() -> list[dict]`, `marcar(tx_id: str, estado: str, detalle: str = "") -> None`, `contadores() -> dict[str, int]`, `siguiente_lote(n: int) -> list[dict]`.
  - Persistencia: JSON `{"transacciones": [{"id", "estado", "detalle", "creado", "actualizado", "datos": {...}}]}`; cada mutación guarda atómico (tmp + `os.replace`).

- [ ] **Step 1: Tests que fallan**

```python
import json
from src.extraccion.datos_fiscales import DatosFiscales
from src.libro_mayor.libro_mayor import LibroMayor

def _d(): return DatosFiscales(nit="1020703023", numero_factura="104827",
                               fecha="31/12/2026", importe="10.00")

def test_agregar_y_leer(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    tx = lm.agregar(_d())
    assert tx == "TX-000001"
    assert lm.contadores()["pendiente"] == 1

def test_persistencia_y_reanudacion(tmp_path):
    ruta = str(tmp_path / "lm.json")
    lm = LibroMayor(ruta); lm.agregar(_d()); lm.agregar(_d())
    lm.marcar("TX-000001", "exitoso")
    lm2 = LibroMayor(ruta)  # reabrir = reiniciar el sistema
    assert [t["id"] for t in lm2.pendientes()] == ["TX-000002"]

def test_estado_invalido_lanza(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json")); lm.agregar(_d())
    import pytest
    with pytest.raises(ValueError): lm.marcar("TX-000001", "volando")

def test_escritura_atomica_no_deja_tmp(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json")); lm.agregar(_d())
    assert list(tmp_path.glob("*.tmp")) == []
    json.loads((tmp_path / "lm.json").read_text(encoding="utf-8"))  # JSON válido

def test_siguiente_lote_de_cinco(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for _ in range(7): lm.agregar(_d())
    assert len(lm.siguiente_lote(5)) == 5
```

- [ ] **Step 2: FAIL** → **Step 3: Implementar** → **Step 4: PASS** → **Step 5: Commit** `feat: libro mayor con estados y escritura atómica`.

---

### Task 7: Generador Excel RCV (importación masiva)

**Files:**
- Create: `src/siat/excel_rcv.py`
- Test: `tests/test_excel_rcv.py`

**Interfaces:**
- Consumes: transacciones (dicts del Libro Mayor).
- Produces: `generar_excel_compras(transacciones: list[dict], ruta_salida: str, razon_social_por_defecto: str = "") -> int` (filas escritas). Columnas oficiales del formato de importación del RCV (verificar contra el formato descargable del portal el día del dry-run — regla: acoplarse a la página): `Nº, ESPECIFICACION, NIT PROVEEDOR, RAZON SOCIAL PROVEEDOR, CODIGO DE AUTORIZACION, NUMERO FACTURA, NUMERO DUI/DIM, FECHA DE FACTURA/DUI/DIM, IMPORTE TOTAL COMPRA, IMPORTE ICE, IMPORTE IEHD, IMPORTE IPJ, TASAS, OTRO NO SUJETO A CREDITO FISCAL, IMPORTES EXENTOS, IMPORTE COMPRAS GRAVADAS A TASA CERO, SUBTOTAL, DESCUENTOS/BONIFICACIONES/REBAJAS SUJETAS AL IVA, IMPORTE GIFT CARD, IMPORTE BASE CF, CREDITO FISCAL, TIPO COMPRA, CODIGO DE CONTROL`. Reglas: ESPECIFICACION=1, importes no aplicables=0, SUBTOTAL=IMPORTE TOTAL, BASE CF=SUBTOTAL, CREDITO FISCAL=round(base*0.13,2), TIPO COMPRA=1, CODIGO DE CONTROL="0" (prevaloradas SIAT no llevan), sin espacios ni decimales espurios (causa de rechazo documentada).

- [ ] **Step 1: Tests que fallan** (abre el xlsx con openpyxl y verifica cabeceras exactas, fila de datos, crédito fiscal 13%, y que autorización no tenga espacios) → **Step 2: FAIL** → **Step 3: Implementar** → **Step 4: PASS** → **Step 5: Commit** `feat: generador Excel RCV importación masiva`.

---

### Task 8: Mock fiel del SIAT (Flask)

**Files:**
- Create: `mock_siat/servidor.py`, `mock_siat/templates/login.html`, `mock_siat/templates/menu.html`, `mock_siat/templates/registro_compra.html`, `mock_siat/static/estilo.css`
- Test: `tests/test_mock_siat.py` (Flask test client)

**Interfaces:**
- Produces: `crear_app(lento: bool = True, tasa_error: float = 0.10) -> Flask`; rutas `GET /` (login), `POST /login`, `GET|POST /rcv/compras/registro`, `GET /api/registradas` (JSON de facturas aceptadas, para asserts E2E); variable global reiniciable `REGISTRADAS`.
- **Fidelidad**: `login.html` replica `referencia_siat/siat-login-real.html` — MISMOS ids (`kc-form-login`, `nitCur`, `email`, `password`, `kc-login`), misma estética (fondo teal circuitos, tarjeta neón, título "IMPUESTOS NACIONALES", chips). El form de compras usa los ids de `selectores_siat.json` perfil mock y estética consistente con el portal (se ajustará al capturar el real logueado).

- [ ] **Step 1: Tests que fallan**

```python
from mock_siat.servidor import crear_app

def _cliente():
    app = crear_app(lento=False, tasa_error=0.0)
    return app.test_client()

def test_login_tiene_ids_reales_del_siat():
    html = _cliente().get("/").data.decode()
    for sel in ('id="kc-form-login"', 'id="nitCur"', 'id="email"', 'id="password"', 'id="kc-login"'):
        assert sel in html

def test_login_correcto_redirige_a_menu():
    r = _cliente().post("/login", data={"nitCur": "123456789", "email": "a@b.c", "password": "x"})
    assert r.status_code == 302

def test_registro_compra_exitoso_aparece_en_api():
    c = _cliente()
    c.post("/login", data={"nitCur": "1", "email": "a@b.c", "password": "x"})
    r = c.post("/rcv/compras/registro", data={
        "nitProveedor": "1020703023", "codigoAutorizacion": "300400500600",
        "numeroFactura": "104827", "fechaFactura": "31/12/2026",
        "importeTotal": "10.00", "tipoCompra": "1", "codigoControl": "0"})
    assert "mensaje-exito" in r.data.decode()
    assert c.get("/api/registradas").json[0]["numeroFactura"] == "104827"

def test_tasa_error_uno_siempre_falla():
    app = crear_app(lento=False, tasa_error=1.0)
    c = app.test_client()
    c.post("/login", data={"nitCur": "1", "email": "a@b.c", "password": "x"})
    r = c.post("/rcv/compras/registro", data={"nitProveedor": "1", "codigoAutorizacion": "1",
        "numeroFactura": "1", "fechaFactura": "01/01/2026", "importeTotal": "1", "tipoCompra": "1", "codigoControl": "0"})
    assert "mensaje-error" in r.data.decode()
```

- [ ] **Step 2: FAIL** → **Step 3: Implementar** (sesión Flask, `lento=True` añade `time.sleep(random.uniform(2,15))` para simular al SIAT real, error aleatorio según `tasa_error`; extraer del HTML capturado la paleta y estructura para `login.html` y `estilo.css`) → **Step 4: PASS** → **Step 5: Commit** `feat: mock fiel del portal SIAT con lentitud y errores simulados`.

---

### Task 9: Ejecutor RPA Selenium

**Files:**
- Create: `src/siat/rpa_selenium.py`
- Test: `tests/test_rpa_e2e.py` (E2E contra mock en hilo, Chrome headless; `@pytest.mark.e2e`)

**Interfaces:**
- Consumes: `LibroMayor`, `config/selectores_siat.json`, mock (Task 8).
- Produces:
  - `class Credenciales(NamedTuple)`: `nit: str, email: str, password: str`
  - `class EjecutorRPA(perfil: str, selectores: dict, libro: LibroMayor, credenciales: Credenciales, tamano_lote: int = 5, timeout: int = 60, headless: bool = True)`
  - `def procesar_todo(self, al_cambiar=None) -> dict` — devuelve contadores finales; `al_cambiar(tx_id, estado)` callback para la GUI.
  - Comportamiento: login → procesar lote de 5 (cada tx: `en_proceso` → llenar form → click → `WebDriverWait` hasta `mensaje_exito` (→`exitoso`) o `mensaje_error`/timeout 60 s (→`fallido` + **stop total**, cerrar navegador, preservar libro)) → relogin entre lotes → al terminar pendientes, cerrar.

- [ ] **Step 1: Tests E2E que fallan**

```python
import threading, pytest
from mock_siat.servidor import crear_app
from src.libro_mayor.libro_mayor import LibroMayor
from src.extraccion.datos_fiscales import DatosFiscales
from src.siat.rpa_selenium import EjecutorRPA, Credenciales
# fixture: levanta crear_app(lento=False, tasa_error=0.0) con werkzeug en hilo daemon, puerto 5001

def test_procesa_todo_exitoso(mock_server, tmp_path, selectores):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for i in range(6):
        lm.agregar(DatosFiscales(nit="1020703023", numero_factura=str(100+i),
                                 autorizacion="3004", fecha="31/12/2026", importe="10.00"))
    rpa = EjecutorRPA("mock", selectores, lm, Credenciales("123", "a@b.c", "x"))
    resumen = rpa.procesar_todo()
    assert resumen["exitoso"] == 6 and resumen["pendiente"] == 0  # 2 lotes con relogin

def test_error_detiene_todo_y_preserva_estado(mock_server_con_fallo_en_tercera, tmp_path, selectores):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for i in range(5): lm.agregar(DatosFiscales(nit="1", numero_factura=str(i),
                                  autorizacion="1", fecha="01/01/2026", importe="1.00"))
    rpa = EjecutorRPA("mock", selectores, lm, Credenciales("1", "a@b.c", "x"))
    resumen = rpa.procesar_todo()
    assert resumen["fallido"] == 1 and resumen["exitoso"] == 2 and resumen["pendiente"] == 2
```

(El mock necesita en Task 8 un modo determinista `fallar_en={n}` para el segundo test — añadirlo ahí si no existe.)

- [ ] **Step 2: FAIL** → **Step 3: Implementar** → **Step 4: PASS** (`pytest -m e2e -v`) → **Step 5: Commit** `feat: ejecutor RPA resiliente con lotes y relogueo`.

---

### Task 10: Captura (cámara + disparador desacoplado)

**Files:**
- Create: `src/captura/camara.py`, `src/captura/disparador.py`
- Test: `tests/test_disparador.py`

**Interfaces:**
- Produces:
  - `class Camara(indice: int = 0)`: `abrir()`, `leer_frame() -> ndarray|None`, `capturar(ruta_destino: str) -> str`, `cerrar()`.
  - `class Disparador(ABC)`: método `armar(callback)`; implementaciones `DisparadorManual` (la GUI/tecla llama `disparar()`) y `DisparadorSensorIR(puerto_serial)` (stub documentado: lee línea "TRIGGER" por pyserial — se completa cuando Adrián entregue la cajita; lanza `NotImplementedError` con mensaje claro si se usa sin hardware).
  - `class IndicadorLed(ABC)`: `verde()`, `rojo()`; implementaciones `LedVirtual` (callback a GUI) y `LedHardware` (stub igual que el sensor).

- [ ] **Step 1: Tests del disparador/led virtuales (sin hardware)** → **Step 2: FAIL** → **Step 3: Implementar** → **Step 4: PASS** → **Step 5: Commit** `feat: captura con disparador y LED desacoplados del hardware`.

---

### Task 11: GUI PyQt6

**Files:**
- Create: `src/gui/app.py`, `src/gui/hilo_rpa.py`
- Test: manual (checklist) — la GUI no lleva tests automatizados en este proyecto.

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `class VentanaPrincipal(QMainWindow)` con: vista de cámara en vivo (QTimer 30 fps), LED virtual (círculo verde/rojo), botón "Capturar (Espacio)", pipeline QR→OCR→validador al capturar, tabla del Libro Mayor con colores por estado, contadores, botones "Procesar en SIAT" (lanza `EjecutorRPA` en `QThread` con callback de progreso), "Exportar Excel RCV", "Marcar saltado", "Reintentar (→pendiente)"; diálogo de credenciales (nunca se guardan en disco).

- [ ] **Step 1: Implementar** → **Step 2: Checklist manual** (cámara visible, captura con tecla, tarjeta simulada procesada, tabla actualiza, RPA contra mock desde la GUI, exportar Excel abre archivo válido) → **Step 3: Commit** `feat: GUI PyQt6 completa`.

---

### Task 12: `main.py`, README y verificación final

**Files:**
- Create: `src/main.py`, `README.md`
- Modify: `config/config.json` si hizo falta.

- [ ] **Step 1: `main.py`** (carga configs, arranca GUI; `--sin-camara` para demo con imágenes de carpeta; `--mock` levanta mock_siat en subproceso para la demo completa con un solo comando).
- [ ] **Step 2: README** (instalación, cómo correr mock+app, cómo correr tests, cómo llenar el perfil `real` el día del dry-run — pasos Playwright para capturar el form logueado, advertencia legal: solo credenciales propias del contribuyente).
- [ ] **Step 3: Verificación completa** — `pytest -v` todo verde; flujo demo manual end-to-end contra el mock.
- [ ] **Step 4: Commit final** `docs: README y punto de entrada`.

---

## Self-review del plan

- **Cobertura del spec:** captura ✔ (T10), QR ✔ (T4), OCR ✔ (T5), extractor ✔ (T2), validador ✔ (T3), libro mayor ✔ (T6), RPA ✔ (T9), Excel ✔ (T7), mock fiel ✔ (T8), GUI ✔ (T11), configs/selectores ✔ (T1), principio de fidelidad ✔ (T1, T8, T12-README).
- **Placeholders:** el único "PENDIENTE" es el perfil `real` del form de compras — imposible de capturar sin credenciales; documentado como paso del dry-run en README (T12). Aceptado en el spec.
- **Consistencia de tipos:** `DatosFiscales`, `LibroMayor`, `EjecutorRPA`, `crear_app` usados con las mismas firmas en T2→T11.
