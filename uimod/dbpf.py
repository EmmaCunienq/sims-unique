"""Lecture et écriture des fichiers .package (format DBPF 2.1) des Sims 4."""
import struct
import zlib

HEADER_SIZE = 96
COMPRESSION_NONE = 0x0000
COMPRESSION_ZLIB = 0x5A42


def read_index(path):
    """Liste des ressources : dicts {type, group, instance, offset, size, compression, path}."""
    with open(path, 'rb') as f:
        header = f.read(HEADER_SIZE)
        if len(header) < HEADER_SIZE or header[:4] != b'DBPF':
            return []
        count, = struct.unpack_from('<I', header, 36)
        size, = struct.unpack_from('<I', header, 44)
        position, = struct.unpack_from('<Q', header, 64)
        if count == 0:
            return []
        f.seek(position)
        index = f.read(size)
    flags, = struct.unpack_from('<I', index, 0)
    p = 4
    constant = {}
    for bit, name in enumerate(('type', 'group', 'hi')):
        if flags & (1 << bit):
            constant[name], = struct.unpack_from('<I', index, p)
            p += 4
    entries = []
    for _ in range(count):
        entry = {}
        for name in ('type', 'group', 'hi'):
            if name in constant:
                entry[name] = constant[name]
            else:
                entry[name], = struct.unpack_from('<I', index, p)
                p += 4
        lo, offset, file_size, _mem_size = struct.unpack_from('<IIII', index, p)
        p += 16
        compression = COMPRESSION_NONE
        if file_size & 0x80000000:
            compression, = struct.unpack_from('<H', index, p)
            p += 4
        entries.append({
            'type': entry['type'], 'group': entry['group'], 'instance': (entry['hi'] << 32) | lo,
            'offset': offset, 'size': file_size & 0x7FFFFFFF, 'compression': compression, 'path': path,
        })
    return entries


def read_resource(entry):
    with open(entry['path'], 'rb') as f:
        f.seek(entry['offset'])
        data = f.read(entry['size'])
    if entry['compression'] == COMPRESSION_ZLIB:
        return zlib.decompress(data)
    if entry['compression'] != COMPRESSION_NONE:
        raise ValueError('Compression {:04X} non gérée'.format(entry['compression']))
    return data


def write_package(path, resources):
    """Écrit un package non compressé. resources : [((type, group, instance), bytes)]"""
    body = bytearray()
    index = bytearray(struct.pack('<I', 0))  # aucun champ constant
    for (res_type, group, instance), data in resources:
        offset = HEADER_SIZE + len(body)
        body += data
        index += struct.pack('<IIIIIIIHH',
                             res_type, group, instance >> 32, instance & 0xFFFFFFFF,
                             offset, len(data) | 0x80000000, len(data), COMPRESSION_NONE, 1)
    header = bytearray(HEADER_SIZE)
    header[0:4] = b'DBPF'
    struct.pack_into('<II', header, 4, 2, 1)                       # version 2.1
    struct.pack_into('<I', header, 36, len(resources))             # nombre d'entrées
    struct.pack_into('<I', header, 44, len(index))                 # taille de l'index
    struct.pack_into('<I', header, 60, 3)                          # version mineure de l'index
    struct.pack_into('<Q', header, 64, HEADER_SIZE + len(body))    # position de l'index
    with open(path, 'wb') as f:
        f.write(header + body + index)
