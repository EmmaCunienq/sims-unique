"""Persistance des choix (sim joué, héritier) par foyer, dans un fichier JSON.

Format :
{
  "<household_id>": {
    "enabled": true,
    "controlled": <sim_id>,
    "heir": <sim_id ou null>,
    "heir_manual": false
  }
}
"""
import json
import os

from sims_unique.log import log_exception
from sims_unique.paths import mod_folder

_DATA_FILE = os.path.join(mod_folder(), 'SimsUnique_data.json')
_cache = None


def _load():
    global _cache
    if _cache is None:
        _cache = {}
        try:
            if os.path.exists(_DATA_FILE):
                with open(_DATA_FILE, 'r', encoding='utf-8') as f:
                    _cache = json.load(f)
        except Exception:
            log_exception('storage._load')
            _cache = {}
    return _cache


def save():
    try:
        tmp = _DATA_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(_load(), f, indent=2)
        if os.path.exists(_DATA_FILE):
            os.remove(_DATA_FILE)
        os.rename(tmp, _DATA_FILE)
    except Exception:
        log_exception('storage.save')


def get_household_data(household_id):
    data = _load()
    key = str(household_id)
    if key not in data:
        data[key] = {'enabled': True, 'controlled': None, 'heir': None, 'heir_manual': False, 'mode': 1}
    return data[key]
