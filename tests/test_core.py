"""Verrou, succession, héritier manuel, activation et sauvegarde."""
import json
import unittest

import fakegame
from fakegame import Age


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core, storage
        self.core = core
        self.storage = storage
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)

    def state(self):
        return self.core.current_state()

    def try_switch(self, sim_info):
        """Simule un clic du joueur sur un Sim (passe par l'injection)."""
        return self.w.client.set_active_sim_info(sim_info)


class FirstLoadTest(CoreTestCase):
    def test_active_sim_becomes_controlled(self):
        _, data, controlled, heir = self.state()
        self.assertIs(controlled, self.mom)
        self.assertIs(heir, self.teen)
        self.assertIn('uniquement Mere Test', self.w.notifications[0])

    def test_no_active_sim_does_nothing(self):
        self.w.client.active_sim_info = None
        _, data, controlled, _ = self.state()
        self.assertIsNone(controlled)
        self.assertIsNone(data['controlled'])

    def test_already_ghost_sim_is_not_succeeded(self):
        self.mom.kill()
        _, _, controlled, _ = self.state()
        self.assertIs(controlled, self.mom)


class LockTest(CoreTestCase):
    def setUp(self):
        super().setUp()
        self.state()

    def test_switch_to_other_sim_is_blocked(self):
        self.assertFalse(self.try_switch(self.dad))
        self.assertIs(self.w.client.active_sim_info, self.mom)
        self.assertIn('Vous ne pouvez jouer que Mere Test', self.w.notifications[-1])

    def test_block_message_is_not_spammed(self):
        self.try_switch(self.dad)
        self.try_switch(self.kid)
        blocked = [n for n in self.w.notifications if 'ne pouvez jouer' in n]
        self.assertEqual(len(blocked), 1)

    def test_switch_to_controlled_sim_is_allowed(self):
        self.w.client.active_sim_info = None
        self.assertTrue(self.try_switch(self.mom))

    def test_allowed_while_zone_loading(self):
        self.w.zone.is_zone_running = False
        self.assertTrue(self.try_switch(self.dad))

    def test_allowed_when_mod_disabled(self):
        self.core.disable()
        self.assertTrue(self.try_switch(self.dad))

    def test_allowed_when_controlled_not_selectable(self):
        self.w.client.selectable_sims.remove(self.mom)
        self.assertTrue(self.try_switch(self.dad))

    def test_enforce_puts_controlled_sim_back(self):
        self.w.client.active_sim_info = self.dad  # le jeu a changé de Sim par un autre chemin
        self.core.enforce_active_sim()
        self.assertIs(self.w.client.active_sim_info, self.mom)


class SuccessionTest(CoreTestCase):
    def setUp(self):
        super().setUp()
        self.state()

    def test_death_passes_control_to_heir(self):
        self.mom.kill()
        self.core.enforce_active_sim()
        _, data, controlled, heir = self.state()
        self.assertIs(controlled, self.teen)
        self.assertIs(self.w.client.active_sim_info, self.teen)
        self.assertIn('Mere Test est mort(e)', self.w.notifications[-1])
        self.assertIn('Vous jouez maintenant Ado Test', self.w.notifications[-1])
        # Nouvel héritier calculé depuis l'Ado : pas d'enfant, ni conjoint -> frère/sœur.
        self.assertIs(heir, self.kid)

    def test_leaving_household_passes_control(self):
        self.w.remove_from_household(self.mom)
        _, _, controlled, _ = self.state()
        self.assertIs(controlled, self.teen)
        self.assertIn('n\'est plus là', self.w.notifications[-1])

    def test_game_switch_after_death_goes_to_heir(self):
        self.mom.kill()
        # Le jeu essaie de passer au Père : le mod fait la succession vers l'Ado puis bloque le Père.
        self.try_switch(self.dad)
        self.assertIs(self.w.client.active_sim_info, self.teen)

    def test_manual_heir_is_used_on_death(self):
        self.core.set_heir_sim(self.aunt)
        self.mom.kill()
        _, _, controlled, _ = self.state()
        self.assertIs(controlled, self.aunt)

    def test_dead_heir_is_replaced(self):
        self.teen.kill()
        _, _, _, heir = self.state()
        self.assertIs(heir, self.kid)

    def test_no_heir_ends_lineage(self):
        for sim in (self.dad, self.teen, self.kid, self.aunt):
            self.w.remove_from_household(sim)
        self.mom.kill()
        _, data, controlled, _ = self.state()
        self.assertIsNone(controlled)
        self.assertFalse(data['enabled'])
        self.assertIn('la lignée s\'arrête', self.w.notifications[-1])
        self.assertTrue(self.try_switch(self.mom))  # plus de verrou

    def test_new_oldest_child_becomes_default_heir(self):
        self.w.add_sim(6, 'Aine', Age.YOUNGADULT, parents=(1,))
        _, _, _, heir = self.state()
        self.assertEqual(heir.first_name, 'Aine')


class ManualHeirTest(CoreTestCase):
    def setUp(self):
        super().setUp()
        self.state()

    def test_set_heir_sim(self):
        self.core.set_heir_sim(self.aunt)
        _, data, _, heir = self.state()
        self.assertIs(heir, self.aunt)
        self.assertTrue(data['heir_manual'])

    def test_manual_heir_survives_new_child(self):
        self.core.set_heir_sim(self.aunt)
        self.w.add_sim(6, 'Aine', Age.YOUNGADULT, parents=(1,))
        self.assertIs(self.state()[3], self.aunt)

    def test_choosing_default_heir_is_not_manual(self):
        self.core.set_heir_sim(self.teen)
        self.assertFalse(self.state()[1]['heir_manual'])

    def test_cannot_choose_self_or_outsider(self):
        outsider = self.w.add_sim(9, 'Voisin', Age.ADULT, in_household=False)
        self.assertIn('ne peut pas', self.core.set_heir_sim(self.mom))
        self.assertIn('ne peut pas', self.core.set_heir_sim(outsider))
        self.assertIs(self.state()[3], self.teen)

    def test_manual_heir_leaving_falls_back_to_default(self):
        self.core.set_heir_sim(self.aunt)
        self.w.remove_from_household(self.aunt)
        _, data, _, heir = self.state()
        self.assertIs(heir, self.teen)
        self.assertFalse(data['heir_manual'])
        self.assertIn('n\'est plus disponible', self.w.notifications[-1])

    def test_set_heir_by_index(self):
        self.core.set_heir(4)  # liste : Ado, Enfant, Père, Tante
        self.assertIs(self.state()[3], self.aunt)

    def test_set_heir_invalid_index(self):
        self.assertIn('invalide', self.core.set_heir(0))
        self.assertIn('invalide', self.core.set_heir(99))

    def test_reset_heir(self):
        self.core.set_heir_sim(self.aunt)
        self.assertEqual(self.core.default_heir_if_manual(), self.teen)
        self.core.reset_heir()
        self.assertIs(self.state()[3], self.teen)
        self.assertIsNone(self.core.default_heir_if_manual())

    def test_can_be_heir(self):
        self.assertFalse(self.core.can_be_heir(self.mom))   # soi-même
        self.assertFalse(self.core.can_be_heir(self.teen))  # déjà héritier
        self.assertTrue(self.core.can_be_heir(self.dad))
        self.dad.kill()
        self.assertFalse(self.core.can_be_heir(self.dad))


class AbdicateEnableTest(CoreTestCase):
    def setUp(self):
        super().setUp()
        self.state()

    def test_abdicate(self):
        result = self.core.abdicate()
        self.assertIn('Ado Test', result)
        _, _, controlled, heir = self.state()
        self.assertIs(controlled, self.teen)
        self.assertIs(self.w.client.active_sim_info, self.teen)
        self.assertIn('Mere Test passe la main', self.w.notifications[-1])
        # Mère est vivante : elle n'est plus jouable.
        self.assertFalse(self.try_switch(self.mom))

    def test_abdicate_without_heir(self):
        for sim in (self.dad, self.teen, self.kid, self.aunt):
            self.w.remove_from_household(sim)
        self.assertIn('Aucun héritier', self.core.abdicate())
        self.assertIs(self.state()[2], self.mom)

    def test_disable_then_enable_with_other_sim(self):
        self.core.disable()
        self.assertFalse(self.core.is_enabled())
        self.core.enable_with(self.dad)
        _, _, controlled, heir = self.state()
        self.assertIs(controlled, self.dad)
        self.assertIs(self.w.client.active_sim_info, self.dad)
        self.assertIs(heir, self.teen)

    def test_enable_uses_active_sim(self):
        self.core.disable()
        self.w.client.active_sim_info = self.aunt
        self.core.enable()
        self.assertIs(self.state()[2], self.aunt)

    def test_status_text(self):
        self.assertEqual(self.core.status_text(), ['Sim joué : Mere Test', 'Héritier : Ado Test (par défaut)', 'Affichage : Invisible (1)'])
        self.core.disable()
        self.assertIn('désactivé', self.core.status_text()[0])


class StorageTest(CoreTestCase):
    def test_state_is_saved_and_reloaded(self):
        self.state()
        self.core.set_heir_sim(self.aunt)
        with open(fakegame.data_file(), encoding='utf-8') as f:
            saved = json.load(f)
        self.assertEqual(saved['1000']['controlled'], 1)
        self.assertEqual(saved['1000']['heir'], 5)
        self.assertTrue(saved['1000']['heir_manual'])

        # Nouvelle session de jeu : le cache est vidé, le Sim actif est un autre.
        self.storage._cache = None
        self.w.client.active_sim_info = self.dad
        _, _, controlled, heir = self.state()
        self.assertIs(controlled, self.mom)
        self.assertIs(heir, self.aunt)

    def test_households_are_independent(self):
        self.state()
        other = fakegame.Household(2000)
        self.w.household = other
        neighbour = self.w.add_sim(20, 'Voisin', Age.ADULT)
        self.w.client.active_sim_info = neighbour
        self.assertIs(self.state()[2], neighbour)
        self.assertEqual(self.storage.get_household_data(1000)['controlled'], 1)

    def test_corrupt_file_is_ignored(self):
        with open(fakegame.data_file(), 'w', encoding='utf-8') as f:
            f.write('{pas du json')
        self.storage._cache = None
        self.assertIs(self.state()[2], self.mom)


if __name__ == '__main__':
    unittest.main()
