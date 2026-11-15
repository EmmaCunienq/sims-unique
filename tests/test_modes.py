"""Modes d'affichage : 1 invisible, 2 vision du foyer, 3 état du foyer."""
import types
import unittest

import fakegame
from fakegame import Age, Sim


class ModesTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core, interactions
        self.core = core
        self.i = interactions
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)
        self.client = self.w.client
        self.w.zone.on_loading_screen_animation_finished()

    def test_default_mode_is_invisible(self):
        self.assertEqual(self.core.current_mode(), 1)
        self.assertEqual(self.client.bar(), ['Mere'])

    def test_household_mode_shows_everyone_but_only_controlled_is_clickable(self):
        updates = self.client.bar_updates
        self.core.set_mode(2)
        self.assertEqual(sorted(self.client.bar()), ['Ado', 'Enfant', 'Mere', 'Pere', 'Tante'])
        self.assertEqual(self.client.clickable(), ['Mere'])
        self.assertGreater(self.client.bar_updates, updates)  # l'interface est rafraîchie
        self.assertIn('Vision du foyer', self.w.notifications[-1])

    def test_household_state_mode(self):
        self.core.set_mode(3)
        self.assertEqual(len(self.client.bar()), 5)
        self.assertEqual(self.client.clickable(), ['Mere'])

    def test_back_to_invisible(self):
        self.core.set_mode(2)
        self.core.set_mode(1)
        self.assertEqual(self.client.bar(), ['Mere'])

    def test_game_adding_sims_is_kept_in_mode_2(self):
        self.core.set_mode(2)
        baby = self.w.add_sim(6, 'Bebe', Age.BABY, parents=(1, 2), in_household=False)
        self.w.household.members.append(baby)
        self.client.add_selectable_sim_info(baby)
        self.assertIn('Bebe', self.client.bar())
        self.assertNotIn('Bebe', self.client.clickable())

    def test_watcher_keeps_everyone_in_mode_2(self):
        self.core.set_mode(2)
        self.w.alarms[-1].callback(self.w.alarms[-1])
        self.assertEqual(len(self.client.bar()), 5)

    def test_abdicate_moves_the_lock(self):
        self.core.set_mode(2)
        updates = self.client.bar_updates
        self.core.abdicate()
        self.assertEqual(self.client.clickable(), ['Ado'])
        self.assertIs(self.client.active_sim_info, self.teen)
        self.assertGreater(self.client.bar_updates, updates)

    def test_death_in_mode_2(self):
        self.core.set_mode(3)
        self.mom.kill()
        self.w.alarms[-1].callback(self.w.alarms[-1])
        self.assertIs(self.client.active_sim_info, self.teen)
        self.assertIn('Ado', self.client.clickable())
        self.assertNotIn('Pere', self.client.clickable())

    def test_disable_unlocks_everyone(self):
        self.core.set_mode(2)
        self.core.disable()
        self.assertEqual(sorted(self.client.clickable()), ['Ado', 'Enfant', 'Mere', 'Pere', 'Tante'])

    def test_lock_ignores_outsiders_and_babies_stay_native(self):
        self.core.set_mode(2)
        visitor = self.w.add_sim(9, 'Voisin', Age.ADULT, in_household=False)
        self.assertTrue(visitor.get_is_enabled_in_skewer())
        baby = self.w.add_sim(10, 'Bebe', Age.BABY)
        self.assertFalse(baby.get_is_enabled_in_skewer())

    def test_mode_is_saved_per_household(self):
        self.core.set_mode(3)
        from sims_unique import storage
        storage._cache = None
        self.assertEqual(self.core.current_mode(), 3)
        self.w.household = fakegame.Household(2000)
        self.assertEqual(self.core.current_mode(), 1)

    def test_invalid_mode(self):
        self.assertIn('invalide', self.core.set_mode(7))
        self.assertEqual(self.core.current_mode(), 1)

    def test_status_shows_mode(self):
        self.core.set_mode(2)
        self.assertIn('Affichage : Vision du foyer (2)', self.core.status_text())

    def test_mode_commands(self):
        import sims4.commands
        self.w.console.clear()
        sims4.commands.registry['unique.mode'](_connection=None)
        self.assertEqual(self.w.console[1], '2 : Vision du foyer - le foyer apparaît dans la barre, en petit et grisé')
        sims4.commands.registry['unique.mode'](3, _connection=None)
        self.assertEqual(self.core.current_mode(), 3)

    def test_mode_menu_needs_shift_click(self):
        self.w.cheats_enabled = True  # testingcheats ne suffit pas
        ctx = types.SimpleNamespace(sim=Sim(self.mom), shift_held=False)
        self.assertFalse(self.i.SimsUniqueModeHouseholdInteraction._test(Sim(self.mom), ctx))

    def test_mode_menu_offers_other_modes(self):
        ctx = types.SimpleNamespace(sim=Sim(self.mom), shift_held=True)
        classes = (self.i.SimsUniqueModeInvisibleInteraction, self.i.SimsUniqueModeHouseholdInteraction,
                   self.i.SimsUniqueModeHouseholdStateInteraction)
        visible = [c.get_name(target=Sim(self.mom), context=ctx) for c in classes if c._test(Sim(self.mom), ctx)]
        self.assertEqual(visible, ['Affichage : Vision du foyer', 'Affichage : État du foyer'])
        inst = self.i.SimsUniqueModeHouseholdInteraction(Sim(self.mom), ctx)
        for _ in inst._run_interaction_gen(None):
            pass
        self.assertEqual(self.core.current_mode(), 2)
        # Pas de menu de mode sur un autre Sim.
        self.assertFalse(self.i.SimsUniqueModeInvisibleInteraction._test(Sim(self.dad), ctx))


class MoodTest(unittest.TestCase):
    """Mode 2 : émotion masquée DANS LA BARRE SEULEMENT (marqueur), jamais dans les messages d'émotion."""

    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core
        self.core = core
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)
        self.w.zone.on_loading_screen_animation_finished()

    def career(self, sim_info):
        return self.w.client.bar_data(sim_info)['career_category']

    def test_mode_2_marks_locked_sims_only(self):
        self.core.set_mode(2)
        self.assertEqual(self.career(self.dad), self.core.BAR_MOOD_HIDDEN_MARKER)
        self.assertEqual(self.career(self.kid), self.core.BAR_MOOD_HIDDEN_MARKER)
        self.assertIsNone(self.career(self.mom))  # Sim joué : émotion visible

    def test_mode_3_and_1_do_not_mark(self):
        self.core.set_mode(3)
        self.assertIsNone(self.career(self.dad))
        self.core.set_mode(1)
        self.assertIsNone(self.career(self.dad))

    def test_marker_matches_ui_patch(self):
        import sys
        sys.path.insert(0, fakegame.ROOT)
        from uimod import patches
        self.assertEqual(patches.MOOD_HIDDEN_MARKER, str(self.core.BAR_MOOD_HIDDEN_MARKER))
        self.assertLess(self.core.BAR_MOOD_HIDDEN_MARKER, 2 ** 32)  # champ uint32 du protobuf

    def test_real_moods_are_never_altered(self):
        """Régression : une émotion vide envoyée par le script cassait le panneau de discussion."""
        self.core.set_mode(2)
        for sim in (self.dad, self.mom):
            msg = sim.get_sim_instance().Buffs._create_mood_update_msg()
            self.assertEqual(msg.mood_key, fakegame.BuffComponent.MOOD_HAPPY)

    def test_abdicate_moves_the_marker(self):
        self.core.set_mode(2)
        updates = self.w.client.bar_updates
        self.core.abdicate()
        self.assertIsNone(self.career(self.teen))
        self.assertEqual(self.career(self.mom), self.core.BAR_MOOD_HIDDEN_MARKER)
        self.assertGreater(self.w.client.bar_updates, updates)

    def test_disable_removes_markers(self):
        self.core.set_mode(2)
        self.core.disable()
        self.assertIsNone(self.career(self.dad))

if __name__ == '__main__':
    unittest.main()
