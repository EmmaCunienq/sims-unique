"""Lecture minimale du bytecode ActionScript 3 (ABC) d'un fichier GFX/SWF.

Sert uniquement à trouver l'index du corps d'une méthode (« method body index »), que JPEXS
demande pour remplacer UNE méthode en P-code sans recompiler toute la classe.
Référence : AVM2 Overview (Adobe), chapitre 4 « The .abc file format ».
"""
import struct
import zlib

DO_ABC, DO_ABC2 = 72, 82


class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        v, = struct.unpack_from('<H', self.d, self.p)
        self.p += 2
        return v

    def u30(self):
        result = shift = 0
        while True:
            b = self.u8()
            result |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80 or shift >= 35:
                return result & 0xFFFFFFFF

    def skip(self, n):
        self.p += n

    def string(self):
        n = self.u30()
        s = self.d[self.p:self.p + n].decode('utf-8', 'replace')
        self.p += n
        return s


def swf_body(data):
    """Corps non compressé d'un SWF/GFX (après l'en-tête de 8 octets)."""
    sig = data[:3]
    if sig in (b'CWS', b'CFX'):
        return zlib.decompress(data[8:])
    if sig in (b'FWS', b'GFX'):
        return data[8:]
    raise ValueError('Signature inconnue : {!r}'.format(sig))


def abc_blocks(data):
    """Liste des blocs ABC (bytes) des tags DoABC/DoABC2, dans l'ordre du fichier."""
    body = swf_body(data)
    nbits = body[0] >> 3
    p = (5 + 4 * nbits + 7) // 8 + 4  # RECT + frame rate + frame count
    blocks = []
    while p + 2 <= len(body):
        code_len, = struct.unpack_from('<H', body, p)
        p += 2
        code, length = code_len >> 6, code_len & 0x3F
        if length == 0x3F:
            length, = struct.unpack_from('<I', body, p)
            p += 4
        if code == DO_ABC2:
            r = Reader(body, p)
            r.skip(4)  # flags
            while body[r.p] != 0:
                r.p += 1
            r.p += 1  # nom
            blocks.append(body[r.p:p + length])
        elif code == DO_ABC:
            blocks.append(body[p:p + length])
        p += length
        if code == 0:
            break
    return blocks


def _skip_traits(r):
    traits = []
    for _ in range(r.u30()):
        name = r.u30()
        kind = r.u8()
        t = kind & 0x0F
        entry = {'name': name, 'kind': t}
        if t in (0, 6):  # slot, const
            r.u30()
            r.u30()
            if r.u30():
                r.u8()
        elif t in (1, 2, 3):  # method, getter, setter
            r.u30()
            entry['method'] = r.u30()
        elif t == 4:  # class
            r.u30()
            r.u30()
        elif t == 5:  # function
            r.u30()
            entry['method'] = r.u30()
        if kind & 0x40:  # ATTR_Metadata
            for _ in range(r.u30()):
                r.u30()
        traits.append(entry)
    return traits


def parse(abc):
    """Renvoie {'classes': {nom_qualifié: {'iinit', 'cinit', 'methods': {nom: (kind, method)}}},
    'bodies': {method_index: body_index}}."""
    r = Reader(abc)
    r.skip(4)  # minor, major
    ints = [0] + [None] * 0
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.u30()
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.u30()
    n = r.u30()
    r.skip(8 * max(0, n - 1))
    strings = [''] + [None] * 0
    n = r.u30()
    strings = [''] + [r.string() for _ in range(max(0, n - 1))]
    n = r.u30()
    namespaces = [(0, 0)] + [(r.u8(), r.u30()) for _ in range(max(0, n - 1))]
    n = r.u30()
    for _ in range(max(0, n - 1)):
        for _ in range(r.u30()):
            r.u30()
    n = r.u30()
    multinames = [None]
    for _ in range(max(0, n - 1)):
        kind = r.u8()
        if kind in (0x07, 0x0D):  # QName
            ns, name = r.u30(), r.u30()
            multinames.append((ns, name))
        elif kind in (0x0F, 0x10):  # RTQName
            multinames.append((None, r.u30()))
        elif kind in (0x11, 0x12):  # RTQNameL
            multinames.append(None)
        elif kind in (0x09, 0x0E):  # Multiname
            name = r.u30()
            r.u30()
            multinames.append((None, name))
        elif kind in (0x1B, 0x1C):  # MultinameL
            r.u30()
            multinames.append(None)
        elif kind == 0x1D:  # TypeName
            r.u30()
            for _ in range(r.u30()):
                r.u30()
            multinames.append(None)
        else:
            raise ValueError('Multiname inconnu 0x{:02X}'.format(kind))

    def qname(index):
        m = multinames[index]
        if not m:
            return None
        ns, name = m
        prefix = strings[namespaces[ns][1]] if ns else ''
        return (prefix + '.' if prefix else '') + strings[name]

    def short(index):
        m = multinames[index]
        return strings[m[1]] if m else None

    method_count = r.u30()
    for _ in range(method_count):
        params = r.u30()
        r.u30()
        for _ in range(params):
            r.u30()
        r.u30()
        flags = r.u8()
        if flags & 0x08:  # HAS_OPTIONAL
            for _ in range(r.u30()):
                r.u30()
                r.u8()
        if flags & 0x80:  # HAS_PARAM_NAMES
            for _ in range(params):
                r.u30()
    for _ in range(r.u30()):  # metadata
        r.u30()
        items = r.u30()
        for _ in range(2 * items):
            r.u30()
    class_count = r.u30()
    instances = []
    for _ in range(class_count):
        name = r.u30()
        r.u30()
        flags = r.u8()
        if flags & 0x08:
            r.u30()
        for _ in range(r.u30()):
            r.u30()
        iinit = r.u30()
        instances.append({'name': qname(name), 'iinit': iinit, 'traits': _skip_traits(r)})
    statics = []
    for _ in range(class_count):
        cinit = r.u30()
        statics.append({'cinit': cinit, 'traits': _skip_traits(r)})
    for _ in range(r.u30()):  # scripts
        r.u30()
        _skip_traits(r)
    bodies = {}
    codes = []
    for body_index in range(r.u30()):
        method = r.u30()
        header = (r.u30(), r.u30(), r.u30(), r.u30())  # max_stack, locals, init/max scope depth
        length = r.u30()
        code = r.d[r.p:r.p + length]
        r.skip(length)
        exceptions = [tuple(r.u30() for _ in range(5)) for _ in range(r.u30())]
        _skip_traits(r)
        bodies[method] = body_index
        codes.append((method, header, bytes(code), exceptions))

    kinds = {1: 'method', 2: 'getter', 3: 'setter'}
    classes = {}
    for inst, static in zip(instances, statics):
        methods = {}
        for t in inst['traits']:
            if t['kind'] in kinds:
                methods[(kinds[t['kind']], short(t['name']))] = t['method']
        for t in static['traits']:
            if t['kind'] in kinds:
                methods[('static ' + kinds[t['kind']], short(t['name']))] = t['method']
        classes[inst['name']] = {'iinit': inst['iinit'], 'cinit': static['cinit'], 'methods': methods}
    return {'classes': classes, 'bodies': bodies, 'codes': codes,
            'pools': {'multinames': len(multinames), 'methods': method_count, 'classes': class_count}}


def body_index(gfx_bytes, class_name, method_name, kind='method'):
    """Index du corps de méthode (dans le bloc ABC qui contient la classe) pour JPEXS."""
    found = []
    for abc in abc_blocks(gfx_bytes):
        info = parse(abc)
        cls = info['classes'].get(class_name)
        if cls is None:
            continue
        method = cls['methods'].get((kind, method_name))
        if method is not None:
            found.append(info['bodies'][method])
    if len(found) != 1:
        raise ValueError('{}.{} ({}) trouvé {} fois'.format(class_name, method_name, kind, len(found)))
    return found[0]
