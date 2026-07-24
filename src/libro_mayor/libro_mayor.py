"""Libro Mayor: base de datos local en JSON con máquina de estados.

Componente crítico de resiliencia (según el informe): nunca pierde el progreso
ante fallos del SIAT y siempre sabe qué transacciones ya se enviaron. Cada
mutación se persiste de forma atómica (archivo temporal + os.replace) para que
ni un corte de energía corrompa el archivo.
"""
import json
import os
import tempfile
import threading
from datetime import datetime

ESTADOS = ("pendiente", "en_proceso", "completado", "saltado")


class LibroMayor:
    def __init__(self, ruta: str):
        self.ruta = ruta
        self._transacciones: list[dict] = []
        # Lock reentrante: varios métodos se llaman entre sí (marcar_varias →
        # marcar → _guardar) y el lote corre en un hilo aparte de la GUI.
        self._lock = threading.RLock()
        self._cargar()

    # ── Persistencia ──────────────────────────────────────────────────────
    def _cargar(self) -> None:
        with self._lock:
            if os.path.exists(self.ruta):
                with open(self.ruta, encoding="utf-8") as f:
                    data = json.load(f)
                self._transacciones = data.get("transacciones", [])
            else:
                self._transacciones = []

    def _guardar(self) -> None:
        with self._lock:
            directorio = os.path.dirname(self.ruta) or "."
            os.makedirs(directorio, exist_ok=True)
            # tmp con nombre único (no fijo) para que dos escrituras concurrentes
            # no pisen el mismo archivo temporal y corrompan el JSON.
            fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"transacciones": self._transacciones}, f,
                              ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.ruta)  # atómico en el mismo volumen
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise

    # ── Operaciones ───────────────────────────────────────────────────────
    def agregar(self, datos, imagen: str | None = None) -> str:
        with self._lock:
            tx_id = f"TX-{len(self._transacciones) + 1:06d}"
            ahora = datetime.now().isoformat(timespec="seconds")
            self._transacciones.append({
                "id": tx_id,
                "estado": "pendiente",
                "detalle": "",
                "creado": ahora,
                "actualizado": ahora,
                "imagen": imagen,   # ruta de la foto capturada, para verificación manual
                "datos": datos.a_dict() if hasattr(datos, "a_dict") else dict(datos),
            })
            self._guardar()
            return tx_id

    def actualizar_datos(self, tx_id: str, nuevos_datos: dict) -> None:
        """Reemplaza los campos fiscales de una transacción (edición manual)."""
        with self._lock:
            for tx in self._transacciones:
                if tx["id"] == tx_id:
                    tx["datos"] = dict(nuevos_datos)
                    tx["actualizado"] = datetime.now().isoformat(timespec="seconds")
                    self._guardar()
                    return
            raise KeyError(f"No existe la transacción '{tx_id}'.")

    def eliminar(self, tx_id: str) -> None:
        """Borra una transacción (ej. una foto duplicada por accidente)."""
        with self._lock:
            antes = len(self._transacciones)
            self._transacciones = [t for t in self._transacciones if t["id"] != tx_id]
            if len(self._transacciones) == antes:
                raise KeyError(f"No existe la transacción '{tx_id}'.")
            self._guardar()

    def vaciar(self) -> None:
        """Borra todas las transacciones (empezar de cero)."""
        with self._lock:
            self._transacciones = []
            self._guardar()

    def marcar(self, tx_id: str, estado: str, detalle: str = "") -> None:
        if estado not in ESTADOS:
            raise ValueError(
                f"Estado inválido: '{estado}'. Válidos: {', '.join(ESTADOS)}"
            )
        with self._lock:
            for tx in self._transacciones:
                if tx["id"] == tx_id:
                    tx["estado"] = estado
                    tx["detalle"] = detalle
                    tx["actualizado"] = datetime.now().isoformat(timespec="seconds")
                    self._guardar()
                    return
            raise KeyError(f"No existe la transacción '{tx_id}'.")

    def puede_cargar(self, tx_id: str) -> bool:
        """True solo si la transacción está pendiente (completado no se recarga)."""
        with self._lock:
            for tx in self._transacciones:
                if tx["id"] == tx_id:
                    return tx["estado"] == "pendiente"
            return False

    def marcar_varias(self, ids: list[str], estado: str) -> None:
        """Cambia el estado de varias transacciones de una vez (selección múltiple)."""
        with self._lock:
            for tx_id in ids:
                self.marcar(tx_id, estado)

    # ── Consultas ─────────────────────────────────────────────────────────
    def todas(self) -> list[dict]:
        with self._lock:
            return list(self._transacciones)

    def pendientes(self) -> list[dict]:
        with self._lock:
            return [t for t in self._transacciones if t["estado"] == "pendiente"]

    def siguiente_lote(self, n: int) -> list[dict]:
        with self._lock:
            return self.pendientes()[:n]

    def contadores(self) -> dict[str, int]:
        with self._lock:
            conteo = {estado: 0 for estado in ESTADOS}
            for tx in self._transacciones:
                conteo[tx["estado"]] += 1
            return conteo
