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
