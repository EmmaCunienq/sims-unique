"""Bandeau de portraits : seul le Sim joué doit y apparaître."""
import unittest

import fakegame
from fakegame import Age


class BarTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core
        self.core = core
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)
        self.client = self.w.client

    def load_zone(self):
        self.w.zone.on_loading_screen_animation_finished()

    def test_zone_load_keeps_only_controlled_sim(self):
        self.assertEqual(self.client.bar(), ['Mere', 'Pere', 'Ado', 'Enfant', 'Tante'])
        self.load_zone()
        self.assertEqual(self.client.bar(), ['Mere'])
        self.assertIs(self.client.active_sim_info, self.mom)

    def test_hidden_sims_stay_in_household(self):
        self.load_zone()
        self.assertEqual(len(self.w.household.members), 5)

    def test_hiding_when_another_sim_was_active(self):
        self.core.current_state()  # Mère devient le Sim joué
        self.client.active_sim_info = self.dad
        self.load_zone()
        self.assertEqual(self.client.bar(), ['Mere'])
        self.assertIs(self.client.active_sim_info, self.mom)

    def test_game_re_adding_a_sim_is_undone(self):
        self.load_zone()
        baby = self.w.add_sim(6, 'Bebe', Age.BABY, parents=(1, 2), in_household=False)
        self.w.household.members.append(baby)
        self.client.add_selectable_sim_info(baby)  # naissance : le jeu l'ajoute au bandeau
        self.client.add_selectable_sim_info(self.dad)
        self.assertEqual(self.client.bar(), ['Mere'])

    def test_re_adding_during_loading_is_left_to_zone_load(self):
        self.load_zone()
        self.w.zone.is_zone_running = False
        self.client.add_selectable_sim_info(self.dad)
        self.assertIn('Pere', self.client.bar())
        self.w.zone.is_zone_running = True
        self.load_zone()
        self.assertEqual(self.client.bar(), ['Mere'])

    def test_watcher_cleans_the_bar(self):
        self.load_zone()
        self.client.selectable_sims.append(self.aunt)  # ajout par un chemin non intercepté
        self.w.alarms[-1].callback(self.w.alarms[-1])
        self.assertEqual(self.client.bar(), ['Mere'])

    def test_death_shows_heir_only(self):
        self.load_zone()
        self.mom.kill()
        self.w.alarms[-1].callback(self.w.alarms[-1])
        # Mère (morte) est laissée au jeu, l'héritière devient le seul Sim vivant du bandeau.
        self.assertEqual(self.client.bar(), ['Mere', 'Ado'])
        self.assertIs(self.client.active_sim_info, self.teen)
        self.w.remove_from_household(self.mom)  # le jeu retire le défunt du foyer
        self.assertEqual(self.client.bar(), ['Ado'])

    def test_abdicate_swaps_the_bar(self):
        self.load_zone()
        self.core.abdicate()
        self.assertEqual(self.client.bar(), ['Ado'])
        self.assertIs(self.client.active_sim_info, self.teen)

    def test_disable_restores_everyone(self):
        self.load_zone()
        self.core.disable()
        self.assertEqual(sorted(self.client.bar()), ['Ado', 'Enfant', 'Mere', 'Pere', 'Tante'])

    def test_enable_with_other_sim(self):
        self.load_zone()
        self.core.disable()
        self.core.enable_with(self.dad)
        self.assertEqual(self.client.bar(), ['Pere'])
        self.assertIs(self.client.active_sim_info, self.dad)

    def test_end_of_lineage_restores_everyone(self):
        for sim in (self.dad, self.teen, self.kid, self.aunt):
            self.w.remove_from_household(sim)
        self.w.add_sim(7, 'Fantome', Age.ADULT).kill()  # seul autre membre : déjà mort
        self.load_zone()
        self.mom.kill()
        self.core.current_state()
        self.assertEqual(sorted(self.client.bar()), ['Fantome', 'Mere'])

    def test_heir_can_still_be_chosen_by_clicking_in_world(self):
        self.load_zone()
        self.core.set_heir_sim(self.aunt)
        self.assertIs(self.core.get_heir(), self.aunt)

    def test_missing_client_methods_do_not_crash(self):
        fakegame.Client.remove_selectable_sim_info, original = None, fakegame.Client.remove_selectable_sim_info
        try:
            self.load_zone()
            self.assertIs(self.client.active_sim_info, self.mom)
        finally:
            fakegame.Client.remove_selectable_sim_info = original
        with open(fakegame.log_file(), encoding='utf-8') as f:
            self.assertIn('aucune des méthodes', f.read())


if __name__ == '__main__':
    unittest.main()
