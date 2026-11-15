"""Choix de l'héritier par défaut."""
import unittest

import fakegame
from fakegame import Age


class LineageTest(unittest.TestCase):
    def setUp(self):
        self.w = fakegame.reset()
        from sims_unique import lineage
        self.lineage = lineage

    def heir(self, owner):
        return self.lineage.default_heir(owner, self.w.household.members)

    def test_oldest_child_first(self):
        mom, dad, teen, kid, aunt = fakegame.family(self.w)
        self.assertIs(self.heir(mom), teen)

    def test_same_age_children_use_age_progress(self):
        mom = self.w.add_sim(1, 'Mere', Age.ADULT)
        young = self.w.add_sim(2, 'Jeune', Age.CHILD, parents=(1,), age_progress=1.0)
        older = self.w.add_sim(3, 'Aine', Age.CHILD, parents=(1,), age_progress=5.0)
        self.assertIs(self.heir(mom), older)

    def test_child_beats_older_spouse(self):
        mom, dad, teen, kid, aunt = fakegame.family(self.w)
        candidates = [s for s, _ in self.lineage.ranked_heir_candidates(mom, self.w.household.members)]
        self.assertEqual(candidates, [teen, kid, dad, aunt])

    def test_spouse_when_no_child(self):
        mom = self.w.add_sim(1, 'Mere', Age.ADULT, spouse=2)
        dad = self.w.add_sim(2, 'Pere', Age.ADULT, spouse=1)
        self.w.add_sim(5, 'Tante', Age.ELDER)
        self.assertIs(self.heir(mom), dad)

    def test_grandchild_then_sibling_then_parent(self):
        grandma = self.w.add_sim(10, 'Grandmere', Age.ELDER)
        mom = self.w.add_sim(1, 'Mere', Age.ADULT, parents=(10,))
        uncle = self.w.add_sim(2, 'Oncle', Age.ADULT, parents=(10,))
        # La fille de Mère n'est pas dans le foyer, mais son enfant oui.
        self.w.add_sim(3, 'Fille', Age.YOUNGADULT, parents=(1,), in_household=False)
        grandchild = self.w.add_sim(4, 'PetitEnfant', Age.BABY, parents=(3,))
        ranks = {s.first_name: r for s, r in self.lineage.ranked_heir_candidates(mom, self.w.household.members)}
        self.assertEqual(ranks, {'PetitEnfant': 2, 'Oncle': 3, 'Grandmere': 4})
        self.assertIs(self.heir(mom), grandchild)

    def test_other_members_oldest_first(self):
        me = self.w.add_sim(1, 'Moi', Age.ADULT)
        self.w.add_sim(2, 'Coloc', Age.YOUNGADULT)
        elder = self.w.add_sim(3, 'Vieux', Age.ELDER)
        self.assertIs(self.heir(me), elder)

    def test_dead_sims_are_excluded(self):
        mom, dad, teen, kid, aunt = fakegame.family(self.w)
        teen.kill()
        self.assertIs(self.heir(mom), kid)

    def test_no_heir_when_alone(self):
        me = self.w.add_sim(1, 'Seul', Age.ADULT)
        self.assertIsNone(self.heir(me))


if __name__ == '__main__':
    unittest.main()
