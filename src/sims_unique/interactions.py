"""Interactions du menu contextuel (pie menu).

Les tunings XML (générés par build.py dans SimsUnique.package) pointent vers ces classes.
Les noms affichés et les conditions d'affichage sont gérés ici, en Python.
"""
from event_testing.results import TestResult
from interactions.base.immediate_interaction import ImmediateSuperInteraction
from sims4.localization import LocalizationHelperTuning
from sims4.utils import flexmethod
from singletons import DEFAULT

from sims_unique import core
from sims_unique.log import log_exception
from sims_unique.notify import confirm, notify, sim_name

PREFIX = 'Sims unique : '


def _sim_info_of(obj):
    if obj is None or obj is DEFAULT:
        return None
    if getattr(obj, 'is_sim', False):
        return getattr(obj, 'sim_info', None)
    return None


class _SimsUniqueInteraction(ImmediateSuperInteraction):
    """Base : nom en texte brut, test et action délégués aux sous-classes."""

    on_self = True  # True : clic sur son propre Sim ; False : clic sur un autre Sim
    # True : réglage rangé dans le menu « Sims unique », visible seulement au Maj+clic sur le Sim
    # (avec ou sans testingcheats).
    in_settings_menu = False

    @classmethod
    def label(cls, actor, target):
        raise NotImplementedError

    @classmethod
    def visible(cls, actor, target):
        raise NotImplementedError

    def run(self, actor, target):
        raise NotImplementedError

    @flexmethod
    def _get_name(cls, inst, target=DEFAULT, context=DEFAULT, **kwargs):
        inst_or_cls = inst if inst is not None else cls
        try:
            if inst is not None:
                target = inst.target
                context = inst.context
            actor = _sim_info_of(context.sim) if context is not DEFAULT and context is not None else None
            text = inst_or_cls.label(actor, _sim_info_of(target))
            if not inst_or_cls.in_settings_menu:
                text = PREFIX + text  # hors du menu Sims unique : on rappelle le nom du mod
        except Exception:
            log_exception('{}._get_name'.format(cls.__name__))
            text = PREFIX.rstrip(' :')
        return LocalizationHelperTuning.get_raw_text(text)

    @classmethod
    def _test(cls, target, context, **kwargs):
        try:
            actor = _sim_info_of(context.sim)
            target_info = _sim_info_of(target)
            if actor is None or target_info is None:
                return TestResult(False, 'Sims unique : cible non Sim')
            if cls.on_self != (actor.sim_id == target_info.sim_id):
                return TestResult(False, 'Sims unique : mauvaise cible')
            if cls.in_settings_menu and not getattr(context, 'shift_held', False):
                return TestResult(False, 'Sims unique : réglages au Maj+clic')
            if not cls.visible(actor, target_info):
                return TestResult(False, 'Sims unique : indisponible')
        except Exception:
            log_exception('{}._test'.format(cls.__name__))
            return TestResult(False, 'Sims unique : erreur')
        return super()._test(target, context, **kwargs)

    def _run_interaction_gen(self, timeline):
        try:
            self.run(_sim_info_of(self.sim), _sim_info_of(self.target))
        except Exception:
            log_exception('{}.run'.format(type(self).__name__))
        return True
        yield  # fait de cette méthode un générateur, comme attendu par le jeu


# --------------------------------------------------------------------------- #
# Clic sur un autre Sim du foyer
# --------------------------------------------------------------------------- #

class SimsUniqueSetHeirInteraction(_SimsUniqueInteraction):
    on_self = False

    @classmethod
    def label(cls, actor, target):
        return 'Désigner comme héritier'

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor) and core.can_be_heir(target)

    def run(self, actor, target):
        core.set_heir_sim(target)


# --------------------------------------------------------------------------- #
# Clic sur son propre Sim
# --------------------------------------------------------------------------- #

class SimsUniqueStatusInteraction(_SimsUniqueInteraction):

    @classmethod
    def label(cls, actor, target):
        return 'Voir la succession'

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor)

    def run(self, actor, target):
        lines = core.heir_candidates_text()
        # Retirer la ligne d'aide console, inutile dans la notification.
        lines = [line for line in lines if not line.startswith('Choisir :')]
        lines.append('Cliquez sur un Sim du foyer > Sims unique : Désigner comme héritier.')
        notify('\n'.join(lines))


class SimsUniqueAbdicateInteraction(_SimsUniqueInteraction):

    @classmethod
    def label(cls, actor, target):
        return 'Passer la main à {}'.format(sim_name(core.get_heir()))

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor) and core.get_heir() is not None

    def run(self, actor, target):
        heir = core.get_heir()
        if heir is None:
            return
        confirm('Arrêter définitivement de jouer {} et continuer avec {} ?'.format(sim_name(actor), sim_name(heir)),
                core.abdicate, owner=actor)


class SimsUniqueDefaultHeirInteraction(_SimsUniqueInteraction):

    @classmethod
    def label(cls, actor, target):
        return 'Revenir à l\'héritier par défaut ({})'.format(sim_name(core.default_heir_if_manual()))

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor) and core.default_heir_if_manual() is not None

    def run(self, actor, target):
        core.reset_heir()


class SimsUniqueDisableInteraction(_SimsUniqueInteraction):
    in_settings_menu = True

    @classmethod
    def label(cls, actor, target):
        return 'Désactiver pour ce foyer'

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor)

    def run(self, actor, target):
        confirm('Désactiver Sims unique pour ce foyer ? Tous les Sims redeviendront jouables.',
                core.disable, owner=actor)


class _SimsUniqueModeInteraction(_SimsUniqueInteraction):
    """Change le mode d'affichage de la barre ; seuls les modes autres que l'actuel sont proposés."""
    mode = None
    in_settings_menu = True

    @classmethod
    def label(cls, actor, target):
        return 'Affichage : {}'.format(core.MODES[cls.mode])

    @classmethod
    def visible(cls, actor, target):
        return core.is_controlled(actor) and core.current_mode() != cls.mode

    def run(self, actor, target):
        core.set_mode(self.mode)


class SimsUniqueModeInvisibleInteraction(_SimsUniqueModeInteraction):
    mode = core.MODE_INVISIBLE


class SimsUniqueModeHouseholdInteraction(_SimsUniqueModeInteraction):
    mode = core.MODE_HOUSEHOLD


class SimsUniqueModeHouseholdStateInteraction(_SimsUniqueModeInteraction):
    mode = core.MODE_HOUSEHOLD_STATE


class SimsUniqueEnableInteraction(_SimsUniqueInteraction):
    in_settings_menu = True

    @classmethod
    def label(cls, actor, target):
        return 'Ne jouer que ce Sim'

    @classmethod
    def visible(cls, actor, target):
        household = core.get_household()
        return (household is not None and core.find_member(household, actor.sim_id) is not None
                and not core.is_enabled())

    def run(self, actor, target):
        confirm('Ne plus jouer que {} dans ce foyer ?'.format(sim_name(actor)),
                lambda: core.enable_with(actor), owner=actor)
