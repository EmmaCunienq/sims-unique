"""Liens familiaux et choix de l'héritier par défaut.

Ordre de priorité pour l'héritier par défaut (parmi les Sims vivants du foyer) :
  1. enfants du Sim joué (le plus âgé d'abord)
  2. conjoint
  3. petits-enfants
  4. frères et sœurs
  5. parents
  6. autres membres du foyer (le plus âgé d'abord)
"""
from sims_unique.log import log_exception

RANK_LABELS = {
    0: 'enfant',
    1: 'conjoint',
    2: 'petit-enfant',
    3: 'frère/sœur',
    4: 'parent',
    5: 'membre du foyer',
}


def is_dead(sim_info):
    try:
        tracker = getattr(sim_info, 'death_tracker', None)
        if tracker is not None and getattr(tracker, 'death_type', None):
            return True
    except Exception:
        log_exception('lineage.is_dead')
    return False


def _find_sim_info(sim_id):
    try:
        import services
        return services.sim_info_manager().get(sim_id)
    except Exception:
        return None


def parent_ids(sim_info):
    """Identifiants des parents biologiques/adoptifs connus du Sim."""
    ids = set()
    genealogy = getattr(sim_info, 'genealogy', None)
    if genealogy is None:
        return ids
    try:
        ids.update(genealogy.get_parent_sim_ids_gen())
    except Exception:
        try:
            from sims.genealogy_tracker import FamilyRelationshipIndex
            for relation in (FamilyRelationshipIndex.MOTHER, FamilyRelationshipIndex.FATHER):
                parent_id = genealogy.get_relation(relation)
                if parent_id:
                    ids.add(parent_id)
        except Exception:
            log_exception('lineage.parent_ids')
    ids.discard(0)
    ids.discard(None)
    return ids


def age_key(sim_info):
    """Clé de tri : plus la valeur est grande, plus le Sim est âgé."""
    try:
        age = int(sim_info.age)
    except Exception:
        age = 0
    try:
        progress = float(getattr(sim_info, 'age_progress', 0) or 0)
    except Exception:
        progress = 0.0
    return age, progress


def relation_rank(owner, other, members_by_id):
    """Rang de proximité familiale de `other` par rapport à `owner` (0 = le plus proche)."""
    owner_id = owner.sim_id
    other_parents = parent_ids(other)
    if owner_id in other_parents:
        return 0
    if getattr(owner, 'spouse_sim_id', None) == other.sim_id:
        return 1
    for parent_id in other_parents:
        parent = members_by_id.get(parent_id) or _find_sim_info(parent_id)
        parents_of_parent = parent_ids(parent) if parent is not None else set()
        if owner_id in parents_of_parent:
            return 2
    owner_parents = parent_ids(owner)
    if owner_parents and owner_parents & other_parents:
        return 3
    if other.sim_id in owner_parents:
        return 4
    return 5


def ranked_heir_candidates(owner, household_members):
    """Liste triée de (sim_info, rang) : le premier est l'héritier par défaut."""
    members_by_id = {m.sim_id: m for m in household_members}
    candidates = []
    for member in household_members:
        if member.sim_id == owner.sim_id or is_dead(member):
            continue
        rank = relation_rank(owner, member, members_by_id)
        candidates.append((member, rank))
    candidates.sort(key=lambda c: (c[1], tuple(-v for v in age_key(c[0]))))
    return candidates


def default_heir(owner, household_members):
    candidates = ranked_heir_candidates(owner, household_members)
    return candidates[0][0] if candidates else None
