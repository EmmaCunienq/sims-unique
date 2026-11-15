"""Commandes de triche (ouvrir la console avec Ctrl+Maj+C)."""
import sims4.commands

from sims_unique import core
from sims_unique.log import log_exception

_LIVE = sims4.commands.CommandType.Live


def _print(connection, lines):
    output = sims4.commands.CheatOutput(connection)
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        output(line)


def _safe(connection, func, *args):
    try:
        _print(connection, func(*args))
    except Exception:
        log_exception(func.__name__)
        _print(connection, 'Erreur, voir SimsUnique.log dans le dossier du mod.')


@sims4.commands.Command('unique.statut', 'unique.status', command_type=_LIVE)
def cmd_status(_connection=None):
    _safe(_connection, core.status_text)


@sims4.commands.Command('unique.heritier', 'unique.heir', command_type=_LIVE)
def cmd_heir(index: int = None, _connection=None):
    if index is None:
        _safe(_connection, core.heir_candidates_text)
    else:
        _safe(_connection, core.set_heir, index)


@sims4.commands.Command('unique.heritier_defaut', 'unique.heir_default', command_type=_LIVE)
def cmd_heir_default(_connection=None):
    _safe(_connection, core.reset_heir)


@sims4.commands.Command('unique.abdiquer', 'unique.abdicate', command_type=_LIVE)
def cmd_abdicate(_connection=None):
    _safe(_connection, core.abdicate)


@sims4.commands.Command('unique.mode', command_type=_LIVE)
def cmd_mode(mode: int = None, _connection=None):
    if mode is None:
        _print(_connection, ['{} : {} - {}'.format(n, core.MODES[n], core.MODE_DESCRIPTIONS[n]) for n in core.MODES]
               + ['Choisir : unique.mode <numéro>'])
    else:
        _safe(_connection, core.set_mode, mode)


@sims4.commands.Command('unique.on', command_type=_LIVE)
def cmd_on(_connection=None):
    _safe(_connection, core.enable)


@sims4.commands.Command('unique.off', command_type=_LIVE)
def cmd_off(_connection=None):
    _safe(_connection, core.disable)


@sims4.commands.Command('unique.aide', 'unique.help', command_type=_LIVE)
def cmd_help(_connection=None):
    _print(_connection, [
        'unique.statut : Sim joué et héritier',
        'unique.heritier : liste des héritiers possibles',
        'unique.heritier <n> : choisir l\'héritier n',
        'unique.heritier_defaut : revenir à l\'héritier par défaut',
        'unique.abdiquer : arrêter de jouer ce Sim et jouer son héritier',
        'unique.mode <1|2|3> : affichage invisible / vision du foyer / état du foyer',
        'unique.off : désactiver le mod pour ce foyer',
        'unique.on : réactiver, avec le Sim actif comme Sim joué',
    ])
