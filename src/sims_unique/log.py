"""Journal minimal écrit dans SimsUnique.log, à côté du mod."""
import os
import time
import traceback

from sims_unique.paths import mod_folder

_LOG_FILE = os.path.join(mod_folder(), 'SimsUnique.log')


def log(message):
    try:
        with open(_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write('[{}] {}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), message))
    except Exception:
        pass


def log_exception(context):
    log('ERREUR dans {}:\n{}'.format(context, traceback.format_exc()))
