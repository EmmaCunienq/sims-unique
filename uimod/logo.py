"""Logo du menu « Sims unique » : plumbob vert à facettes coiffé d'une couronne dorée.

Dessiné par programme (aucune image externe), dans le style des icônes de catégorie
du jeu : 46x46, couleurs vives et brillantes, contour sombre, ombre légère, fond transparent.
Format de sortie identique aux icônes du jeu : DDS 32 bits non compressé (A8R8G8B8).
"""
import struct
import zlib

SIZE = 46
SUPERSAMPLE = 4

# Plumbob : pointe haute, milieu gauche/droit, pointe basse, et arête centrale (effet 3D).
TOP, LEFT, RIGHT, BOTTOM, RIDGE = (23, 13), (11.5, 28), (34.5, 28), (23, 45), (20.5, 30)
PLUMBOB_FACETS = [
    ((TOP, LEFT, RIDGE), (170, 245, 110), (110, 215, 70)),      # haut gauche : le plus clair
    ((TOP, RIDGE, RIGHT), (100, 210, 65), (60, 170, 40)),       # haut droit
    ((LEFT, RIDGE, BOTTOM), (75, 185, 50), (40, 135, 30)),      # bas gauche
    ((RIDGE, RIGHT, BOTTOM), (45, 140, 30), (25, 100, 20)),     # bas droit : le plus sombre
]
PLUMBOB_OUTLINE = (20, 70, 15)
HIGHLIGHT = ((21.5, 16.5), (14.5, 27), (17, 27.5), (22.5, 19))  # reflet sur la facette claire

CROWN = ((15, 12.5), (15, 4.5), (19, 8.5), (23, 1.5), (27, 8.5), (31, 4.5), (31, 12.5))
CROWN_TOP, CROWN_BOTTOM = (255, 228, 110), (225, 150, 25)
CROWN_OUTLINE = (120, 70, 0)
JEWEL_CENTER, JEWEL_RADIUS, JEWEL_COLOR = (23, 10), 1.6, (220, 40, 60)


def _inside(px, py, polygon):
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _grow(polygon, amount):
    """Agrandit un polygone depuis son centre (pour le contour)."""
    cx = sum(p[0] for p in polygon) / len(polygon)
    cy = sum(p[1] for p in polygon) / len(polygon)
    out = []
    for x, y in polygon:
        dx, dy = x - cx, y - cy
        d = (dx * dx + dy * dy) ** 0.5 or 1
        out.append((x + dx / d * amount, y + dy / d * amount))
    return out


def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _blend(dst, color, alpha):
    r, g, b, a = dst
    out_a = alpha + a * (1 - alpha)
    if out_a == 0:
        return (0, 0, 0, 0)
    mix = [(c * alpha + d * a * (1 - alpha)) / out_a for c, d in zip(color, (r, g, b))]
    return (mix[0], mix[1], mix[2], out_a)


def _sample(x, y):
    """Couleur RGBA (0-255, alpha 0-1) d'un point du logo, en coordonnées 46x46."""
    px = (0.0, 0.0, 0.0, 0.0)
    plumbob = (TOP, LEFT, BOTTOM, RIGHT)
    # Ombre portée douce
    if _inside(x - 1.2, y - 1.4, _grow(plumbob, 1.0)) or _inside(x - 1.2, y - 1.4, _grow(CROWN, 1.0)):
        px = _blend(px, (0, 0, 0), 0.35)
    # Contour sombre puis facettes avec dégradé vertical
    if _inside(x, y, _grow(plumbob, 1.3)):
        px = _blend(px, PLUMBOB_OUTLINE, 1.0)
    for polygon, light, dark in PLUMBOB_FACETS:
        if _inside(x, y, polygon):
            t = (y - TOP[1]) / (BOTTOM[1] - TOP[1])
            px = _blend(px, _lerp(light, dark, t), 1.0)
    if _inside(x, y, HIGHLIGHT):
        px = _blend(px, (255, 255, 255), 0.55)
    # Couronne
    if _inside(x, y, _grow(CROWN, 1.2)):
        px = _blend(px, CROWN_OUTLINE, 1.0)
    if _inside(x, y, CROWN):
        t = (y - 1.5) / 11.0
        px = _blend(px, _lerp(CROWN_TOP, CROWN_BOTTOM, t), 1.0)
        if y < 6.5 and _inside(x + 1.0, y + 1.0, CROWN) and not _inside(x - 1.0, y - 1.0, CROWN):
            px = _blend(px, (255, 255, 230), 0.6)  # liseré brillant
    dx, dy = x - JEWEL_CENTER[0], y - JEWEL_CENTER[1]
    if dx * dx + dy * dy <= JEWEL_RADIUS ** 2:
        px = _blend(px, JEWEL_COLOR, 1.0)
        if dx < 0 and dy < 0:
            px = _blend(px, (255, 200, 210), 0.6)
    return px


def render(size=SIZE):
    """Liste de pixels (r, g, b, a) en 0-255, ligne par ligne."""
    pixels = []
    n = SUPERSAMPLE
    scale = SIZE / size
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(n):
                for sx in range(n):
                    r, g, b, a = _sample((x + (sx + 0.5) / n) * scale, (y + (sy + 0.5) / n) * scale)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            alpha = acc[3] / (n * n)
            if acc[3] > 0:
                color = [int(round(c / acc[3])) for c in acc[:3]]
            else:
                color = [0, 0, 0]
            pixels.append((color[0], color[1], color[2], int(round(alpha * 255))))
    return pixels


def to_dds(pixels, size=SIZE):
    """DDS 32 bits non compressé, mêmes en-têtes que les icônes de catégorie du jeu."""
    header = bytearray(128)
    header[0:4] = b'DDS '
    struct.pack_into('<IIIIIII', header, 4, 124, 0x1007 | 0x8, size, size, size * 4, 0, 1)
    struct.pack_into('<II', header, 76, 32, 0x41)                 # pixel format : RGB + alpha
    struct.pack_into('<IIIII', header, 84, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF)
    struct.pack_into('<I', header, 104, 0xFF000000)
    struct.pack_into('<I', header, 108, 0x1000)                   # caps : texture
    body = bytearray()
    for r, g, b, a in pixels:
        body += struct.pack('<I', (a << 24) | (r << 16) | (g << 8) | b)
    return bytes(header + body)


def to_png(pixels, size=SIZE, scale=1, background=None):
    """PNG d'aperçu (agrandi, sur un fond optionnel)."""
    rows = bytearray()
    for y in range(size * scale):
        rows.append(0)
        for x in range(size * scale):
            r, g, b, a = pixels[(y // scale) * size + (x // scale)]
            if background:
                br, bg, bb = background
                r, g, b = [(c * a + k * (255 - a)) // 255 for c, k in ((r, br), (g, bg), (b, bb))]
                a = 255
            rows += bytes((r, g, b, a))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size * scale, size * scale, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(rows), 9)) + chunk(b'IEND', b''))
