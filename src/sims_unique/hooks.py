"""Injections dans le code du jeu."""
import services
import sims4.resources
from server.client import Client
from sims4.tuning.instance_manager import InstanceManager
from zone import Zone

from sims_unique import core, ids
from sims_unique.injector import inject
from sims_unique.log import log, log_exception


@inject(InstanceManager, 'load_data_into_class_instances')
def _load_data_into_class_instances(original, self, *args, **kwargs):
    """Ajoute les interactions du mod au menu de tous les Sims."""
    result = original(self, *args, **kwargs)
    if self.TYPE != sims4.resources.Types.OBJECT:
        return result
    try:
        sim_key = sims4.resources.get_resource_key(ids.SIM_OBJECT_TUNING_ID, sims4.resources.Types.OBJECT)
        sim_tuning = self.types.get(sim_key)
        affordance_manager = services.get_instance_manager(sims4.resources.Types.INTERACTION)
        affordances = []
        for instance_id in ids.INTERACTION_IDS:
            affordance = affordance_manager.get(instance_id)
            if affordance is None:
                log('Interaction introuvable : {} (SimsUnique.package manquant ?)'.format(instance_id))
            else:
                affordances.append(affordance)
        if sim_tuning is not None and affordances:
            sim_tuning._super_affordances = sim_tuning._super_affordances + tuple(affordances)
            log('{} interactions ajoutées au menu des Sims'.format(len(affordances)))
    except Exception:
        log_exception('ajout des interactions')
    return result


@inject(Client, 'set_active_sim_info')
def _set_active_sim_info(original, self, sim_info, *args, **kwargs):
    if core.should_block_switch(self, sim_info):
        return False
    return original(self, sim_info, *args, **kwargs)


def _after_selectable_added(original, self, sim_info, *args, **kwargs):
    result = original(self, sim_info, *args, **kwargs)
    try:
        core.on_selectable_added(sim_info)
    except Exception:
        log_exception('on_selectable_added')
    return result


if hasattr(Client, 'add_selectable_sim_info'):
    inject(Client, 'add_selectable_sim_info')(_after_selectable_added)
else:
    log('Client.add_selectable_sim_info introuvable : le bandeau sera corrigé toutes les 3 secondes')


def _get_is_enabled_in_skewer(original, self, *args, **kwargs):
    """Modes 2 et 3 : les autres membres restent dans la barre mais ne sont pas cliquables.

    Le jeu utilise cette même valeur pour les bébés : il saute ces Sims quand il
    choisit le prochain Sim actif, et l'interface désactive leur portrait.
    """
    result = original(self, *args, **kwargs)
    if result:
        try:
            if core.is_locked_in_bar(self):
                return False
        except Exception:
            log_exception('get_is_enabled_in_skewer')
    return result


try:
    from sims.sim_info import SimInfo
    if hasattr(SimInfo, 'get_is_enabled_in_skewer'):
        inject(SimInfo, 'get_is_enabled_in_skewer')(_get_is_enabled_in_skewer)
    else:
        log('SimInfo.get_is_enabled_in_skewer introuvable : modes 2 et 3 sans verrouillage natif')
except Exception:
    log_exception('injection get_is_enabled_in_skewer')


def _get_selector_visual_type(original, self, sim_info, *args, **kwargs):
    """Mode 2 : marque les Sims verrouillés pour que la barre (et elle seule) masque leur émotion.

    Ne PAS modifier les messages d'émotion eux-mêmes : ils servent à toute l'interface
    (une émotion vide cassait le panneau de discussion).
    """
    result = original(self, sim_info, *args, **kwargs)
    try:
        if core.hides_mood_in_bar(sim_info):
            visual_type, _career_category = result
            return visual_type, core.BAR_MOOD_HIDDEN_MARKER
    except Exception:
        log_exception('_get_selector_visual_type')
    return result


if hasattr(Client, '_get_selector_visual_type'):
    inject(Client, '_get_selector_visual_type')(_get_selector_visual_type)
else:
    log('Client._get_selector_visual_type introuvable : émotions visibles dans la barre en mode 2')


@inject(Zone, 'on_loading_screen_animation_finished')
def _on_loading_screen_animation_finished(original, self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    log('Zone chargée')
    core.enforce_active_sim()
    core.start_watcher()
    return result
