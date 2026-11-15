"""Options du menu en jeu : visibilité, libellés, actions."""
import types
import unittest

import fakegame
from fakegame import Sim


class InteractionsTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import core, interactions
        self.core = core
        self.i = interactions
        self.mom, self.dad, self.teen, self.kid, self.aunt = fakegame.family(self.w)
        self.core.current_state()

    def ctx(self, actor):
        return types.SimpleNamespace(sim=Sim(actor))

    def visible(self, cls, actor, target):
        return bool(cls._test(Sim(target), self.ctx(actor)))

    def menu(self, actor, target):
        """Libellés de toutes les options visibles, comme dans le pie menu."""
        names = []
        for cls_name in sorted(fakegame_ids()):
            cls = getattr(self.i, cls_name)
            if self.visible(cls, actor, target):
                names.append(cls.get_name(target=Sim(target), context=self.ctx(actor)))
        return sorted(names)

    def run_interaction(self, cls, actor, target):
        inst = cls(Sim(target), self.ctx(actor))
        gen = inst._run_interaction_gen(None)
        with self.assertRaises(StopIteration) as stop:
            next(gen)
        self.assertTrue(stop.exception.value)
        return inst

    # -- menus -------------------------------------------------------------- #

    def test_menu_on_self_without_cheats(self):
        self.assertEqual(self.menu(self.mom, self.mom), [
            'Sims unique : Passer la main à Ado Test',
            'Sims unique : Voir la succession',
        ])

    def test_menu_on_self_with_testingcheats(self):
        self.w.cheats_enabled = True
        self.assertEqual(self.menu(self.mom, self.mom), [
            'Affichage : Vision du foyer',
            'Affichage : État du foyer',
            'Désactiver pour ce foyer',
            'Sims unique : Passer la main à Ado Test',
            'Sims unique : Voir la succession',
        ])

    def test_settings_menu_flags_match_package_category(self):
        from sims_unique import ids
        in_menu = {cls for name, cls in ids.INTERACTIONS.items() if name in ids.CATEGORY_INTERACTIONS}
        flagged = {cls for cls in ids.INTERACTIONS.values() if getattr(self.i, cls).in_settings_menu}
        self.assertEqual(in_menu, flagged)

    def test_menu_on_other_household_sim(self):
        self.assertEqual(self.menu(self.mom, self.dad), ['Sims unique : Désigner comme héritier'])

    def test_menu_on_current_heir_is_empty(self):
        self.assertEqual(self.menu(self.mom, self.teen), [])

    def test_menu_on_outsider_is_empty(self):
        outsider = self.w.add_sim(9, 'Voisin', fakegame.Age.ADULT, in_household=False)
        self.assertEqual(self.menu(self.mom, outsider), [])

    def test_menu_with_manual_heir_offers_reset(self):
        self.w.cheats_enabled = True
        self.core.set_heir_sim(self.aunt)
        self.assertIn('Sims unique : Revenir à l\'héritier par défaut (Ado Test)', self.menu(self.mom, self.mom))
        self.assertIn('Sims unique : Passer la main à Tante Test', self.menu(self.mom, self.mom))

    def test_menu_when_disabled(self):
        self.core.disable()
        self.assertEqual(self.menu(self.dad, self.dad), [])
        self.w.cheats_enabled = True
        self.assertEqual(self.menu(self.dad, self.dad), ['Ne jouer que ce Sim'])
        self.assertEqual(self.menu(self.dad, self.kid), [])

    def test_no_abdicate_without_heir(self):
        for sim in (self.dad, self.teen, self.kid, self.aunt):
            self.w.remove_from_household(sim)
        self.assertNotIn('Sims unique : Passer la main', ' '.join(self.menu(self.mom, self.mom)))

    def test_non_sim_target_is_rejected(self):
        not_a_sim = types.SimpleNamespace(is_sim=False)
        self.assertFalse(self.i.SimsUniqueStatusInteraction._test(not_a_sim, self.ctx(self.mom)))

    # -- actions ------------------------------------------------------------ #

    def test_set_heir_action(self):
        self.run_interaction(self.i.SimsUniqueSetHeirInteraction, self.mom, self.aunt)
        self.assertIs(self.core.get_heir(), self.aunt)

    def test_status_action(self):
        self.run_interaction(self.i.SimsUniqueStatusInteraction, self.mom, self.mom)
        text = self.w.notifications[-1]
        self.assertIn('1. Ado Test - enfant (par défaut) <- héritier', text)
        self.assertIn('Désigner comme héritier', text)
        self.assertNotIn('unique.heritier', text)

    def test_abdicate_confirmed(self):
        self.run_interaction(self.i.SimsUniqueAbdicateInteraction, self.mom, self.mom)
        self.assertIn('Ado Test', self.w.dialogs[-1].text)
        self.w.answer_dialog(accept=True)
        self.assertIs(self.core.current_state()[2], self.teen)

    def test_abdicate_cancelled(self):
        self.run_interaction(self.i.SimsUniqueAbdicateInteraction, self.mom, self.mom)
        self.w.answer_dialog(accept=False)
        self.assertIs(self.core.current_state()[2], self.mom)

    def test_disable_confirmed(self):
        self.run_interaction(self.i.SimsUniqueDisableInteraction, self.mom, self.mom)
        self.w.answer_dialog(accept=True)
        self.assertFalse(self.core.is_enabled())

    def test_enable_confirmed(self):
        self.core.disable()
        self.run_interaction(self.i.SimsUniqueEnableInteraction, self.dad, self.dad)
        self.w.answer_dialog(accept=True)
        self.assertIs(self.core.current_state()[2], self.dad)

    def test_default_heir_action(self):
        self.core.set_heir_sim(self.aunt)
        self.run_interaction(self.i.SimsUniqueDefaultHeirInteraction, self.mom, self.mom)
        self.assertIs(self.core.get_heir(), self.teen)

    def test_error_in_action_does_not_crash(self):
        cls = self.i.SimsUniqueSetHeirInteraction
        original = self.core.set_heir_sim
        self.core.set_heir_sim = lambda sim: 1 / 0
        try:
            self.run_interaction(cls, self.mom, self.aunt)
        finally:
            self.core.set_heir_sim = original
        with open(fakegame.log_file(), encoding='utf-8') as f:
            self.assertIn('ZeroDivisionError', f.read())


def fakegame_ids():
    from sims_unique import ids
    return ids.INTERACTIONS.values()


if __name__ == '__main__':
    unittest.main()
