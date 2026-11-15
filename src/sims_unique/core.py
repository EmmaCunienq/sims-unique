"""Cœur du mod : un seul Sim jouable par foyer, avec succession par héritier."""
import time

import services

from sims_unique import lineage, storage
from sims_unique.log import log, log_exception
from sims_unique.notify import notify, sim_name

# Vrai quand c'est le mod lui-même qui change le Sim actif.
_allow_switch = False
# Anti-spam pour le message « vous ne pouvez pas jouer ce Sim ».
_last_block_message = 0.0


# --------------------------------------------------------------------------- #
# Accès au jeu
# --------------------------------------------------------------------------- #

def get_client():
    try:
        return services.client_manager().get_first_client()
    except Exception:
        return None


def get_household():
    try:
        return services.active_household()
    except Exception:
        return None


def cheats_enabled():
    """Vrai si « testingcheats on » est actif (le menu de réglages n'apparaît qu'alors)."""
    try:
        return bool(services.get_cheat_service().cheats_enabled)
    except Exception:
        return False


def zone_is_running():
    try:
        zone = services.current_zone()
        return zone is not None and zone.is_zone_running
    except Exception:
        return False


def household_members(household):
    return list(household.sim_info_gen())


def find_member(household, sim_id):
    if sim_id is None:
        return None
    for member in household.sim_info_gen():
        if member.sim_id == sim_id:
            return member
    return None


def is_selectable(client, sim_info):
    try:
        return any(s.sim_id == sim_info.sim_id for s in client.selectable_sims)
    except Exception:
        return True


def set_active(sim_info):
    """Rend `sim_info` actif en contournant le verrou du mod."""
    global _allow_switch
    client = get_client()
    if client is None or sim_info is None:
        return False
    if client.active_sim_info is not None and client.active_sim_info.sim_id == sim_info.sim_id:
        return True
    _allow_switch = True
    try:
        return client.set_active_sim_info(sim_info)
    finally:
        _allow_switch = False


# --------------------------------------------------------------------------- #
# Bandeau de portraits : seul le Sim joué est sélectionnable
# --------------------------------------------------------------------------- #

_ADD_METHODS = (('add_selectable_sim_info', False), ('add_selectable_sim_by_id', True))
_REMOVE_METHODS = (('remove_selectable_sim_info', False), ('remove_selectable_sim_by_id', True))


def _call_client(client, methods, sim_info):
    global _allow_switch
    for name, by_id in methods:
        method = getattr(client, name, None)
        if method is None:
            continue
        _allow_switch = True
        try:
            method(sim_info.sim_id if by_id else sim_info)
        finally:
            _allow_switch = False
        return True
    log('Client : aucune des méthodes {} n\'existe'.format([m for m, _ in methods]))
    return False


def show_in_bar(sim_info):
    client = get_client()
    if client is not None and not is_selectable(client, sim_info):
        _call_client(client, _ADD_METHODS, sim_info)


def hide_from_bar(sim_info):
    client = get_client()
    if client is not None and is_selectable(client, sim_info):
        _call_client(client, _REMOVE_METHODS, sim_info)


def _should_hide(household, controlled, sim_info):
    return (sim_info.sim_id != controlled.sim_id
            and find_member(household, sim_info.sim_id) is not None
            and not lineage.is_dead(sim_info))  # un Sim en train de mourir est laissé au jeu


MODE_INVISIBLE, MODE_HOUSEHOLD, MODE_HOUSEHOLD_STATE = 1, 2, 3
MODES = {
    MODE_INVISIBLE: 'Invisible',
    MODE_HOUSEHOLD: 'Vision du foyer',
    MODE_HOUSEHOLD_STATE: 'État du foyer',
}
MODE_DESCRIPTIONS = {
    MODE_INVISIBLE: 'seul votre Sim apparaît dans la barre',
    MODE_HOUSEHOLD: 'le foyer apparaît dans la barre, en petit et grisé',
    MODE_HOUSEHOLD_STATE: 'le foyer apparaît dans la barre, en petit et grisé, avec ses émotions',
}


def get_mode(data):
    mode = data.get('mode', MODE_INVISIBLE) if data else MODE_INVISIBLE
    return mode if mode in MODES else MODE_INVISIBLE


def current_mode():
    household = get_household()
    return get_mode(storage.get_household_data(household.id)) if household is not None else MODE_INVISIBLE


def refresh_bar():
    """Demande au jeu de renvoyer les données de la barre à l'interface."""
    client = get_client()
    method = getattr(client, 'send_selectable_sims_update', None)
    if method is not None:
        try:
            method()
        except Exception:
            log_exception('refresh_bar')


def is_locked_in_bar(sim_info):
    """Vrai si `sim_info` doit apparaître non cliquable dans la barre (modes 2 et 3).

    Appelé très souvent par le jeu : aucune modification d'état ici.
    """
    household = get_household()
    if household is None or sim_info is None:
        return False
    data = storage.get_household_data(household.id)
    if not data.get('enabled', True) or get_mode(data) == MODE_INVISIBLE:
        return False
    controlled_id = data.get('controlled')
    if controlled_id is None or sim_info.sim_id == controlled_id:
        return False
    if find_member(household, sim_info.sim_id) is None:
        return False
    controlled = find_member(household, controlled_id)
    return controlled is not None and not lineage.is_dead(controlled)


# Marqueur placé dans le champ career_category des données de la barre (SimPB) pour les Sims
# dont l'émotion doit être masquée DANS LA BARRE SEULEMENT (mode 2). L'interface modifiée
# (uimod/patches.py) le reconnaît. Les vraies émotions continuent d'être envoyées partout
# (panneau de discussion, relations...). Valeur arbitraire : « SU » + mode 2.
BAR_MOOD_HIDDEN_MARKER = 0x53550002


def hides_mood_in_bar(sim_info):
    """Mode 2 (vision du foyer) : pas d'émotion sur le portrait des Sims verrouillés."""
    return current_mode() == MODE_HOUSEHOLD and is_locked_in_bar(sim_info)


def _apply_bar(household, controlled, refresh=False):
    """Sim joué visible et actif ; les autres membres retirés (mode 1) ou verrouillés (modes 2, 3)."""
    mode = get_mode(storage.get_household_data(household.id))
    show_in_bar(controlled)
    set_active(controlled)
    for member in household_members(household):
        if mode == MODE_INVISIBLE:
            if _should_hide(household, controlled, member):
                hide_from_bar(member)
        else:
            show_in_bar(member)
    if refresh:
        refresh_bar()


def restore_bar(household):
    """Remet tous les membres du foyer dans le bandeau (mod désactivé)."""
    if household is None:
        return
    for member in household_members(household):
        show_in_bar(member)
    refresh_bar()


def on_selectable_added(sim_info):
    """Appelé quand le jeu rajoute un Sim au bandeau : en mode 1, on le retire s'il n'est pas le Sim joué."""
    if _allow_switch or sim_info is None or not zone_is_running():
        return
    household, data, controlled, _ = current_state()
    if controlled is None or get_mode(data) != MODE_INVISIBLE:
        return
    if _should_hide(household, controlled, sim_info):
        hide_from_bar(sim_info)


def set_mode(mode):
    household, data, controlled, _ = current_state()
    if controlled is None:
        return 'Le mod n\'est pas actif pour ce foyer.'
    if mode not in MODES:
        return 'Mode invalide : 1 (invisible), 2 (vision du foyer) ou 3 (état du foyer).'
    data['mode'] = mode
    storage.save()
    _apply_bar(household, controlled, refresh=True)
    text = 'Affichage « {} » : {}.'.format(MODES[mode], MODE_DESCRIPTIONS[mode])
    notify(text)
    return text


# --------------------------------------------------------------------------- #
# État
# --------------------------------------------------------------------------- #

def current_state():
    """Renvoie (household, data, controlled_sim_info, heir_sim_info), état validé.

    Gère automatiquement : première initialisation, mort ou départ du Sim joué,
    héritier disparu, recalcul de l'héritier par défaut.
    """
    household = get_household()
    if household is None:
        return None, None, None, None
    data = storage.get_household_data(household.id)
    if not data.get('enabled', True):
        return household, data, None, None

    changed = False
    controlled = find_member(household, data.get('controlled'))

    # Première fois pour ce foyer : on prend le Sim actif.
    if data.get('controlled') is None:
        client = get_client()
        active = client.active_sim_info if client is not None else None
        if active is None or find_member(household, active.sim_id) is None:
            return household, data, None, None
        _assign_controlled(data, active)
        controlled = active
        changed = True
        notify('Vous jouez désormais uniquement {}.'.format(sim_name(active)))

    # Le Sim joué est mort ou a quitté le foyer -> succession.
    elif controlled is None or (lineage.is_dead(controlled) and not data.get('controlled_was_dead')):
        old_name = sim_name(controlled) if controlled is not None else 'Votre Sim'
        reason = '{} n\'est plus là'.format(old_name)
        if controlled is not None and lineage.is_dead(controlled):
            reason = '{} est mort(e)'.format(old_name)
        controlled = _succession(household, data, reason)
        storage.save()
        if controlled is None:
            return household, data, None, None
        changed = False  # déjà sauvegardé

    heir = _validate_heir(household, data, controlled)
    if heir is not None and data.get('heir') != heir.sim_id:
        data['heir'] = heir.sim_id
        changed = True
    elif heir is None and data.get('heir') is not None:
        data['heir'] = None
        changed = True

    if changed:
        storage.save()
    return household, data, controlled, heir


def _assign_controlled(data, sim_info):
    data['controlled'] = sim_info.sim_id
    data['controlled_was_dead'] = lineage.is_dead(sim_info)
    data['heir'] = None
    data['heir_manual'] = False


def _validate_heir(household, data, controlled):
    members = household_members(household)
    if data.get('heir_manual'):
        heir = find_member(household, data.get('heir'))
        if heir is not None and heir.sim_id != controlled.sim_id and not lineage.is_dead(heir):
            return heir
        if data.get('heir') is not None:
            notify('L\'héritier choisi n\'est plus disponible : retour à l\'héritier par défaut.')
        data['heir_manual'] = False
    return lineage.default_heir(controlled, members)


def _succession(household, data, reason):
    """Passe le contrôle à l'héritier. Renvoie le nouveau Sim joué (ou None)."""
    heir = find_member(household, data.get('heir'))
    if heir is None or lineage.is_dead(heir) or heir.sim_id == data.get('controlled'):
        heir = None
        old = find_member(household, data.get('controlled'))
        if old is not None:
            heir = lineage.default_heir(old, household_members(household))
        else:
            alive = [m for m in household_members(household) if not lineage.is_dead(m)]
            alive.sort(key=lineage.age_key, reverse=True)
            heir = alive[0] if alive else None

    if heir is None:
        data['enabled'] = False
        data['controlled'] = None
        data['heir'] = None
        restore_bar(household)
        notify('{}.\nAucun héritier disponible : la lignée s\'arrête et le mod est désactivé pour ce foyer.'.format(reason))
        return None

    _assign_controlled(data, heir)
    log('Succession -> {} ({})'.format(sim_name(heir), reason))
    _apply_bar(household, heir, refresh=True)
    new_heir = lineage.default_heir(heir, household_members(household))
    data['heir'] = new_heir.sim_id if new_heir is not None else None
    notify('{}.\nVous jouez maintenant {}.\nHéritier : {}.'.format(reason, sim_name(heir), sim_name(new_heir)))
    return heir


# --------------------------------------------------------------------------- #
# Actions (appelées par les commandes)
# --------------------------------------------------------------------------- #

def enforce_active_sim():
    """Remet le Sim joué comme Sim actif et seul Sim du bandeau si nécessaire."""
    if not zone_is_running():
        return
    household, data, controlled, _ = current_state()
    if controlled is None or get_client() is None:
        return
    _apply_bar(household, controlled)


def abdicate():
    household, data, controlled, heir = current_state()
    if controlled is None:
        return 'Le mod n\'est pas actif pour ce foyer.'
    if heir is None:
        return 'Aucun héritier disponible : impossible de passer la main.'
    data['heir'] = heir.sim_id
    new = _succession(household, data, '{} passe la main'.format(sim_name(controlled)))
    storage.save()
    return 'Vous jouez maintenant {}.'.format(sim_name(new))


def set_heir(index):
    household, data, controlled, _ = current_state()
    if controlled is None:
        return 'Le mod n\'est pas actif pour ce foyer.'
    candidates = lineage.ranked_heir_candidates(controlled, household_members(household))
    if index < 1 or index > len(candidates):
        return 'Numéro invalide. Tapez unique.heritier pour voir la liste.'
    heir = candidates[index - 1][0]
    data['heir'] = heir.sim_id
    data['heir_manual'] = index != 1
    storage.save()
    notify('Nouvel héritier de {} : {}.'.format(sim_name(controlled), sim_name(heir)))
    return 'Héritier : {}.'.format(sim_name(heir))


def set_heir_sim(sim_info):
    household, data, controlled, _ = current_state()
    if controlled is None:
        return 'Le mod n\'est pas actif pour ce foyer.'
    if find_member(household, sim_info.sim_id) is None or sim_info.sim_id == controlled.sim_id:
        return '{} ne peut pas être héritier.'.format(sim_name(sim_info))
    default = lineage.default_heir(controlled, household_members(household))
    data['heir'] = sim_info.sim_id
    data['heir_manual'] = default is None or default.sim_id != sim_info.sim_id
    storage.save()
    notify('Nouvel héritier de {} : {}.'.format(sim_name(controlled), sim_name(sim_info)))
    return 'Héritier : {}.'.format(sim_name(sim_info))


def can_be_heir(sim_info):
    """Vrai si `sim_info` peut être désigné héritier (et ne l'est pas déjà)."""
    household, data, controlled, heir = current_state()
    if controlled is None or sim_info is None:
        return False
    if find_member(household, sim_info.sim_id) is None or lineage.is_dead(sim_info):
        return False
    if sim_info.sim_id == controlled.sim_id:
        return False
    return heir is None or heir.sim_id != sim_info.sim_id


def default_heir_if_manual():
    """Héritier par défaut, seulement si l'héritier actuel a été choisi à la main."""
    household, data, controlled, _ = current_state()
    if controlled is None or not data.get('heir_manual'):
        return None
    return lineage.default_heir(controlled, household_members(household))


def is_controlled(sim_info):
    _, _, controlled, _ = current_state()
    return controlled is not None and sim_info is not None and controlled.sim_id == sim_info.sim_id


def is_enabled():
    household, data, _, _ = current_state()
    return household is not None and data.get('enabled', True)


def get_heir():
    return current_state()[3]


def enable_with(sim_info):
    household = get_household()
    if household is None or sim_info is None or find_member(household, sim_info.sim_id) is None:
        return 'Ce Sim ne fait pas partie du foyer.'
    data = storage.get_household_data(household.id)
    data['enabled'] = True
    _assign_controlled(data, sim_info)
    storage.save()
    _apply_bar(household, sim_info, refresh=True)
    _, _, _, heir = current_state()
    notify('Vous jouez désormais uniquement {}.\nHéritier : {}.'.format(sim_name(sim_info), sim_name(heir)))
    return 'Mod activé.'


def reset_heir():
    household, data, controlled, _ = current_state()
    if controlled is None:
        return 'Le mod n\'est pas actif pour ce foyer.'
    data['heir_manual'] = False
    data['heir'] = None
    storage.save()
    _, _, _, heir = current_state()
    notify('Héritier par défaut de {} : {}.'.format(sim_name(controlled), sim_name(heir)))
    return 'Héritier par défaut : {}.'.format(sim_name(heir))


def heir_candidates_text():
    household, data, controlled, heir = current_state()
    if controlled is None:
        return ['Le mod n\'est pas actif pour ce foyer.']
    lines = ['Sim joué : {}'.format(sim_name(controlled))]
    candidates = lineage.ranked_heir_candidates(controlled, household_members(household))
    if not candidates:
        lines.append('Aucun héritier possible.')
    for i, (sim_info, rank) in enumerate(candidates, start=1):
        marker = ' <- héritier' if heir is not None and sim_info.sim_id == heir.sim_id else ''
        default = ' (par défaut)' if i == 1 else ''
        lines.append('{}. {} - {}{}{}'.format(i, sim_name(sim_info), lineage.RANK_LABELS[rank], default, marker))
    lines.append('Choisir : unique.heritier <numéro>')
    return lines


def status_text():
    household, data, controlled, heir = current_state()
    if household is None:
        return ['Aucun foyer actif.']
    if not data.get('enabled', True):
        return ['Mod désactivé pour ce foyer (unique.on pour l\'activer avec le Sim actif).']
    return [
        'Sim joué : {}'.format(sim_name(controlled)),
        'Héritier : {}{}'.format(sim_name(heir), ' (choisi)' if data.get('heir_manual') else ' (par défaut)'),
        'Affichage : {} ({})'.format(MODES[get_mode(data)], get_mode(data)),
    ]


def enable():
    household = get_household()
    client = get_client()
    if household is None or client is None or client.active_sim_info is None:
        return 'Aucun Sim actif.'
    data = storage.get_household_data(household.id)
    data['enabled'] = True
    _assign_controlled(data, client.active_sim_info)
    storage.save()
    current_state()
    _apply_bar(household, client.active_sim_info, refresh=True)
    return 'Mod activé : vous jouez uniquement {}.'.format(sim_name(client.active_sim_info))


def disable():
    household = get_household()
    if household is None:
        return 'Aucun foyer actif.'
    data = storage.get_household_data(household.id)
    data['enabled'] = False
    storage.save()
    restore_bar(household)
    notify('Mod désactivé pour ce foyer : tous les Sims sont jouables.')
    return 'Mod désactivé pour ce foyer : tous les Sims sont jouables.'


# --------------------------------------------------------------------------- #
# Verrou : appelé depuis l'injection de Client.set_active_sim_info
# --------------------------------------------------------------------------- #

def should_block_switch(client, target_sim_info):
    """Vrai si le changement de Sim actif vers `target_sim_info` doit être refusé."""
    global _last_block_message
    if _allow_switch or target_sim_info is None or not zone_is_running():
        return False
    household, data, controlled, _ = current_state()
    if controlled is None:
        return False
    if target_sim_info.sim_id == controlled.sim_id:
        return False
    # Sécurité : si le Sim joué n'est pas sélectionnable (voyage, etc.),
    # on laisse faire le jeu pour éviter tout blocage.
    if not is_selectable(client, controlled):
        return False
    now = time.time()
    if now - _last_block_message > 5:
        _last_block_message = now
        notify('Vous ne pouvez jouer que {}.\n(unique.abdiquer pour passer la main à l\'héritier)'.format(sim_name(controlled)))
    return True


# --------------------------------------------------------------------------- #
# Surveillance périodique (détection de mort, Sim actif changé par le jeu)
# --------------------------------------------------------------------------- #

class _Watcher:
    handle = None


_watcher = _Watcher()


def _tick(_handle):
    try:
        enforce_active_sim()
    except Exception:
        log_exception('core._tick')


def start_watcher():
    try:
        import alarms
        import clock
        if _watcher.handle is not None:
            try:
                alarms.cancel_alarm(_watcher.handle)
            except Exception:
                pass
        _watcher.handle = alarms.add_alarm_real_time(
            _watcher, clock.interval_in_real_seconds(3), _tick, repeating=True)
    except Exception:
        log_exception('core.start_watcher')
