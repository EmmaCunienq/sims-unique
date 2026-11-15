"""Ressources du menu « Sims unique » : catégorie de pie menu, sa SimData, ses textes et son logo.

L'interface ne lit pas la catégorie depuis le script Python : le moteur lui fournit la
liste des catégories (« GetInteractionCategoryList ») à partir des SimData exportées.
Il faut donc, pour une catégorie de mod :
  - le tuning XML (type 0x03E9D964) lu par le Python du jeu ;
  - la SimData (type 0x545AC67A, groupe 0x00E9D967) lue par le moteur pour l'interface ;
  - une table de textes (STBL) pour le nom, dans chaque langue ;
  - l'icône (DDS 46x46, type 0x00B2D882), au même format que celles du jeu.
"""
import os
import struct
import sys

from uimod import logo, simdata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'sims_unique'))
import ids  # noqa: E402

# Type du tuning lu par le Python du jeu (sims4.resources.Types.PIE_MENU_CATEGORY).
PIE_MENU_CATEGORY_TYPE = 0x03E9D964
SIMDATA_TYPE = 0x545AC67A
# Groupe des SimData de catégories, relevé sur les 301 catégories du jeu (différent du type ci-dessus).
SIMDATA_GROUP = 0x00E9D967
STBL_TYPE = 0x220557DA
DDS_TYPE = 0x00B2D882

# Langues du jeu (octet de poids fort de l'instance STBL) : 0x00 anglais ... 0x07 français ...
LANGUAGE_PREFIXES = range(0x00, 0x13)

# Schéma PieMenuCategory actuel du jeu (relevé sur 205 catégories, hash 0xE2EAA141).
SCHEMA = {
    'name': 'PieMenuCategory',
    'hash': 0xE2EAA141,
    'size': 64,
    'columns': [  # (nom, type, offset), dans l'ordre du jeu
        ('_parent', simdata.TABLE_SET_REFERENCE, 32),
        ('_special_category', simdata.INT64, 40),
        ('_collapsible', simdata.BOOL, 0),
        ('_display_priority', simdata.INT32, 8),
        ('_icon', simdata.RESOURCE_KEY, 16),
        ('_display_name', simdata.LOCALIZATION_KEY, 4),
        ('mood_overrides', simdata.VECTOR, 52),
        ('always_show_disabled_interactions', simdata.BOOL, 48),
    ],
}
DISPLAY_PRIORITY = 1


def label_hash():
    return simdata.fnv32(ids.CATEGORY_LABEL_KEY)


def category_tuning():
    xml = '''<?xml version="1.0" encoding="utf-8"?>
<I c="PieMenuCategory" i="pie_menu_category" m="interactions.pie_menu_category" n="{name}" s="{instance}">
  <T n="_collapsible">False</T>
  <T n="_display_name">0x{label:08X}<!--{text}--></T>
  <T n="_display_priority">{priority}</T>
  <T n="_icon">{icon_type:08x}:00000000:{icon:016x}</T>
</I>
'''.format(name=ids.CATEGORY_NAME, instance=ids.CATEGORY_ID, label=label_hash(), text=ids.CATEGORY_LABEL,
           priority=DISPLAY_PRIORITY, icon_type=DDS_TYPE, icon=ids.LOGO_ID)
    return xml.encode('utf-8')


def category_simdata():
    columns = [{'name': n, 'hash': simdata.fnv32(n), 'type': t, 'flags': 0, 'offset': o}
               for n, t, o in SCHEMA['columns']]
    sim = {
        'version': 0x101,
        'name': ids.CATEGORY_NAME,
        'name_hash': simdata.fnv32(ids.CATEGORY_NAME),
        'schema': {'name': SCHEMA['name'], 'name_hash': simdata.fnv32(SCHEMA['name']),
                   'hash': SCHEMA['hash'], 'size': SCHEMA['size'], 'columns': columns},
        'row': bytes(SCHEMA['size']),
    }
    simdata.set_value(sim, '_collapsible', False)
    simdata.set_value(sim, '_display_name', label_hash())
    simdata.set_value(sim, '_display_priority', DISPLAY_PRIORITY)
    simdata.set_value(sim, '_icon', (DDS_TYPE, 0, ids.LOGO_ID))
    simdata.set_value(sim, '_parent', 0)
    simdata.set_value(sim, '_special_category', 0)
    # Vecteur vide : offset nul (0x80000000), 0 élément — comme dans les catégories du jeu.
    row = bytearray(sim['row'])
    struct.pack_into('<II', row, 52, simdata.NULL, 0)
    sim['row'] = bytes(row)
    simdata.set_value(sim, 'always_show_disabled_interactions', False)
    return simdata.write(sim)


def string_table(strings):
    """STBL version 5 non compressée. strings : {hash32: texte}"""
    entries = bytearray()
    total = 0
    for key, text in strings.items():
        raw = text.encode('utf-8')
        entries += struct.pack('<IBH', key, 0, len(raw)) + raw
        total += len(raw) + 1
    header = b'STBL' + struct.pack('<HBQHI', 5, 0, len(strings), 0, total)
    return header + bytes(entries)


def stbl_instance(prefix):
    return (prefix << 56) | (ids.fnv64(ids.STRINGS_NAME) & 0x00FFFFFFFFFFFFFF)


def resources():
    """[((type, group, instance), bytes)] à ajouter au package principal."""
    table = string_table({label_hash(): ids.CATEGORY_LABEL})
    out = [
        ((PIE_MENU_CATEGORY_TYPE, 0, ids.CATEGORY_ID), category_tuning()),
        ((SIMDATA_TYPE, SIMDATA_GROUP, ids.CATEGORY_ID), category_simdata()),
        ((DDS_TYPE, 0, ids.LOGO_ID), logo.to_dds(logo.render())),
    ]
    out += [((STBL_TYPE, 0, stbl_instance(p)), table) for p in LANGUAGE_PREFIXES]
    return out
