"""Ressources du menu « Sims unique » : catégorie, SimData, textes, logo."""
import glob
import os
import struct
import sys
import unittest
import xml.etree.ElementTree as ET

import fakegame

sys.path.insert(0, fakegame.ROOT)
from uimod import logo, menu_resources, simdata  # noqa: E402

fakegame.install()
from sims_unique import ids  # noqa: E402

GAME_SIMDATA = sorted(glob.glob(os.path.join(fakegame.ROOT, 'tools', 'work', 'simdata', '*.simdata')))


class CategoryTest(unittest.TestCase):
    def test_tuning(self):
        root = ET.fromstring(menu_resources.category_tuning())
        self.assertEqual((root.get('c'), root.get('i'), root.get('m')),
                         ('PieMenuCategory', 'pie_menu_category', 'interactions.pie_menu_category'))
        self.assertEqual(int(root.get('s')), ids.CATEGORY_ID)
        values = {el.get('n'): el.text for el in root}
        self.assertEqual(int(values['_display_name'], 16), menu_resources.label_hash())
        self.assertEqual(values['_icon'], '00b2d882:00000000:{:016x}'.format(ids.LOGO_ID))
        self.assertEqual(values['_collapsible'], 'False')

    def test_simdata_values(self):
        sim = simdata.parse(menu_resources.category_simdata())
        self.assertEqual(sim['name'], ids.CATEGORY_NAME)
        self.assertEqual(sim['schema']['hash'], 0xE2EAA141)
        self.assertEqual(simdata.get_value(sim, '_display_name'), menu_resources.label_hash())
        self.assertEqual(simdata.get_value(sim, '_icon'), (0x00B2D882, 0, ids.LOGO_ID))
        self.assertEqual(simdata.get_value(sim, '_parent'), 0)
        self.assertEqual(simdata.get_value(sim, '_collapsible'), False)
        self.assertEqual(simdata.get_value(sim, 'mood_overrides'), (-0x80000000, 0))

    @unittest.skipUnless(GAME_SIMDATA, 'SimData du jeu non extraites (tools/work/simdata)')
    def test_simdata_layout_matches_game(self):
        """Même schéma, mêmes colonnes et même taille de ligne qu'une catégorie du jeu."""
        ours = simdata.parse(menu_resources.category_simdata())
        for path in GAME_SIMDATA:
            with open(path, 'rb') as f:
                try:
                    game = simdata.parse(f.read())
                except ValueError:
                    continue
            if game['schema']['hash'] == ours['schema']['hash']:
                break
        self.assertEqual(game['schema'], ours['schema'])
        self.assertEqual(len(game['row']), len(ours['row']))

    @unittest.skipUnless(GAME_SIMDATA, 'SimData du jeu non extraites (tools/work/simdata)')
    def test_simdata_writer_round_trips_game_files(self):
        checked = 0
        for path in GAME_SIMDATA:
            with open(path, 'rb') as f:
                data = f.read()
            try:
                sim = simdata.parse(data)
            except ValueError:
                continue
            self.assertEqual(simdata.write(sim), data, path)
            checked += 1
        self.assertGreater(checked, 100)

    def test_resource_keys(self):
        keys = [k for k, _ in menu_resources.resources()]
        self.assertIn((0x03E9D964, 0, ids.CATEGORY_ID), keys)
        self.assertIn((0x545AC67A, 0x00E9D967, ids.CATEGORY_ID), keys)
        self.assertIn((0x00B2D882, 0, ids.LOGO_ID), keys)
        stbl = [k for k in keys if k[0] == 0x220557DA]
        self.assertIn(0x07, [k[2] >> 56 for k in stbl])  # français
        self.assertEqual(len(set(k[2] & 0x00FFFFFFFFFFFFFF for k in stbl)), 1)


class StringTableTest(unittest.TestCase):
    def test_stbl_format(self):
        data = menu_resources.string_table({0x12345678: 'Sims unique', 0x9ABCDEF0: 'Été'})
        self.assertEqual(data[:4], b'STBL')
        version, compressed, count, reserved, total = struct.unpack_from('<HBQHI', data, 4)
        self.assertEqual((version, compressed, count, reserved), (5, 0, 2, 0))
        p, texts = 21, []
        for _ in range(count):
            key, flags, length = struct.unpack_from('<IBH', data, p)
            texts.append((key, data[p + 7:p + 7 + length].decode('utf-8')))
            p += 7 + length
        self.assertEqual(texts, [(0x12345678, 'Sims unique'), (0x9ABCDEF0, 'Été')])
        self.assertEqual(total, sum(len(t.encode('utf-8')) + 1 for _, t in texts))
        self.assertEqual(p, len(data))


class LogoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pixels = logo.render()
        cls.dds = logo.to_dds(cls.pixels)

    def test_dds_header_like_game_icons(self):
        self.assertEqual(self.dds[:4], b'DDS ')
        height, width = struct.unpack_from('<II', self.dds, 12)
        self.assertEqual((width, height), (46, 46))
        flags, = struct.unpack_from('<I', self.dds, 80)
        self.assertEqual(flags, 0x41)  # RGB + alpha, non compressé (comme les icônes du jeu)
        self.assertEqual(struct.unpack_from('<IIIII', self.dds, 88),
                         (32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000))
        self.assertEqual(len(self.dds), 128 + 46 * 46 * 4)  # 8592 octets, comme le jeu

    def test_transparent_background_and_visible_shape(self):
        alpha = [p[3] for p in self.pixels]
        self.assertEqual(alpha[0], 0)  # coin transparent
        self.assertGreater(sum(1 for a in alpha if a == 255), 300)
        green = self.pixels[30 * 46 + 18]  # facette du plumbob
        self.assertGreater(green[1], green[0])
        gold = self.pixels[9 * 46 + 17]    # couronne
        self.assertGreater(gold[0], gold[2])

    def test_deterministic(self):
        self.assertEqual(logo.to_dds(logo.render()), self.dds)


if __name__ == '__main__':
    unittest.main()
