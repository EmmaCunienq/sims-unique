"""Construit SimsUnique.ts4script + SimsUnique.package et, avec --install, les copie dans Mods.

Usage :
    python build.py            # crée build/SimsUnique/SimsUnique.ts4script
    python build.py --install  # idem + copie dans Documents/Electronic Arts/<Les Sims 4>/Mods
    python build.py --no-ui    # sans le package d'interface (barre de portraits modifiée)

Les Sims 4 n'exécute que des fichiers .pyc compilés avec Python 3.7 : une archive contenant
seulement des sources .py est ignorée par le jeu. build.py cherche Python 3.7 :
  1. tools/python37/python.exe  (version « embeddable » de python.org décompressée là)
  2. le lanceur Windows `py -3.7` (Python 3.7 installé normalement)
"""
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from uimod import build_ui, dbpf, menu_resources  # noqa: E402
SRC = os.path.join(ROOT, 'src')
OUT_DIR = os.path.join(ROOT, 'build', 'SimsUnique')
OUT_FILE = os.path.join(OUT_DIR, 'SimsUnique.ts4script')
LOCAL_PY37 = os.path.join(ROOT, 'tools', 'python37', 'python.exe')
PY37_MAGIC = (3394).to_bytes(2, 'little') + b'\r\n'  # en-tête des .pyc Python 3.7


class BuildError(Exception):
    pass


def python37_commands():
    if os.path.exists(LOCAL_PY37):
        yield [LOCAL_PY37]
    yield ['py', '-3.7']


def compile_with_py37(staging):
    """Compile en .pyc 3.7 à côté des sources. Renvoie la commande utilisée, ou None."""
    for command in python37_commands():
        try:
            subprocess.run(command + ['-m', 'compileall', '-b', '-q', staging],
                           check=True, capture_output=True)
            return command
        except Exception:
            continue
    return None


def build(allow_source=False):
    """Construit le .ts4script. Sans Python 3.7, échoue (sauf allow_source, pour les tests)."""
    staging = tempfile.mkdtemp(prefix='sims_unique_')
    try:
        shutil.copytree(SRC, os.path.join(staging, 'src'), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        staging_src = os.path.join(staging, 'src')
        command = compile_with_py37(staging_src)
        if command is None and not allow_source:
            raise BuildError(
                'Python 3.7 introuvable : le jeu ignore les scripts non compilés.\n'
                'Décompressez python-3.7.9-embed-amd64.zip (python.org) dans tools/python37/,\n'
                'ou installez Python 3.7, puis relancez build.py.')
        wanted_ext = '.pyc' if command else '.py'
        print('Compilation Python 3.7 :', ' '.join(command) if command else 'NON (sources .py, inutilisable en jeu)')
        if command:
            for folder, _, files in os.walk(staging_src):
                for name in files:
                    if name.endswith('.pyc'):
                        with open(os.path.join(folder, name), 'rb') as f:
                            if f.read(4) != PY37_MAGIC:
                                raise BuildError('{} n\'est pas un .pyc Python 3.7'.format(name))

        os.makedirs(OUT_DIR, exist_ok=True)
        if os.path.exists(OUT_FILE):
            os.remove(OUT_FILE)
        with zipfile.ZipFile(OUT_FILE, 'w', zipfile.ZIP_STORED) as zf:
            for folder, _, files in os.walk(staging_src):
                for name in files:
                    if name.endswith(wanted_ext):
                        full = os.path.join(folder, name)
                        zf.write(full, os.path.relpath(full, staging_src))
        print('Créé :', OUT_FILE)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


PACKAGE_FILE = os.path.join(OUT_DIR, 'SimsUnique.package')
INTERACTION_TYPE = 0xE882D22F  # type de ressource "Interaction tuning"

TUNING_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<I c="{cls}" i="interaction" m="sims_unique.interactions" n="{name}" s="{instance}">
  <V n="_saveable" t="disabled" />
  <T n="allow_autonomous">False</T>
  <T n="allow_user_directed">True</T>
  <L n="interaction_category_tags">
    <E>Interaction_All</E>
  </L>{category}
</I>
'''


def tuning_resources():
    sys.path.insert(0, os.path.join(SRC, 'sims_unique'))
    import ids
    resources = []
    for name, cls in ids.INTERACTIONS.items():
        instance = ids.fnv64(name)
        category = ''
        if name in ids.CATEGORY_INTERACTIONS:
            category = '\n  <T n="category">{}<!--{}--></T>'.format(ids.CATEGORY_ID, ids.CATEGORY_NAME)
        xml = TUNING_TEMPLATE.format(cls=cls, name=name, instance=instance, category=category)
        resources.append(((INTERACTION_TYPE, 0, instance), xml.encode('utf-8')))
    return resources + menu_resources.resources()


def write_dbpf(path, resources):
    """Écrit un package DBPF 2.1 non compressé. resources : [((type, group, instance), bytes)]"""
    dbpf.write_package(path, resources)


def build_package():
    resources = tuning_resources()
    write_dbpf(PACKAGE_FILE, resources)
    print('Créé :', PACKAGE_FILE, '({} ressources : interactions, menu Sims unique, logo, textes)'.format(len(resources)))


UI_PACKAGE_FILE = os.path.join(OUT_DIR, 'SimsUnique_UI.package')


def build_ui_package():
    """Package d'interface (barre de portraits). Facultatif : ignoré si les outils manquent."""
    try:
        instances = build_ui.build_ui(UI_PACKAGE_FILE)
    except build_ui.UIBuildError as error:
        if os.path.exists(UI_PACKAGE_FILE):
            os.remove(UI_PACKAGE_FILE)
        print('Interface NON construite :', error)
        return False
    print('Créé :', UI_PACKAGE_FILE, '(interface remplacée : {})'.format(
        ', '.join('{:016X}'.format(i) for i in instances)))
    return True


def find_mods_folder():
    home = os.path.expanduser('~')
    documents = [os.path.join(home, 'Documents'), os.path.join(home, 'OneDrive', 'Documents')]
    for docs in documents:
        ea = os.path.join(docs, 'Electronic Arts')
        if not os.path.isdir(ea):
            continue
        # Le nom varie selon la langue (et contient des espaces insécables en français).
        for game in sorted(os.listdir(ea)):
            mods = os.path.join(ea, game, 'Mods')
            if 'sims' in game.lower() and '4' in game and os.path.isdir(mods):
                return mods
    return None


def is_locked(path):
    try:
        with open(path, 'r+b'):
            return False
    except PermissionError:
        return True


def install():
    mods = find_mods_folder()
    if mods is None:
        print('Dossier Mods introuvable : copiez build/SimsUnique à la main dans Mods.')
        return
    target = os.path.join(mods, 'SimsUnique')
    os.makedirs(target, exist_ok=True)
    sources = [OUT_FILE, PACKAGE_FILE]
    installed_ui = os.path.join(target, os.path.basename(UI_PACKAGE_FILE))
    if os.path.exists(UI_PACKAGE_FILE):
        sources.append(UI_PACKAGE_FILE)
    elif os.path.exists(installed_ui):
        os.remove(installed_ui)  # --no-ui ou échec : on ne laisse pas une ancienne interface
        print('Interface retirée de :', target)
    to_copy = []
    for source in sources:
        destination = os.path.join(target, os.path.basename(source))
        if os.path.exists(destination) and filecmp.cmp(source, destination, shallow=False):
            continue  # identique : rien à copier
        to_copy.append((source, destination))
    # Vérifier tous les verrous AVANT de copier, pour ne jamais installer à moitié.
    locked = [os.path.basename(d) for _, d in to_copy if os.path.exists(d) and is_locked(d)]
    if locked:
        print('ERREUR : {} verrouillé(s) par le jeu. Rien n\'a été installé : fermez le jeu puis relancez.'.format(
            ', '.join(locked)))
        sys.exit(1)
    for source, destination in to_copy:
        shutil.copy2(source, destination)
    print('Installé dans :', target)
    print('Relancez le jeu pour charger la nouvelle version.')


if __name__ == '__main__':
    try:
        build()
    except BuildError as error:
        print('ERREUR :', error)
        sys.exit(1)
    build_package()
    if '--no-ui' in sys.argv:
        if os.path.exists(UI_PACKAGE_FILE):
            os.remove(UI_PACKAGE_FILE)
        print('Interface : ignorée (--no-ui)')
    else:
        build_ui_package()
    if '--install' in sys.argv:
        install()
