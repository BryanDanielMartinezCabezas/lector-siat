"""Modelo de los campos fiscales extraídos del reverso de una tarjeta prepago."""
from dataclasses import dataclass


@dataclass
class DatosFiscales:
    nit: str | None = None
    numero_factura: str | None = None
    autorizacion: str | None = None
    fecha: str | None = None       # formato dd/mm/aaaa
    importe: str | None = None     # decimal con punto, ej. "10.00"
    operadora: str | None = None   # ENTEL | TIGO | VIVA
    origen: str = "ocr"            # qr | ocr | manual

    def campos_faltantes(self) -> list[str]:
        """Devuelve los campos obligatorios que aún no tienen valor."""
        obligatorios = {
            "nit": self.nit,
            "numero_factura": self.numero_factura,
            "fecha": self.fecha,
            "importe": self.importe,
        }
        return [nombre for nombre, valor in obligatorios.items() if not valor]

    def esta_completo(self) -> bool:
        return not self.campos_faltantes()

    def a_dict(self) -> dict:
        return {
            "nit": self.nit,
            "numero_factura": self.numero_factura,
            "autorizacion": self.autorizacion,
            "fecha": self.fecha,
            "importe": self.importe,
            "operadora": self.operadora,
            "origen": self.origen,
        }
