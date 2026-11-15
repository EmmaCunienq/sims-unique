"""Point d'entrée chargé par le jeu (module à la racine du .ts4script)."""
from sims_unique.ids import VERSION
from sims_unique.log import log, log_exception

try:
    import sims_unique.hooks  # noqa: F401
    import sims_unique.commands  # noqa: F401
    import sims_unique.interactions  # noqa: F401
    log('Sims unique {} chargé'.format(VERSION))
except Exception:
    log_exception('chargement du mod')
