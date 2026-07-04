"""Interfaz gráfica (PyQt6) del Lector SIAT.

Muestra la cámara en vivo, el LED virtual (verde/rojo), los contadores por
estado y la tabla del Libro Mayor, y ofrece los controles para capturar,
procesar en el SIAT (RPA en un hilo aparte), exportar el Excel del RCV y
gestionar manualmente las transacciones fallidas.
"""
import os

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QTableWidget, QTableWidgetItem, QDialog,
    QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox, QFileDialog,
    QHeaderView, QComboBox,
)

from src.captura.camara import Camara
from src.captura.indicador_led import LedVirtual
from src.extraccion.datos_fiscales import DatosFiscales
from src.extraccion.pipeline import PipelineExtraccion
from src.extraccion.validador import validar
from src.libro_mayor.libro_mayor import LibroMayor, ESTADOS
from src.siat.excel_rcv import generar_excel_compras
from src.siat.rpa_selenium import Credenciales
from src.gui.hilo_rpa import HiloRPA

_COLORES_ESTADO = {
    "pendiente": "#d9a441", "en_proceso": "#3794d6", "exitoso": "#3fb950",
    "fallido": "#f85149", "saltado": "#6e7681",
}

# Tema oscuro moderno neutro (estilo VS Code).
_ESTILO = """
QMainWindow, QWidget { background: #1e1e1e; color: #d4d4d4;
    font-family: 'Segoe UI', Roboto, sans-serif; font-size: 13px; }
QLabel { color: #d4d4d4; }
QPushButton { background: #2d2d30; color: #e8e8e8; border: 1px solid #3c3c3c;
    border-radius: 6px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #37373d; border-color: #0e7ac0; }
QPushButton:pressed { background: #094771; }
QPushButton:disabled { color: #6e6e6e; background: #262626; }
#btnPrimario { background: #0e7ac0; border-color: #0e7ac0; color: white; }
#btnPrimario:hover { background: #1a8ad4; }
QTableWidget { background: #252526; alternate-background-color: #2a2a2b;
    color: #d4d4d4; gridline-color: #3c3c3c; border: 1px solid #3c3c3c;
    border-radius: 8px; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #094771; color: white; }
QHeaderView::section { background: #2d2d30; color: #9da5b4; padding: 8px;
    border: none; border-bottom: 1px solid #3c3c3c; font-weight: 600; }
QLineEdit { background: #1a1a1a; color: #e8e8e8; border: 1px solid #3c3c3c;
    border-radius: 6px; padding: 8px; }
QLineEdit:focus { border-color: #0e7ac0; }
QDialog { background: #252526; }
"""


class DialogoCredenciales(QDialog):
    def __init__(self, parent=None, prefill: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Credenciales del contribuyente")
        prefill = prefill or {}
        form = QFormLayout(self)
        self.nit = QLineEdit(prefill.get("nit_cur_ci", ""))
        self.email = QLineEdit(prefill.get("email", ""))
        self.password = QLineEdit(prefill.get("password", ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("NIT / CUR / CI:", self.nit)
        form.addRow("Correo:", self.email)
        form.addRow("Contraseña:", self.password)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def credenciales(self) -> Credenciales:
        return Credenciales(self.nit.text().strip(), self.email.text().strip(),
                            self.password.text())


class DialogoDetalle(QDialog):
    """Muestra la foto de la tarjeta en grande y permite editar todos los campos."""

    CAMPOS = [
        ("nit", "NIT"), ("numero_factura", "N° Factura"),
        ("autorizacion", "Código de Autorización"), ("fecha", "Fecha (dd/mm/aaaa)"),
        ("importe", "Importe (Bs)"), ("operadora", "Operadora"),
    ]

    def __init__(self, parent, tx: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle {tx['id']} — verificar y editar")
        self.resize(760, 460)
        layout = QHBoxLayout(self)

        # Izquierda: la foto capturada, para verificar que la fila es esa tarjeta.
        img = QLabel("(sin imagen)")
        img.setMinimumSize(400, 400)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background:#141414;border:1px solid #3c3c3c;border-radius:8px;")
        ruta = tx.get("imagen")
        if ruta and os.path.exists(ruta):
            pix = QPixmap(ruta)
            if not pix.isNull():
                img.setPixmap(pix.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(img, 1)

        # Derecha: campos editables + validación.
        col = QVBoxLayout()
        titulo = QLabel(f"{tx['id']} · estado: {tx['estado']}")
        titulo.setStyleSheet("font-size:15px;font-weight:700;")
        col.addWidget(titulo)
        form = QFormLayout()
        d = tx.get("datos", {})
        self.entradas = {}
        for clave, etiqueta in self.CAMPOS:
            le = QLineEdit(str(d.get(clave) or ""))
            self.entradas[clave] = le
            form.addRow(etiqueta + ":", le)
        col.addLayout(form)

        self.lbl_estado_val = QLabel()
        self.lbl_estado_val.setWordWrap(True)
        col.addWidget(self.lbl_estado_val)
        col.addStretch(1)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        col.addWidget(botones)
        layout.addLayout(col, 1)
        self._revalidar()
        for le in self.entradas.values():
            le.textChanged.connect(self._revalidar)

    def datos_editados(self) -> dict:
        base = {c: e.text().strip() or None for c, e in self.entradas.items()}
        base["origen"] = "manual"
        return base

    def _revalidar(self):
        d = self.datos_editados()
        errores = validar(DatosFiscales(**{k: d.get(k) for k in
                          ("nit", "numero_factura", "autorizacion", "fecha",
                           "importe", "operadora", "origen")}))
        if errores:
            self.lbl_estado_val.setText("⚠ " + "  ·  ".join(errores))
            self.lbl_estado_val.setStyleSheet("color:#f0a020;")
        else:
            self.lbl_estado_val.setText("✔ Datos válidos.")
            self.lbl_estado_val.setStyleSheet("color:#3fb950;")


class VentanaPrincipal(QMainWindow):
    def __init__(self, config: dict, selectores: dict, credenciales_prefill: dict | None = None):
        super().__init__()
        self.config = config
        self.selectores = selectores
        self.credenciales_prefill = credenciales_prefill or {}
        self.setWindowTitle("Lector SIAT — Tarjetas Prepago")
        self.resize(1100, 680)

        self.libro = LibroMayor(config["ruta_libro_mayor"])
        self.led = LedVirtual(al_cambiar=self._pintar_led)
        self.pipeline = PipelineExtraccion(ocr_motor=None)  # OCR se carga bajo demanda
        self._ocr_cargado = False
        self.camara = Camara(config.get("camara_indice", 0))
        self._hilo_rpa = None

        self._construir_ui()
        self._iniciar_camara()
        self._refrescar_tabla()

    # ── Construcción de la interfaz ───────────────────────────────────────
    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Columna izquierda: cámara + LED + captura
        izq = QVBoxLayout()
        titulo_app = QLabel("Lector SIAT")
        titulo_app.setStyleSheet("font-size:20px;font-weight:700;color:#e8e8e8;padding-bottom:2px;")
        subtitulo = QLabel("Tarjetas prepago → Registro de Compras")
        subtitulo.setStyleSheet("font-size:12px;color:#8a8a8a;padding-bottom:10px;")
        izq.addWidget(titulo_app)
        izq.addWidget(subtitulo)

        # Selector de cámara (webcam interna, DroidCam, USB, etc.)
        fila_cam = QHBoxLayout()
        fila_cam.addWidget(QLabel("Cámara:"))
        self.selector_camara = QComboBox()
        self.selector_camara.currentIndexChanged.connect(self._cambiar_camara)
        fila_cam.addWidget(self.selector_camara, 1)
        self.btn_refrescar_cam = QPushButton("⟳")
        self.btn_refrescar_cam.setFixedWidth(40)
        self.btn_refrescar_cam.setToolTip("Volver a buscar cámaras")
        self.btn_refrescar_cam.clicked.connect(self._poblar_camaras)
        fila_cam.addWidget(self.btn_refrescar_cam)
        izq.addLayout(fila_cam)

        self.vista_camara = QLabel("Iniciando cámara…")
        self.vista_camara.setFixedSize(480, 360)
        self.vista_camara.setStyleSheet(
            "background:#141414;color:#777;border:1px solid #3c3c3c;border-radius:10px;")
        self.vista_camara.setAlignment(Qt.AlignmentFlag.AlignCenter)
        izq.addWidget(self.vista_camara)

        fila_led = QHBoxLayout()
        self.led_widget = QLabel()
        self.led_widget.setFixedSize(28, 28)
        self._pintar_led("apagado")
        fila_led.addWidget(self.led_widget)
        self.etiqueta_lectura = QLabel("Listo para capturar.")
        fila_led.addWidget(self.etiqueta_lectura, 1)
        izq.addLayout(fila_led)

        self.btn_capturar = QPushButton("📸  Capturar  (Espacio)")
        self.btn_capturar.setObjectName("btnPrimario")
        self.btn_capturar.setMinimumHeight(42)
        self.btn_capturar.clicked.connect(self.capturar)
        izq.addWidget(self.btn_capturar)
        izq.addStretch(1)
        layout.addLayout(izq)

        # Columna derecha: contadores + tabla + acciones
        der = QVBoxLayout()
        self.contadores_layout = QGridLayout()
        self.contadores_layout.setSpacing(10)
        self._labels_contador = {}
        for i, estado in enumerate(ESTADOS):
            tarjeta = QWidget()
            tarjeta.setStyleSheet(
                "background:#252526;border:1px solid #3c3c3c;border-radius:8px;")
            v = QVBoxLayout(tarjeta)
            v.setContentsMargins(8, 10, 8, 10)
            v.setSpacing(2)
            caja = QLabel("0")
            caja.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caja.setStyleSheet(
                f"background:transparent;border:none;color:{_COLORES_ESTADO[estado]};"
                "font-size:26px;font-weight:700;")
            titulo = QLabel(estado.replace("_", " ").upper())
            titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            titulo.setStyleSheet(
                "background:transparent;border:none;font-size:10px;"
                "color:#8a8a8a;font-weight:600;letter-spacing:0.5px;")
            v.addWidget(caja)
            v.addWidget(titulo)
            self.contadores_layout.addWidget(tarjeta, 0, i)
            self._labels_contador[estado] = caja
        der.addLayout(self.contadores_layout)

        self.tabla = QTableWidget(0, 8)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setHorizontalHeaderLabels(
            ["Tarjeta", "ID", "Estado", "NIT", "N° Factura", "Autorización",
             "Fecha", "Importe"])
        self.tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.verticalHeader().setDefaultSectionSize(56)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self._abrir_detalle_fila)
        pista = QLabel("Doble clic en una fila para ver la foto en grande y editar los campos.")
        pista.setStyleSheet("color:#8a8a8a;font-size:11px;")
        der.addWidget(pista)
        der.addWidget(self.tabla, 1)

        acciones = QHBoxLayout()
        self.btn_ver = QPushButton("🔍 Ver / Editar")
        self.btn_ver.clicked.connect(self._abrir_detalle_seleccion)
        self.btn_procesar = QPushButton("▶ Procesar en SIAT")
        self.btn_procesar.setObjectName("btnPrimario")
        self.btn_procesar.clicked.connect(self.procesar_siat)
        self.btn_excel = QPushButton("⬇ Exportar Excel RCV")
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.btn_saltar = QPushButton("⏭ Saltado")
        self.btn_saltar.clicked.connect(lambda: self._cambiar_estado_seleccion("saltado"))
        self.btn_reintentar = QPushButton("↺ Reintentar")
        self.btn_reintentar.clicked.connect(lambda: self._cambiar_estado_seleccion("pendiente"))
        self.btn_borrar = QPushButton("🗑 Borrar")
        self.btn_borrar.clicked.connect(self._borrar_seleccion)
        self.btn_vaciar = QPushButton("Vaciar todo")
        self.btn_vaciar.clicked.connect(self._vaciar_libro)
        for b in (self.btn_ver, self.btn_procesar, self.btn_excel, self.btn_saltar,
                  self.btn_reintentar, self.btn_borrar, self.btn_vaciar):
            acciones.addWidget(b)
        der.addLayout(acciones)
        layout.addLayout(der, 1)

    # ── Cámara ────────────────────────────────────────────────────────────
    def _iniciar_camara(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._actualizar_frame)
        self._poblar_camaras()

    def _poblar_camaras(self):
        """Busca cámaras disponibles y las carga en el selector."""
        self.selector_camara.blockSignals(True)
        self.selector_camara.clear()
        indices = Camara.listar_camaras()
        if not indices:
            self.selector_camara.addItem("Sin cámara", -1)
            self.vista_camara.setText(
                "Cámara no disponible\n(use captura manual de archivo)")
        else:
            for idx in indices:
                etiqueta = "Cámara 0 (interna)" if idx == 0 else f"Cámara {idx} (DroidCam/USB)"
                self.selector_camara.addItem(etiqueta, idx)
        self.selector_camara.blockSignals(False)
        if indices:
            self._cambiar_camara()

    def _cambiar_camara(self):
        indice = self.selector_camara.currentData()
        if indice is None or indice < 0:
            return
        self._timer.stop()
        if self.camara.cambiar_a(indice):
            self.etiqueta_lectura.setText(f"Cámara {indice} activa. Listo para capturar.")
            self._timer.start(33)  # ~30 fps
        else:
            self.vista_camara.setText(f"No se pudo abrir la cámara {indice}.")

    def _actualizar_frame(self):
        frame = self.camara.leer_frame()
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self.vista_camara.setPixmap(QPixmap.fromImage(img).scaled(
            self.vista_camara.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.capturar()

    # ── Captura + extracción ──────────────────────────────────────────────
    def _asegurar_ocr(self):
        if not self._ocr_cargado:
            try:
                from src.extraccion.ocr_motor import OcrMotor
                self.pipeline = PipelineExtraccion(
                    ocr_motor=OcrMotor(self.config["ruta_modelos_ocr"]))
            except Exception:
                self.pipeline = PipelineExtraccion(ocr_motor=None)
            self._ocr_cargado = True

    def capturar(self):
        frame = self.camara.leer_frame()
        if frame is None:
            ruta, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar imagen de tarjeta", "", "Imágenes (*.png *.jpg *.jpeg)")
            if not ruta:
                return
            frame = cv2.imread(ruta)
        else:
            ruta = self.camara.nombre_captura(self.config["ruta_capturas"])
            os.makedirs(self.config["ruta_capturas"], exist_ok=True)
            cv2.imwrite(ruta, frame)

        self._asegurar_ocr()
        resultado = self.pipeline.procesar_imagen(frame)
        # Se agrega SIEMPRE (con su foto), válida o no, para poder corregir a mano.
        tx = self.libro.agregar(resultado.datos, imagen=ruta)
        if resultado.es_valido:
            self.led.verde()
            self.etiqueta_lectura.setText(
                f"✔ {tx} [{resultado.metodo}] NIT {resultado.datos.nit} · "
                f"Bs {resultado.datos.importe}")
        else:
            self.led.rojo()
            self.etiqueta_lectura.setText(
                f"⚠ {tx} necesita revisión: {'; '.join(resultado.errores)}. "
                "Doble clic en la fila para corregir.")
        self._refrescar_tabla()

    # ── LED + tabla + contadores ──────────────────────────────────────────
    def _pintar_led(self, color: str):
        mapa = {"verde": "#22c55e", "rojo": "#ef4444", "apagado": "#333"}
        self.led_widget.setStyleSheet(
            f"background:{mapa.get(color, '#333')};border-radius:14px;")

    def _refrescar_tabla(self):
        transacciones = self.libro.todas()
        self.tabla.setRowCount(len(transacciones))
        for fila, tx in enumerate(transacciones):
            d = tx["datos"]

            # Columna 0: miniatura de la foto capturada.
            mini = QLabel()
            mini.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ruta = tx.get("imagen")
            if ruta and os.path.exists(ruta):
                pix = QPixmap(ruta)
                if not pix.isNull():
                    mini.setPixmap(pix.scaled(72, 50, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
            else:
                mini.setText("—")
            self.tabla.setCellWidget(fila, 0, mini)

            invalido = bool(validar(DatosFiscales(**{k: d.get(k) for k in
                            ("nit", "numero_factura", "autorizacion", "fecha",
                             "importe", "operadora", "origen")})))
            estado_txt = tx["estado"] + ("  ⚠" if invalido else "")
            valores = [tx["id"], estado_txt, d.get("nit", ""),
                       d.get("numero_factura", ""), d.get("autorizacion", ""),
                       d.get("fecha", ""), d.get("importe", "")]
            for offset, val in enumerate(valores):
                item = QTableWidgetItem(str(val or ""))
                if invalido:
                    item.setForeground(Qt.GlobalColor.red)
                self.tabla.setItem(fila, offset + 1, item)
        c = self.libro.contadores()
        for estado, label in self._labels_contador.items():
            label.setText(str(c[estado]))

    def _tx_de_fila(self, fila: int) -> dict | None:
        if fila < 0:
            return None
        item = self.tabla.item(fila, 1)  # columna ID
        if item is None:
            return None
        tx_id = item.text()
        return next((t for t in self.libro.todas() if t["id"] == tx_id), None)

    def _abrir_detalle_fila(self, fila: int, _col: int = 0):
        tx = self._tx_de_fila(fila)
        if tx is None:
            return
        dlg = DialogoDetalle(self, tx)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.libro.actualizar_datos(tx["id"], dlg.datos_editados())
            self._refrescar_tabla()

    def _abrir_detalle_seleccion(self):
        self._abrir_detalle_fila(self.tabla.currentRow())

    def _borrar_seleccion(self):
        tx = self._tx_de_fila(self.tabla.currentRow())
        if tx is None:
            return
        r = QMessageBox.question(
            self, "Borrar", f"¿Borrar la transacción {tx['id']}?")
        if r == QMessageBox.StandardButton.Yes:
            self.libro.eliminar(tx["id"])
            self._refrescar_tabla()

    def _vaciar_libro(self):
        r = QMessageBox.question(
            self, "Vaciar todo",
            "¿Borrar TODAS las transacciones del Libro Mayor? Esto no se puede deshacer.")
        if r == QMessageBox.StandardButton.Yes:
            self.libro.vaciar()
            self._refrescar_tabla()

    def _cambiar_estado_seleccion(self, estado: str):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        tx_id = self.tabla.item(fila, 0).text()
        self.libro.marcar(tx_id, estado, "Cambio manual desde la GUI.")
        self._refrescar_tabla()

    # ── RPA ───────────────────────────────────────────────────────────────
    def procesar_siat(self):
        if not self.libro.pendientes():
            QMessageBox.information(self, "SIAT", "No hay transacciones pendientes.")
            return
        dlg = DialogoCredenciales(self, self.credenciales_prefill)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cred = dlg.credenciales()
        perfil = self.config.get("perfil_siat", "mock")
        self.btn_procesar.setEnabled(False)
        self._hilo_rpa = HiloRPA(
            perfil, self.selectores, self.libro, cred,
            tamano_lote=self.config.get("tamano_lote", 5),
            timeout=self.config.get("timeout_confirmacion_seg", 60),
            headless=False)
        self._hilo_rpa.cambio_estado.connect(lambda *_: self._refrescar_tabla())
        self._hilo_rpa.terminado.connect(self._rpa_termino)
        self._hilo_rpa.error.connect(self._rpa_error)
        self._hilo_rpa.start()

    def _rpa_termino(self, resumen: dict):
        self.btn_procesar.setEnabled(True)
        self._refrescar_tabla()
        QMessageBox.information(
            self, "SIAT",
            f"Proceso terminado.\nExitosas: {resumen['exitoso']} · "
            f"Fallidas: {resumen['fallido']} · Pendientes: {resumen['pendiente']}")

    def _rpa_error(self, mensaje: str):
        self.btn_procesar.setEnabled(True)
        QMessageBox.critical(self, "Error del RPA", mensaje)

    # ── Excel ─────────────────────────────────────────────────────────────
    def exportar_excel(self):
        pendientes = self.libro.pendientes()
        if not pendientes:
            QMessageBox.information(self, "Excel RCV", "No hay pendientes para exportar.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel RCV", "compras_rcv.xlsx", "Excel (*.xlsx)")
        if not ruta:
            return
        filas = generar_excel_compras(pendientes, ruta)
        QMessageBox.information(self, "Excel RCV", f"Se exportaron {filas} compras a:\n{ruta}")

    def closeEvent(self, event):
        self.camara.cerrar()
        super().closeEvent(event)


def lanzar(config: dict, selectores: dict, credenciales_prefill: dict | None = None):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_ESTILO)
    ventana = VentanaPrincipal(config, selectores, credenciales_prefill)
    ventana.show()
    app.exec()
