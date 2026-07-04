"""Ejecutor RPA resiliente para el registro de compras en el SIAT.

Implementa el mecanismo del informe: procesa el Libro Mayor en lotes, con
esperas explícitas, y ante el primer fallo (error del portal o timeout de 60 s)
marca la transacción como 'fallido' y DETIENE todo, preservando el estado para
poder reanudar exactamente donde quedó.

Nota (memoria del proyecto): el portal SIAT real detecta la automatización del
navegador (--disable-blink-features=AutomationControlled) y bloquea. Para el
dry-run real habrá que usar undetected-chromedriver o priorizar la vía Excel.
Contra el mock local esto no aplica.
"""
from typing import Callable, NamedTuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class Credenciales(NamedTuple):
    nit: str
    email: str
    password: str


class EjecutorRPA:
    def __init__(self, perfil: str, selectores: dict, libro,
                 credenciales: Credenciales, tamano_lote: int = 5,
                 timeout: int = 60, headless: bool = True):
        self.cfg = selectores[perfil]
        self.libro = libro
        self.credenciales = credenciales
        self.tamano_lote = tamano_lote
        self.timeout = timeout
        self.headless = headless
        self._driver = None

    # ── Navegador ─────────────────────────────────────────────────────────
    def _abrir_navegador(self):
        opciones = Options()
        if self.headless:
            opciones.add_argument("--headless=new")
        opciones.add_argument("--no-sandbox")
        opciones.add_argument("--disable-dev-shm-usage")
        # Reducir la huella de automatización (relevante para el SIAT real).
        opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
        opciones.add_experimental_option("useAutomationExtension", False)
        self._driver = webdriver.Chrome(options=opciones)

    def _cerrar_navegador(self):
        if self._driver is not None:
            self._driver.quit()
            self._driver = None

    def _login(self):
        d = self._driver
        d.get(self.cfg["url_login"])
        s = self.cfg["login"]
        WebDriverWait(d, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, s["nit"])))
        url_login = d.current_url
        d.find_element(By.CSS_SELECTOR, s["nit"]).send_keys(self.credenciales.nit)
        d.find_element(By.CSS_SELECTOR, s["email"]).send_keys(self.credenciales.email)
        d.find_element(By.CSS_SELECTOR, s["password"]).send_keys(self.credenciales.password)
        d.find_element(By.CSS_SELECTOR, s["boton"]).click()
        # Espera explícita a que el login se complete (la URL deja de ser la de login).
        WebDriverWait(d, self.timeout).until(lambda drv: drv.current_url != url_login)

    # ── Registro de una transacción ───────────────────────────────────────
    def _registrar(self, datos: dict) -> bool:
        """Llena y envía el formulario. True si el SIAT confirmó; False si falló."""
        d = self._driver
        s = self.cfg["compra"]
        d.get(self.cfg["url_registro_compra"])
        WebDriverWait(d, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, s["nit_proveedor"])))

        def escribir(selector, valor):
            campo = d.find_element(By.CSS_SELECTOR, selector)
            campo.clear()
            campo.send_keys(str(valor or ""))

        escribir(s["nit_proveedor"], datos.get("nit"))
        escribir(s["codigo_autorizacion"], datos.get("autorizacion"))
        escribir(s["numero_factura"], datos.get("numero_factura"))
        escribir(s["fecha"], datos.get("fecha"))
        escribir(s["importe"], datos.get("importe"))
        Select(d.find_element(By.CSS_SELECTOR, s["tipo_compra"])).select_by_value("1")
        escribir(s["codigo_control"], "0")

        d.find_element(By.CSS_SELECTOR, s["boton_registrar"]).click()

        # Espera activa: aparece el mensaje de éxito O el de error (lo que llegue).
        try:
            WebDriverWait(d, self.timeout).until(
                lambda drv: drv.find_elements(By.CSS_SELECTOR, s["mensaje_exito"])
                or drv.find_elements(By.CSS_SELECTOR, s["mensaje_error"]))
        except TimeoutException:
            return False  # 60 s sin respuesta = fallo
        return bool(d.find_elements(By.CSS_SELECTOR, s["mensaje_exito"]))

    # ── Bucle principal ───────────────────────────────────────────────────
    def procesar_todo(self, al_cambiar: Callable[[str, str], None] | None = None) -> dict:
        """Procesa todos los pendientes en lotes. Devuelve los contadores finales."""
        try:
            self._abrir_navegador()
            while True:
                lote = self.libro.siguiente_lote(self.tamano_lote)
                if not lote:
                    break
                self._login()  # relogueo al inicio de cada lote (evita vencimiento)
                for tx in lote:
                    self.libro.marcar(tx["id"], "en_proceso")
                    if al_cambiar:
                        al_cambiar(tx["id"], "en_proceso")
                    ok = self._registrar(tx["datos"])
                    if ok:
                        self.libro.marcar(tx["id"], "exitoso")
                        if al_cambiar:
                            al_cambiar(tx["id"], "exitoso")
                    else:
                        # Ante el primer fallo: marcar y DETENER todo.
                        self.libro.marcar(tx["id"], "fallido",
                                          "Error del SIAT o timeout; proceso detenido.")
                        if al_cambiar:
                            al_cambiar(tx["id"], "fallido")
                        return self.libro.contadores()
        finally:
            self._cerrar_navegador()
        return self.libro.contadores()
