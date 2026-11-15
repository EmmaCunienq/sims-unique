"""Chargement du mod, injections dans le jeu et commandes console."""
import os
import unittest

import fakegame


class LoadingTest(unittest.TestCase):
    def test_mod_loads_without_error(self):
        fakegame.install()
        import sims_unique_main  # noqa: F401
        import sims_unique.hooks  # noqa: F401
        import sims_unique.commands  # noqa: F401
        import sims_unique.interactions  # noqa: F401


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core, ids
        from sims4.tuning.instance_manager import InstanceManager
        self.core = core
        self.ids = ids
        self.InstanceManager = InstanceManager

    def test_interactions_added_to_sim_tuning(self):
        affordances = {i: object() for i in self.ids.INTERACTION_IDS}
        self.w.managers['INTERACTION'] = self.InstanceManager('INTERACTION', affordances)
        sim_tuning = type('object_sim', (), {'_super_affordances': ('existante',)})
        objects = self.InstanceManager('OBJECT', {('OBJECT', self.ids.SIM_OBJECT_TUNING_ID): sim_tuning})
        self.assertEqual(objects.load_data_into_class_instances(), 'loaded')
        self.assertEqual(sim_tuning._super_affordances[0], 'existante')
        self.assertEqual(set(sim_tuning._super_affordances[1:]), set(affordances.values()))
        self.assertEqual(len(sim_tuning._super_affordances), 1 + len(self.ids.INTERACTIONS))

    def test_other_managers_are_untouched(self):
        manager = self.InstanceManager('SNIPPET')
        self.assertEqual(manager.load_data_into_class_instances(), 'loaded')

    def test_missing_package_is_logged(self):
        self.w.managers['INTERACTION'] = self.InstanceManager('INTERACTION', {})
        sim_tuning = type('object_sim', (), {'_super_affordances': ()})
        objects = self.InstanceManager('OBJECT', {('OBJECT', self.ids.SIM_OBJECT_TUNING_ID): sim_tuning})
        objects.load_data_into_class_instances()
        self.assertEqual(sim_tuning._super_affordances, ())
        with open(fakegame.log_file(), encoding='utf-8') as f:
            self.assertIn('SimsUnique.package manquant', f.read())

    def test_zone_load_enforces_sim_and_starts_watcher(self):
        mom, dad, *_ = fakegame.family(self.w)
        self.core.current_state()
        self.w.client.active_sim_info = dad
        self.w.zone.on_loading_screen_animation_finished()
        self.assertEqual(self.w.zone.loaded, 1)  # la méthode d'origine est bien appelée
        self.assertIs(self.w.client.active_sim_info, mom)
        self.assertEqual(len(self.w.alarms), 1)
        self.assertTrue(self.w.alarms[0].repeating)

    def test_watcher_detects_death(self):
        mom, dad, teen, *_ = fakegame.family(self.w)
        self.w.zone.on_loading_screen_animation_finished()
        mom.kill()
        self.w.alarms[-1].callback(self.w.alarms[-1])
        self.assertIs(self.w.client.active_sim_info, teen)

    def test_second_zone_load_replaces_watcher(self):
        fakegame.family(self.w)
        self.w.zone.on_loading_screen_animation_finished()
        self.w.zone.on_loading_screen_animation_finished()
        self.assertTrue(self.w.alarms[0].cancelled)
        self.assertFalse(self.w.alarms[1].cancelled)

    def test_hook_error_falls_back_to_game(self):
        fakegame.family(self.w)
        original = self.core.should_block_switch
        self.core.should_block_switch = lambda *a: 1 / 0
        try:
            self.assertTrue(self.w.client.set_active_sim_info(self.w.all_sims[2]))
        finally:
            self.core.should_block_switch = original


class CommandsTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        import sims4.commands
        self.registry = sims4.commands.registry
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)

    def run_cmd(self, name, *args):
        self.w.console.clear()
        self.registry[name](*args, _connection=None)
        return self.w.console

    def test_all_commands_registered_in_french_and_english(self):
        for name in ('unique.statut', 'unique.status', 'unique.heritier', 'unique.heir',
                     'unique.heritier_defaut', 'unique.heir_default', 'unique.abdiquer', 'unique.abdicate',
                     'unique.on', 'unique.off', 'unique.mode', 'unique.aide', 'unique.help'):
            self.assertIn(name, self.registry)

    def test_status(self):
        self.assertEqual(self.run_cmd('unique.statut'), ['Sim joué : Mere Test', 'Héritier : Ado Test (par défaut)', 'Affichage : Invisible (1)'])

    def test_heir_list_and_choice(self):
        lines = self.run_cmd('unique.heritier')
        self.assertEqual(lines[1], '1. Ado Test - enfant (par défaut) <- héritier')
        self.assertEqual(lines[4], '4. Tante Test - membre du foyer')
        self.run_cmd('unique.heritier', 3)
        self.assertIn('Héritier : Pere Test (choisi)', self.run_cmd('unique.statut'))
        self.run_cmd('unique.heritier_defaut')
        self.assertIn('Héritier : Ado Test (par défaut)', self.run_cmd('unique.statut'))

    def test_abdicate(self):
        self.assertEqual(self.run_cmd('unique.abdiquer'), ['Vous jouez maintenant Ado Test.'])

    def test_off_on(self):
        self.run_cmd('unique.off')
        self.assertTrue(self.w.client.set_active_sim_info(self.aunt))
        self.run_cmd('unique.on')
        self.assertIn('Sim joué : Tante Test', self.run_cmd('unique.statut'))

    def test_help(self):
        self.assertEqual(len(self.run_cmd('unique.aide')), 8)

    def test_error_is_reported_in_console(self):
        from sims_unique import core
        original = core.status_text
        core.status_text = lambda: 1 / 0
        try:
            self.assertIn('Erreur', self.run_cmd('unique.statut')[0])
        finally:
            core.status_text = original


if __name__ == '__main__':
    unittest.main()
