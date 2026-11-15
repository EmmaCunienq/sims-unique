"""Construit SimsUnique_UI.package à partir des fichiers d'interface du jeu installé.

Étapes : extraire le GFX du jeu -> décompiler les classes visées (JPEXS) -> appliquer
les patches -> recompiler (JPEXS) -> écrire un package qui remplace le GFX d'origine.

Prérequis : le jeu installé, Java, et JPEXS décompressé dans tools/jpexs/.
"""
import glob
import os
import shutil
import subprocess
import tempfile

from uimod import abc, dbpf, patches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JPEXS_JAR = os.path.join(ROOT, 'tools', 'jpexs', 'ffdec.jar')
GAME_DIR_CANDIDATES = [
    os.environ.get('SIMS4_GAME_DIR', ''),
    r'C:\Program Files\EA Games\The Sims 4',
    r'C:\Program Files (x86)\Origin Games\The Sims 4',
    r'C:\Program Files (x86)\Steam\steamapps\common\The Sims 4',
    r'C:\Program Files\Steam\steamapps\common\The Sims 4',
]


class UIBuildError(Exception):
    pass


def find_game_dir():
    for candidate in GAME_DIR_CANDIDATES:
        if candidate and os.path.isfile(os.path.join(candidate, 'Data', 'Client', 'UI.package')):
            return candidate
    return None


def game_packages(game_dir):
    """Packages du jeu contenant l'interface ; les derniers (patchs) l'emportent."""
    yield os.path.join(game_dir, 'Data', 'Client', 'UI.package')
    for pattern in (os.path.join(game_dir, 'Delta', '**', '*.package'),
                    os.path.join(game_dir, 'Data', 'Client', '*Delta*.package')):
        for path in sorted(glob.glob(pattern, recursive=True)):
            yield path


def extract_gfx(game_dir, instance):
    found = None
    for package in game_packages(game_dir):
        for entry in dbpf.read_index(package):
            if entry['type'] == patches.GFX_TYPE and entry['instance'] == instance:
                found = entry
    if found is None:
        raise UIBuildError('Fichier d\'interface {:016X} introuvable dans le jeu.'.format(instance))
    return dbpf.read_resource(found), found


def run_jpexs(*args):
    result = subprocess.run(['java', '-jar', JPEXS_JAR] + list(args), capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise UIBuildError('JPEXS a échoué :\n' + (result.stdout + result.stderr)[-2000:])
    return result.stdout


def patch_gfx(gfx_bytes, gfx_patches, work_dir):
    """Applique les patches P-code à un GFX et renvoie le GFX modifié.

    Seuls les corps des méthodes visées sont remplacés (JPEXS -replace ... <index du corps>) ;
    on vérifie ensuite que tous les autres corps de méthode sont restés identiques.
    """
    os.makedirs(work_dir, exist_ok=True)
    original = os.path.join(work_dir, 'original.gfx')
    with open(original, 'wb') as f:
        f.write(gfx_bytes)
    classes = sorted({p['class'] for p in gfx_patches})
    exported = os.path.join(work_dir, 'pcode')
    run_jpexs('-format', 'script:pcode', '-selectclass', ','.join(classes), '-export', 'script', exported, original)

    replace_args = []
    patched_bodies = set()
    methods = []
    for patch in gfx_patches:
        key = (patch['class'],) + tuple(patch['method'])
        if key not in methods:
            methods.append(key)
    for class_name, kind, name in methods:
        pcode_path = os.path.join(exported, *patches.class_path(class_name).split('/'))
        if not os.path.exists(pcode_path):
            raise UIBuildError("Classe {} absente du fichier d'interface.".format(class_name))
        with open(pcode_path, encoding='utf-8') as f:
            class_pcode = f.read()
        try:
            source = patches.extract_method(class_pcode, kind, name)
            for patch in gfx_patches:
                if (patch['class'],) + tuple(patch['method']) == (class_name, kind, name):
                    source = patches.apply_patch(source, patch)
            body = abc.body_index(gfx_bytes, class_name, name, kind)
        except ValueError as error:
            raise UIBuildError(str(error))
        method_path = os.path.join(work_dir, '{}.{}.{}.pcode'.format(class_name, kind, name))
        with open(method_path, 'w', encoding='utf-8') as f:
            f.write(source)
        replace_args += [class_name, method_path, str(body)]
        patched_bodies.add(body)

    output = os.path.join(work_dir, 'patched.gfx')
    run_jpexs('-replace', original, output, *replace_args)
    with open(output, 'rb') as f:
        patched = f.read()
    check_only_bodies_changed(gfx_bytes, patched, patched_bodies)
    return patched


def check_only_bodies_changed(original, patched, allowed):
    """Garde-fou : seuls les corps de méthode prévus ont changé, les autres sont identiques."""
    before = [abc.parse(block) for block in abc.abc_blocks(original)]
    after = [abc.parse(block) for block in abc.abc_blocks(patched)]
    if len(before) != len(after):
        raise UIBuildError('Nombre de blocs ABC modifié.')
    for a, b in zip(before, after):
        if len(a['codes']) != len(b['codes']) or a['pools']['methods'] != b['pools']['methods']                 or a['pools']['classes'] != b['pools']['classes']:
            raise UIBuildError('Structure du bytecode modifiée (méthodes ou classes).')
        changed = {i for i, (x, y) in enumerate(zip(a['codes'], b['codes'])) if x[2:] != y[2:] or x[0] != y[0]}
        unexpected = changed - set(allowed)
        if unexpected:
            raise UIBuildError('Corps de méthode modifiés sans raison : {}'.format(sorted(unexpected)[:10]))
        missing = set(allowed) - changed
        if missing:
            raise UIBuildError('Patch sans effet sur les corps : {}'.format(sorted(missing)))


def build_ui(package_path, game_dir=None):
    """Construit le package d'interface. Renvoie la liste des instances remplacées."""
    game_dir = game_dir or find_game_dir()
    if game_dir is None:
        raise UIBuildError('Jeu introuvable : définissez la variable SIMS4_GAME_DIR.')
    if not os.path.exists(JPEXS_JAR):
        raise UIBuildError('JPEXS introuvable : décompressez-le dans tools/jpexs/.')
    if shutil.which('java') is None:
        raise UIBuildError('Java introuvable.')

    resources = []
    work_dir = tempfile.mkdtemp(prefix='sims_unique_ui_')
    try:
        for instance in sorted({p['gfx'] for p in patches.PATCHES}):
            gfx_bytes, entry = extract_gfx(game_dir, instance)
            gfx_patches = [p for p in patches.PATCHES if p['gfx'] == instance]
            patched = patch_gfx(gfx_bytes, gfx_patches, os.path.join(work_dir, '{:016X}'.format(instance)))
            resources.append(((patches.GFX_TYPE, entry['group'], instance), patched))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    dbpf.write_package(package_path, resources)
    return [instance for (_, _, instance), _ in resources]
