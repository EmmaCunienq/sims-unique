"""Construction du package d'interface (uimod)."""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

import fakegame

sys.path.insert(0, fakegame.ROOT)
from uimod import abc, build_ui, dbpf, patches  # noqa: E402

SOURCE = """trait method QName(ProtectedNamespace("x:Y"),"Reflow")
dispid 0
method
name null
body
code
getlocal0
pushscope
getproperty QName(PackageNamespace(""),"SmallSize")
getlocal 6
ifeq ofs0081
getlocal 11
ofs0081:
returnvoid
end ; code
end ; body
end ; method
trait method QName(PackageNamespace(""),"Other")
method
end ; method
"""
INSERT = {'class': 'X', 'anchor': ['getlocal0', 'pushscope'], 'code': ['nop', 'nop']}
REPLACE = {'class': 'X', 'find': ['ifeq ofs0081', 'getlocal 11'], 'replace': ['pop', 'pop\njump ofs0081']}


class ApplyPatchTest(unittest.TestCase):
    def method(self):
        return patches.extract_method(SOURCE, 'method', 'Reflow')

    def test_extract_method_any_namespace(self):
        body = self.method().splitlines()
        self.assertEqual((body[0], body[-1]), ('method', 'end ; method'))
        self.assertIn('ifeq ofs0081', body)
        with self.assertRaises(ValueError):
            patches.extract_method(SOURCE, 'method', 'Absent')

    def test_insert_after_anchor_block(self):
        lines = patches.apply_patch(self.method(), INSERT).splitlines()
        i = lines.index('pushscope')
        self.assertEqual(lines[i + 1:i + 3], ['nop', 'nop'])

    def test_replace_block(self):
        lines = patches.apply_patch(self.method(), REPLACE).splitlines()
        i = lines.index('getlocal 6')
        self.assertEqual(lines[i + 1:i + 4], ['pop', 'pop', 'jump ofs0081'])
        self.assertNotIn('ifeq ofs0081', lines)

    def test_missing_code_fails(self):
        with self.assertRaises(ValueError) as ctx:
            patches.apply_patch(self.method().replace('pushscope', 'nop'), INSERT)
        self.assertIn('0 fois', str(ctx.exception))

    def test_already_patched_fails(self):
        for patch in (INSERT, REPLACE):
            with self.assertRaises(ValueError):
                patches.apply_patch(patches.apply_patch(self.method(), patch), patch)

    def test_real_patches_are_well_formed(self):
        for patch in patches.PATCHES:
            self.assertTrue(('anchor' in patch and 'code' in patch) or ('find' in patch and 'replace' in patch))
            self.assertEqual(patch['gfx'], patches.LIVE_HUD_GFX)
            self.assertIn(patch['method'][0], ('method', 'getter', 'setter'))
            # Étiquettes ajoutées : préfixe réservé, définies une seule fois.
            labels = [l[:-1] for l in patches.new_lines(patch) if l.endswith(':') and not l.startswith('ofs')]
            self.assertTrue(all(l.startswith('susu') for l in labels), labels)
            self.assertEqual(len(labels), len(set(labels)))

    def test_patches_never_call_the_engine(self):
        """Régression : appeler le moteur depuis la barre a fait planter le jeu au chargement."""
        for patch in patches.PATCHES:
            new = '\n'.join(patches.new_lines(patch))
            old = '\n'.join(patches._lines(patch.get('find', [])))
            for name in patches.ENGINE_CALLS:
                # Un appel déjà présent dans le code d'origine remplacé est toléré, jamais un appel ajouté.
                self.assertLessEqual(new.count(name), old.count(name), (patch['method'], name))

    def test_class_path(self):
        self.assertEqual(patches.class_path('a.b.C'), 'scripts/a/b/C.pcode')


class DbpfTest(unittest.TestCase):
    def test_round_trip(self):
        path = os.path.join(tempfile.mkdtemp(), 'x.package')
        resources = [((patches.GFX_TYPE, 0, 0x5F9A8D994447F9C9), b'GFX' + b'\x00' * 50), ((1, 2, 3), b'abc')]
        dbpf.write_package(path, resources)
        entries = dbpf.read_index(path)
        self.assertEqual([(e['type'], e['group'], e['instance']) for e in entries], [k for k, _ in resources])
        self.assertEqual([dbpf.read_resource(e) for e in entries], [d for _, d in resources])

    def test_reads_zlib_and_constant_type(self):
        """Comme UI.package : ressources compressées zlib et type commun dans l'en-tête d'index."""
        data = b'hello GFX' * 10
        compressed = zlib.compress(data)
        index = struct.pack('<II', 1, patches.GFX_TYPE)  # flags : type constant
        index += struct.pack('<IIIIIIHH', 0, 0x11, 0x22, 96, len(compressed) | 0x80000000, len(data),
                             dbpf.COMPRESSION_ZLIB, 1)
        header = bytearray(96)
        header[:4] = b'DBPF'
        struct.pack_into('<II', header, 4, 2, 1)
        struct.pack_into('<I', header, 36, 1)
        struct.pack_into('<I', header, 44, len(index))
        struct.pack_into('<Q', header, 64, 96 + len(compressed))
        path = os.path.join(tempfile.mkdtemp(), 'z.package')
        with open(path, 'wb') as f:
            f.write(bytes(header) + compressed + index)
        entry, = dbpf.read_index(path)
        self.assertEqual((entry['type'], entry['instance']), (patches.GFX_TYPE, 0x11 << 32 | 0x22))
        self.assertEqual(dbpf.read_resource(entry), data)

    def test_empty_or_invalid_files_are_ignored(self):
        folder = tempfile.mkdtemp()
        empty = os.path.join(folder, 'empty.package')
        open(empty, 'wb').close()
        self.assertEqual(dbpf.read_index(empty), [])


class GuardTest(unittest.TestCase):
    """Garde-fou : seul un corps de méthode prévu peut changer."""

    def test_unexpected_change_is_rejected(self):
        original = build_ui.extract_gfx(GAME, patches.LIVE_HUD_GFX)[0] if GAME else None
        if original is None:
            self.skipTest('jeu absent')
        with self.assertRaises(build_ui.UIBuildError):
            build_ui.check_only_bodies_changed(original, original, {6317})  # prévu mais pas changé
        build_ui.check_only_bodies_changed(original, original, set())  # rien de prévu, rien de changé


class BuildUiErrorsTest(unittest.TestCase):
    def test_missing_game(self):
        original = build_ui.GAME_DIR_CANDIDATES
        build_ui.GAME_DIR_CANDIDATES = [tempfile.mkdtemp()]
        try:
            with self.assertRaises(build_ui.UIBuildError):
                build_ui.build_ui(os.path.join(tempfile.mkdtemp(), 'ui.package'))
        finally:
            build_ui.GAME_DIR_CANDIDATES = original

    def test_missing_jpexs(self):
        original = build_ui.JPEXS_JAR
        build_ui.JPEXS_JAR = os.path.join(tempfile.mkdtemp(), 'absent.jar')
        try:
            with self.assertRaises(build_ui.UIBuildError) as ctx:
                build_ui.build_ui(os.path.join(tempfile.mkdtemp(), 'ui.package'), game_dir=tempfile.mkdtemp())
            self.assertIn('JPEXS', str(ctx.exception))
        finally:
            build_ui.JPEXS_JAR = original


def _unlabel(lines):
    """Remplace les noms d'étiquettes (définitions et cibles de saut) par un nom générique."""
    out = []
    for line in lines:
        line = line.strip()
        if line.endswith(':'):
            out.append('LABEL:')
        elif line.split(' ')[0] in ('jump', 'iftrue', 'iffalse', 'ifeq', 'ifne', 'iflt', 'ifle', 'ifgt', 'ifge',
                                    'ifstricteq', 'ifstrictne', 'ifnlt', 'ifnle', 'ifngt', 'ifnge'):
            out.append(line.split(' ')[0] + ' LABEL')
        else:
            out.append(line)
    return out


GAME = build_ui.find_game_dir()
HAS_TOOLS = GAME is not None and os.path.exists(build_ui.JPEXS_JAR)


@unittest.skipUnless(HAS_TOOLS, 'jeu ou JPEXS absent')
class BuildUiIntegrationTest(unittest.TestCase):
    """Construit vraiment le package depuis le jeu installé, puis le décompile pour vérifier."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix='sims_unique_ui_test_')
        cls.package = os.path.join(cls.folder, 'SimsUnique_UI.package')
        cls.instances = build_ui.build_ui(cls.package)

    def test_package_replaces_live_hud(self):
        entry, = dbpf.read_index(self.package)
        self.assertEqual((entry['type'], entry['group'], entry['instance']),
                         (patches.GFX_TYPE, 0, patches.LIVE_HUD_GFX))
        self.assertEqual(dbpf.read_resource(entry)[:3], b'GFX')

    def test_patched_code_is_compiled_in(self):
        entry, = dbpf.read_index(self.package)
        gfx = os.path.join(self.folder, 'check.gfx')
        with open(gfx, 'wb') as f:
            f.write(dbpf.read_resource(entry))
        out = os.path.join(self.folder, 'export')
        classes = sorted({p['class'] for p in patches.PATCHES})
        subprocess.run(['java', '-jar', build_ui.JPEXS_JAR, '-format', 'script:pcode', '-selectclass',
                        ','.join(classes), '-export', 'script', out, gfx], check=True, capture_output=True)
        for patch in patches.PATCHES:
            with open(os.path.join(out, *patches.class_path(patch['class']).split('/')), encoding='utf-8') as f:
                method = patches.extract_method(f.read(), *patch['method']).splitlines()
            # JPEXS renomme les étiquettes d'après leur position : on les ignore dans la comparaison.
            self.assertEqual(len(patches._find_block(_unlabel(method), _unlabel(patches.new_lines(patch)))), 1,
                             patch['method'])

    def test_only_patched_method_bodies_changed(self):
        original, _ = build_ui.extract_gfx(GAME, patches.LIVE_HUD_GFX)
        entry, = dbpf.read_index(self.package)
        before = abc.parse(abc.abc_blocks(original)[0])
        after = abc.parse(abc.abc_blocks(dbpf.read_resource(entry))[0])
        changed = [i for i, (x, y) in enumerate(zip(before['codes'], after['codes'])) if x != y]
        expected = sorted({abc.body_index(original, p['class'], p['method'][1], p['method'][0])
                           for p in patches.PATCHES})
        self.assertEqual(changed, expected)
        self.assertEqual(len(before['codes']), len(after['codes']))

if __name__ == '__main__':
    unittest.main()
