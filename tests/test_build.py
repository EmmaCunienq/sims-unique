"""Fichiers produits par build.py et compatibilité Python 3.7 (version du jeu)."""
import ast
import importlib.util
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import fakegame

ROOT = fakegame.ROOT
SRC = fakegame.SRC


def load_build():
    spec = importlib.util.spec_from_file_location('sims_unique_build', os.path.join(ROOT, 'build.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_dbpf(path):
    with open(path, 'rb') as f:
        data = f.read()
    assert data[:4] == b'DBPF', 'signature'
    assert struct.unpack_from('<II', data, 4) == (2, 1), 'version'
    count, = struct.unpack_from('<I', data, 36)
    size, = struct.unpack_from('<I', data, 44)
    minor, = struct.unpack_from('<I', data, 60)
    position, = struct.unpack_from('<Q', data, 64)
    assert minor == 3
    assert position + size == len(data), 'index en fin de fichier'
    assert size == 4 + 32 * count
    entries = []
    p = position + 4
    for _ in range(count):
        res_type, group, hi, lo, offset, file_size, mem_size, compression, committed = \
            struct.unpack_from('<IIIIIIIHH', data, p)
        p += 32
        assert file_size & 0x80000000
        file_size &= 0x7FFFFFFF
        assert file_size == mem_size and compression == 0 and committed == 1
        entries.append(((res_type, group, (hi << 32) | lo), data[offset:offset + file_size]))
    return entries


class Python37Test(unittest.TestCase):
    """Le jeu utilise Python 3.7 : aucune syntaxe plus récente ne doit être utilisée."""

    def test_sources_parse_as_python37(self):
        files = []
        for folder, _, names in os.walk(SRC):
            files += [os.path.join(folder, n) for n in names if n.endswith('.py')]
        self.assertGreater(len(files), 5)
        for path in files:
            with open(path, encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, path, feature_version=(3, 7))
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.NamedExpr, path)  # :=
                if isinstance(node, ast.arguments):
                    self.assertEqual(node.posonlyargs, [], path)  # def f(a, /)
                self.assertNotIsInstance(node, ast.Match, path)  # match/case


class IdsTest(unittest.TestCase):
    def setUp(self):
        fakegame.install()
        from sims_unique import ids, interactions
        self.ids = ids
        self.interactions = interactions

    def test_fnv64_known_value(self):
        # Vecteur de test FNV-1 64 bits officiel pour "a".
        self.assertEqual(self.ids.fnv64('a'), 0xAF63BD4C8601B7BE)
        self.assertEqual(self.ids.fnv64('A'), self.ids.fnv64('a'))

    def test_ids_unique_with_high_bit(self):
        self.assertEqual(len(set(self.ids.INTERACTION_IDS)), len(self.ids.INTERACTIONS))
        for instance in self.ids.INTERACTION_IDS:
            self.assertTrue(instance & 0x8000000000000000)

    def test_every_tuning_class_exists(self):
        for cls_name in self.ids.INTERACTIONS.values():
            cls = getattr(self.interactions, cls_name)
            self.assertTrue(issubclass(cls, self.interactions._SimsUniqueInteraction))


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load_build()
        cls.tmp = tempfile.mkdtemp(prefix='sims_unique_build_')
        cls.build.OUT_DIR = cls.tmp
        cls.build.OUT_FILE = os.path.join(cls.tmp, 'SimsUnique.ts4script')
        cls.build.PACKAGE_FILE = os.path.join(cls.tmp, 'SimsUnique.package')
        cls.build.UI_PACKAGE_FILE = os.path.join(cls.tmp, 'SimsUnique_UI.package')
        cls.compiled = cls.build.compile_with_py37(tempfile.mkdtemp()) is not None
        cls.build.build(allow_source=not cls.compiled)
        cls.build.build_package()
        fakegame.install()
        from sims_unique import ids
        cls.ids = ids

    def test_ts4script_contents(self):
        with zipfile.ZipFile(self.build.OUT_FILE) as zf:
            names = set(zf.namelist())
        ext = '.pyc' if any(n.endswith('.pyc') for n in names) else '.py'
        expected = {'sims_unique_main', 'sims_unique/__init__', 'sims_unique/core', 'sims_unique/hooks',
                    'sims_unique/commands', 'sims_unique/interactions', 'sims_unique/ids',
                    'sims_unique/lineage', 'sims_unique/storage', 'sims_unique/notify',
                    'sims_unique/log', 'sims_unique/paths', 'sims_unique/injector'}
        self.assertEqual(names, {n + ext for n in expected})

    def test_ts4script_is_compiled_for_python37(self):
        """Le jeu ignore les .py : sans Python 3.7, ce test échoue volontairement."""
        self.assertTrue(self.compiled, 'Python 3.7 introuvable (voir build.py) : archive inutilisable en jeu')
        with zipfile.ZipFile(self.build.OUT_FILE) as zf:
            for name in zf.namelist():
                self.assertTrue(name.endswith('.pyc'), name)
                self.assertEqual(zf.read(name)[:4], self.build.PY37_MAGIC, name)

    def test_build_refuses_source_only_archive(self):
        original = self.build.compile_with_py37
        self.build.compile_with_py37 = lambda staging: None
        try:
            with self.assertRaises(self.build.BuildError):
                self.build.build()
        finally:
            self.build.compile_with_py37 = original
            self.build.build(allow_source=not self.compiled)

    def test_ts4script_is_uncompressed(self):
        with zipfile.ZipFile(self.build.OUT_FILE) as zf:
            for info in zf.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)

    def test_package_contains_valid_interaction_tunings(self):
        entries = [e for e in read_dbpf(self.build.PACKAGE_FILE) if e[0][0] == 0xE882D22F]
        self.assertEqual(len(entries), len(self.ids.INTERACTIONS))
        by_instance = dict(zip(self.ids.INTERACTION_IDS, self.ids.INTERACTIONS.items()))
        for (res_type, group, instance), data in entries:
            self.assertEqual(group, 0)
            name, cls_name = by_instance[instance]
            root = ET.fromstring(data)
            self.assertEqual(root.tag, 'I')
            self.assertEqual(root.get('i'), 'interaction')
            self.assertEqual(root.get('m'), 'sims_unique.interactions')
            self.assertEqual(root.get('c'), cls_name)
            self.assertEqual(root.get('n'), name)
            self.assertEqual(int(root.get('s')), instance)
            values = {el.get('n'): el.text for el in root if el.tag == 'T'}
            self.assertEqual(values['allow_autonomous'], 'False')
            # Seuls les réglages sont rangés dans le menu « Sims unique ».
            if name in self.ids.CATEGORY_INTERACTIONS:
                self.assertEqual(int(values['category']), self.ids.CATEGORY_ID)
            else:
                self.assertNotIn('category', values)

    def test_package_contains_menu_resources(self):
        keys = [k for k, _ in read_dbpf(self.build.PACKAGE_FILE)]
        self.assertIn((0x03E9D964, 0, self.ids.CATEGORY_ID), keys)    # catégorie (tuning)
        self.assertIn((0x545AC67A, 0x00E9D967, self.ids.CATEGORY_ID), keys)  # catégorie (SimData)
        self.assertIn((0x00B2D882, 0, self.ids.LOGO_ID), keys)        # logo
        self.assertTrue(any(k[0] == 0x220557DA and k[2] >> 56 == 0x07 for k in keys))  # textes FR

    def test_release_zip(self):
        open(self.build.UI_PACKAGE_FILE, 'wb').close()  # interface factice (pas besoin du jeu ici)
        original = self.build.release_path
        self.build.release_path = lambda: os.path.join(self.tmp, 'release.zip')
        try:
            path = self.build.release()
        finally:
            self.build.release_path = original
        with zipfile.ZipFile(path) as zf:
            names = sorted(zf.namelist())
            readme = zf.read('LISEZMOI.txt').decode('utf-8-sig')
        self.assertEqual(names, ['LISEZMOI.txt', 'SimsUnique/SimsUnique.package', 'SimsUnique/SimsUnique.ts4script',
                                 'SimsUnique/SimsUnique_UI.package'])
        self.assertIn('SIMS UNIQUE ' + self.ids.VERSION, readme)
        self.assertNotIn('{', readme)  # tous les champs remplis
        self.assertIn('\r\n', readme)  # fins de ligne Windows (Bloc-notes)

    def test_release_requires_ui(self):
        if os.path.exists(self.build.UI_PACKAGE_FILE):
            os.remove(self.build.UI_PACKAGE_FILE)
        with self.assertRaises(self.build.BuildError):
            self.build.release()

    def test_mods_folder_with_non_breaking_spaces(self):
        home = tempfile.mkdtemp(prefix='sims_unique_home_')
        mods = os.path.join(home, 'Documents', 'Electronic Arts', 'Les Sims 4', 'Mods')
        os.makedirs(mods)
        os.makedirs(os.path.join(home, 'Documents', 'Electronic Arts', 'Autre jeu', 'Mods'))
        original = os.path.expanduser
        self.build.os.path.expanduser = lambda p: home if p == '~' else original(p)
        try:
            self.assertEqual(self.build.find_mods_folder(), mods)
        finally:
            self.build.os.path.expanduser = original


if __name__ == '__main__':
    unittest.main()
