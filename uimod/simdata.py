"""Lecture / écriture des ressources SimData (format « DATA », version 0x101).

Limité à ce dont le mod a besoin : une table d'objets d'une ligne (une instance de tuning),
avec des colonnes de taille fixe. Les vecteurs vides (offset nul) sont gérés ; les
sous-tables (vecteurs non vides, objets imbriqués, chaînes) ne le sont pas.

Structure :
  en-tête (32 o) | en-têtes de tables (28 o chacun) | lignes (alignées sur 16)
  | schémas (24 o) + colonnes (20 o chacune) | chaînes (noms, terminées par \\0)
Les offsets sont relatifs à la position du champ qui les contient ; 0x80000000 = nul.
"""
import struct

NULL = 0x80000000

# Types de données SimData -> taille en octets dans une ligne
BOOL, CHAR8, INT8, UINT8, INT16, UINT16, INT32, UINT32, INT64, UINT64, FLOAT = range(11)
STRING8, HASHED_STRING8, OBJECT, VECTOR, FLOAT2, FLOAT3, FLOAT4 = range(11, 18)
TABLE_SET_REFERENCE, RESOURCE_KEY, LOCALIZATION_KEY = 18, 19, 20
SIZES = {BOOL: 1, CHAR8: 1, INT8: 1, UINT8: 1, INT16: 2, UINT16: 2, INT32: 4, UINT32: 4, INT64: 8,
         UINT64: 8, FLOAT: 4, STRING8: 4, HASHED_STRING8: 8, OBJECT: 4, VECTOR: 8, FLOAT2: 8,
         FLOAT3: 12, FLOAT4: 16, TABLE_SET_REFERENCE: 8, RESOURCE_KEY: 16, LOCALIZATION_KEY: 4}


def fnv32(text):
    h = 0x811C9DC5
    for byte in text.lower().encode('utf-8'):
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= byte
    return h


def _rel(data, pos):
    value, = struct.unpack_from('<i', data, pos)
    return None if (value & 0xFFFFFFFF) == NULL else pos + value


def _cstr(data, pos):
    end = data.index(b'\0', pos)
    return data[pos:end].decode('utf-8')


def parse(data):
    """Renvoie {'name', 'name_hash', 'schema': {...}, 'row': bytes} pour une SimData à une table."""
    if data[:4] != b'DATA':
        raise ValueError('Pas une SimData')
    version, = struct.unpack_from('<I', data, 4)
    table_pos = _rel(data, 8)
    table_count, = struct.unpack_from('<i', data, 12)
    schema_pos = _rel(data, 16)
    schema_count, = struct.unpack_from('<i', data, 20)
    if table_count != 1 or schema_count != 1:
        raise ValueError('{} tables / {} schémas : non géré'.format(table_count, schema_count))

    name_pos = _rel(data, table_pos)
    name_hash, = struct.unpack_from('<I', data, table_pos + 4)
    t_schema = _rel(data, table_pos + 8)
    data_type, row_size = struct.unpack_from('<II', data, table_pos + 12)
    row_pos = _rel(data, table_pos + 20)
    row_count, = struct.unpack_from('<I', data, table_pos + 24)
    if data_type != OBJECT or row_count != 1 or t_schema != schema_pos:
        raise ValueError('Table non gérée')

    s_name = _rel(data, schema_pos)
    s_name_hash, schema_hash, schema_size = struct.unpack_from('<III', data, schema_pos + 4)
    col_pos = _rel(data, schema_pos + 16)
    col_count, = struct.unpack_from('<I', data, schema_pos + 20)
    columns = []
    for i in range(col_count):
        p = col_pos + 20 * i
        c_name = _rel(data, p)
        c_hash, = struct.unpack_from('<I', data, p + 4)
        c_type, c_flags, c_offset = struct.unpack_from('<HHI', data, p + 8)
        c_schema = _rel(data, p + 16)
        if c_schema is not None:
            raise ValueError('Colonne à sous-schéma non gérée')
        columns.append({'name': _cstr(data, c_name), 'hash': c_hash, 'type': c_type,
                        'flags': c_flags, 'offset': c_offset})
    return {
        'version': version,
        'name': _cstr(data, name_pos) if name_pos is not None else None,
        'name_hash': name_hash,
        'schema': {'name': _cstr(data, s_name), 'name_hash': s_name_hash, 'hash': schema_hash,
                   'size': schema_size, 'columns': columns},
        'row': bytes(data[row_pos:row_pos + row_size]),
    }


def _align(buf, n):
    while len(buf) % n:
        buf.append(0)


def write(sim):
    """Inverse de parse() : produit les mêmes octets que le jeu pour ce type de SimData."""
    schema = sim['schema']
    columns = schema['columns']
    out = bytearray(32)
    out[0:4] = b'DATA'
    struct.pack_into('<I', out, 4, sim.get('version', 0x101))
    table_pos = len(out)
    out += bytearray(28)
    _align(out, 16)
    row_pos = len(out)
    out += sim['row']
    _align(out, 16)
    schema_pos = len(out)
    out += bytearray(24)
    col_pos = len(out)
    out += bytearray(20 * len(columns))
    # Chaînes : noms de colonnes (ordre alphabétique, comme le jeu), puis schéma, puis table.
    strings = {}
    for name in sorted(c['name'] for c in columns) + [schema['name'], sim['name']]:
        if name is not None and name not in strings:
            strings[name] = len(out)
            out += name.encode('utf-8') + b'\0'

    def put_rel(pos, target):
        struct.pack_into('<i', out, pos, NULL - 0x100000000 if target is None else target - pos)

    put_rel(8, table_pos)
    struct.pack_into('<i', out, 12, 1)
    put_rel(16, schema_pos)
    struct.pack_into('<i', out, 20, 1)

    put_rel(table_pos, strings.get(sim['name']))
    struct.pack_into('<I', out, table_pos + 4, sim['name_hash'])
    put_rel(table_pos + 8, schema_pos)
    struct.pack_into('<II', out, table_pos + 12, OBJECT, len(sim['row']))
    put_rel(table_pos + 20, row_pos)
    struct.pack_into('<I', out, table_pos + 24, 1)

    put_rel(schema_pos, strings[schema['name']])
    struct.pack_into('<III', out, schema_pos + 4, schema['name_hash'], schema['hash'], schema['size'])
    put_rel(schema_pos + 16, col_pos)
    struct.pack_into('<I', out, schema_pos + 20, len(columns))
    for i, c in enumerate(columns):
        p = col_pos + 20 * i
        put_rel(p, strings[c['name']])
        struct.pack_into('<IHHI', out, p + 4, c['hash'], c['type'], c['flags'], c['offset'])
        put_rel(p + 16, None)
    return bytes(out)


def column(sim, name):
    for c in sim['schema']['columns']:
        if c['name'] == name:
            return c
    raise KeyError(name)


def get_value(sim, name):
    c = column(sim, name)
    raw = sim['row'][c['offset']:c['offset'] + SIZES[c['type']]]
    if c['type'] == RESOURCE_KEY:
        instance, res_type, group = struct.unpack('<QII', raw)
        return res_type, group, instance
    if c['type'] == VECTOR:
        return struct.unpack('<iI', raw)
    fmt = {BOOL: '<?', INT32: '<i', UINT32: '<I', LOCALIZATION_KEY: '<I', TABLE_SET_REFERENCE: '<Q',
           UINT64: '<Q', INT64: '<q', FLOAT: '<f'}[c['type']]
    return struct.unpack(fmt, raw)[0]


def set_value(sim, name, value):
    c = column(sim, name)
    if c['type'] == RESOURCE_KEY:
        res_type, group, instance = value
        raw = struct.pack('<QII', instance, res_type, group)
    else:
        fmt = {BOOL: '<?', INT32: '<i', UINT32: '<I', LOCALIZATION_KEY: '<I', TABLE_SET_REFERENCE: '<Q',
               UINT64: '<Q', INT64: '<q', FLOAT: '<f'}[c['type']]
        raw = struct.pack(fmt, value)
    row = bytearray(sim['row'])
    row[c['offset']:c['offset'] + len(raw)] = raw
    sim['row'] = bytes(row)
