"""Modifications de l'interface du jeu, en P-code (bytecode ActionScript 3 sous forme texte).

Pourquoi le P-code : recompiler une classe entière depuis le code décompilé (JPEXS,
fonction « expérimentale ») produisait un fichier qui faisait planter le moteur du jeu au
chargement. En P-code, on ne remplace que le corps des méthodes visées : tout le reste du
fichier reste octet pour octet celui du jeu.

Chaque patch vise une méthode ('class', 'method' = (genre, nom)) et s'applique à son P-code :
  - insertion : 'anchor' (bloc de lignes) + 'code' (lignes insérées juste après) ;
  - remplacement : 'find' (bloc de lignes) -> 'replace'.
Les lignes sont comparées sans tenir compte de l'indentation. Si un patch du jeu change le
code d'origine, build_ui échoue avec un message clair plutôt que de produire une interface cassée.
Les étiquettes ajoutées commencent par « susu » pour ne jamais entrer en conflit avec celles du jeu.

Barre de portraits (modes 2 et 3 de Sims unique) : un portrait « verrouillé » est un portrait
non cliquable (is_selectable faux, valeur fournie par le mod) qui n'est pas un bébé
(les bébés sont toujours non cliquables dans le jeu de base : on ne change pas leur aspect).
  - verrouillé -> taille mini, miniature grisée (même gris que les Sims indisponibles) ;
  - mode 2 : le script marque ces Sims (career_category = marqueur, voir hooks.py) ; la barre
    masque alors leur fond coloré d'émotion et demande leur miniature sans pose d'émotion.
    Les vraies émotions restent visibles partout ailleurs (panneau de discussion...).
Le Sim joué reste en taille normale. Aucun patch n'appelle le moteur (miniatures, services).
"""

GFX_TYPE = 0x62ECC59A

# Interface du mode Vie : contient la barre de portraits (widgets.Gameplay.SimSelector).
LIVE_HUD_GFX = 0x5F9A8D994447F9C9

PANEL = 'widgets.Gameplay.SimSelector.SelectorPanel'
BUTTON = 'widgets.Gameplay.SimSelector.controls.SimSelectorButton'


def _q(name, ns='PackageNamespace("")'):
    return 'QName({},"{}")'.format(ns, name)


PUBLIC = 'PackageNamespace("")'
BUTTON_NS = 'ProtectedNamespace("widgets.Gameplay.SimSelector.controls:SimSelectorButton")'
COLOR_TRANSFORM = _q('ColorTransform', 'PackageNamespace("flash.geom")')
MOOD_STATIC_DATA = _q('MoodStaticData', 'PackageNamespace("gamedata.Gameplay.shared.definitions")')
MC_THUMBNAIL = _q('mcThumbnail', BUTTON_NS)
M_SIM_PB = _q('mSimPB', BUTTON_NS)

# Marqueur posé par le script (core.BAR_MOOD_HIDDEN_MARKER) dans SimPB.career_category :
# « ne pas montrer l'émotion de ce Sim dans la barre » (mode 2). Seule la barre le lit ;
# les vraies émotions restent envoyées à toute l'interface.
MOOD_HIDDEN_MARKER = str(0x53550002)


def _and_not_hidden(sim_reg, label):
    """Pile : [booléen] -> [booléen ET sim.career_category != marqueur]."""
    return [
        'dup',
        'iffalse ' + label,
        'pop',
    ] + sim_reg.split('\n') + [
        'getproperty ' + _q('career_category'),
        'pushstring "{}"'.format(MOOD_HIDDEN_MARKER),
        'equals',
        'not',
        label + ':',
    ]


def _locked_or(sim_reg, label):
    """Pile : [condition] -> [condition OU (!sim.is_selectable ET !sim.IsBaby)]."""
    return [
        'dup',
        'iftrue ' + label,
        'pop',
        sim_reg,
        'getproperty ' + _q('is_selectable'),
        'not',
        'dup',
        'iffalse ' + label,
        'pop',
        sim_reg,
        'getproperty ' + _q('IsBaby'),
        'not',
        label + ':',
    ]


PATCHES = [
    {
        # Reflow : taille mini si la barre manque de place (d'origine, registre 6) OU si le Sim est verrouillé.
        'gfx': LIVE_HUD_GFX,
        'class': PANEL,
        'method': ('method', 'Reflow'),
        'find': [
            'getproperty ' + _q('SmallSize'),
            'getlocal 6',
            'ifeq ofs0081',
            'getlocal 11',
            'getlocal 6',
            'setproperty ' + _q('SmallSize'),
            'ofs0081:',
        ],
        'replace': [
            'getproperty ' + _q('SmallSize'),
            'getlocal 6',
        ] + _locked_or('getlocal 11\ngetproperty ' + _q('SimInfo'), 'susu_size1') + [
            'ifeq ofs0081',
            'getlocal 11',
            'getlocal 6',
        ] + _locked_or('getlocal 11\ngetproperty ' + _q('SimInfo'), 'susu_size2') + [
            'setproperty ' + _q('SmallSize'),
            'ofs0081:',
        ],
    },
    {
        # RefreshThumbnail : le gris d'origine (Sim indisponible...) s'applique aussi aux Sims verrouillés.
        'gfx': LIVE_HUD_GFX,
        'class': BUTTON,
        'method': ('method', 'RefreshThumbnail'),
        'find': [
            'ofs006c:',
            'iffalse ofs00ae',
        ],
        'replace': ['ofs006c:'] + _locked_or('getlocal1', 'susu_grey') + ['iffalse ofs00ae'],
    },
    {
        # SetMood : fond coloré visible seulement si l'émotion existe (registre 2 = MoodStaticData ou null).
        'gfx': LIVE_HUD_GFX,
        'class': BUTTON,
        'method': ('method', 'SetMood'),
        'anchor': [
            'callproperty ' + _q('GetMoodByKey') + ', 1',
            'coerce ' + MOOD_STATIC_DATA,
            'setlocal2',
        ],
        'code': [
            'getlocal0',
            'getproperty ' + _q('mcMoodBkg'),
            'getlocal2',
            'convert_b',
        ] + _and_not_hidden('getlocal0\ngetproperty ' + M_SIM_PB, 'susu_bkg') + [
            'setproperty ' + _q('visible'),
        ],
    },
    {
        # RefreshThumbnail : miniature sans pose d'émotion pour un Sim marqué (même appel que le jeu,
        # seul l'argument « émotion » vaut null au lieu de mMoodKey).
        'gfx': LIVE_HUD_GFX,
        'class': BUTTON,
        'method': ('method', 'RefreshThumbnail'),
        'find': [
            'getlocal0',
            'getproperty ' + _q('mMoodKey', BUTTON_NS),
            'callpropvoid ' + _q('LoadSimThumbnail') + ', 8',
        ],
        'replace': [
            'getlocal1',
            'getproperty ' + _q('career_category'),
            'pushstring "{}"'.format(MOOD_HIDDEN_MARKER),
            'equals',
            'iftrue susu_nomood',
            'getlocal0',
            'getproperty ' + _q('mMoodKey', BUTTON_NS),
            'jump susu_moodarg',
            'susu_nomood:',
            'pushnull',
            'susu_moodarg:',
            'callpropvoid ' + _q('LoadSimThumbnail') + ', 8',
        ],
    },
    {
        # set SimInfo (données du Sim mises à jour : mode, Sim joué) : fond d'émotion (si émotion connue
        # et non masquée) et gris à jour,
        # SANS redemander la miniature au moteur. Gris = mêmes instructions que RefreshThumbnail.
        'gfx': LIVE_HUD_GFX,
        'class': BUTTON,
        'method': ('setter', 'SimInfo'),
        'anchor': [
            'findproperty ' + _q('enabled'),
            'getlocal1',
            'getproperty ' + _q('is_selectable'),
            'initproperty ' + _q('enabled'),
        ],
        'code': [
            # this.mcMoodBkg.visible = MoodStaticData.GetMoodByKey(param1.mood.mood_key) != null
            'getlocal0',
            'getproperty ' + _q('mcMoodBkg'),
            'getlex ' + MOOD_STATIC_DATA,
            'getlocal1',
            'getproperty ' + _q('mood'),
            'getproperty ' + _q('mood_key'),
            'callproperty ' + _q('GetMoodByKey') + ', 1',
            'convert_b',
        ] + _and_not_hidden('getlocal1', 'susu_bkg') + [
            'setproperty ' + _q('visible'),
            # if(mcThumbnail && !IsBaby) { verrouillé -> gris ; cliquable et disponible -> pas de filtre }
            'getlocal0',
            'getproperty ' + MC_THUMBNAIL,
            'iffalse susu_end',
            'getlocal1',
            'getproperty ' + _q('IsBaby'),
            'iftrue susu_end',
            'getlocal1',
            'getproperty ' + _q('is_selectable'),
            'iffalse susu_grey',
            'getlocal1',
            'getproperty ' + _q('IsSimAvailable'),
            'iffalse susu_end',
            'getlocal0',
            'getproperty ' + MC_THUMBNAIL,
            'getproperty ' + _q('transform'),
            'pushnull',
            'setproperty ' + _q('colorTransform'),
            'jump susu_end',
            'susu_grey:',
            'getlocal0',
            'getproperty ' + MC_THUMBNAIL,
            'getproperty ' + _q('transform'),
            'findpropstrict ' + COLOR_TRANSFORM,
            'constructprop ' + COLOR_TRANSFORM + ', 0',
            'dup',
            'pushint 6710886',
            'setproperty ' + _q('color'),
            'dup',
            'pushdouble 0.3',
            'setproperty ' + _q('blueMultiplier'),
            'dup',
            'pushdouble 0.3',
            'setproperty ' + _q('redMultiplier'),
            'dup',
            'pushdouble 0.3',
            'setproperty ' + _q('greenMultiplier'),
            'setproperty ' + _q('colorTransform'),
            'susu_end:',
        ],
    },
]

# Instructions qui feraient travailler le moteur du jeu (interdites dans nos patches).
ENGINE_CALLS = ('RefreshThumbnail', 'LoadSimThumbnail', 'LoadBabyThumbnail', 'CallGameService',
                'SendUIMessage', 'PostServerCommand')


def class_path(class_name, extension='.pcode'):
    """Chemin du fichier exporté par JPEXS pour une classe."""
    return 'scripts/' + class_name.replace('.', '/') + extension


def _lines(value):
    out = []
    for item in (value if isinstance(value, list) else [value]):
        out.extend(item.split('\n'))
    return out


def new_lines(patch):
    return _lines(patch['replace'] if 'find' in patch else patch['code'])


def _find_block(lines, block):
    stripped = [line.strip() for line in lines]
    target = [line.strip() for line in block]
    return [i for i in range(len(lines) - len(block) + 1) if stripped[i:i + len(block)] == target]


def extract_method(class_pcode, kind, name):
    """P-code d'une méthode (de « method » à « end ; method ») dans le P-code d'une classe exporté par JPEXS."""
    lines = [line.strip() for line in class_pcode.replace('\r', '').split('\n')]
    # Quel que soit l'espace de noms (public, protected...) : « trait <genre> QName(<ns>,"<nom>") ».
    prefix, suffix = 'trait {} QName('.format(kind), ',"{}")'.format(name)
    starts = [i for i, line in enumerate(lines) if line.startswith(prefix) and line.endswith(suffix)]
    if len(starts) != 1:
        raise ValueError('Méthode {} {} trouvée {} fois'.format(kind, name, len(starts)))
    begin = next(i for i in range(starts[0], len(lines)) if lines[i] == 'method')
    end = next(i for i in range(begin, len(lines)) if lines[i] == 'end ; method')
    return '\n'.join(lines[begin:end + 1]) + '\n'


def apply_patch(source, patch):
    """Renvoie le P-code modifié. Lève ValueError si le code d'origine est absent ou ambigu,
    ou si la modification est déjà présente (fichier déjà modifié par un autre mod ?)."""
    lines = source.splitlines()
    new = new_lines(patch)
    block = _lines(patch['find'] if 'find' in patch else patch['anchor'])
    if _find_block(lines, new):
        raise ValueError('{} contient déjà la modification (fichier déjà modifié par un autre mod ?)'.format(
            patch['class']))
    matches = _find_block(lines, block)
    if len(matches) != 1:
        raise ValueError('Code d\'origine trouvé {} fois dans {} : « {} » (le jeu a peut-être été mis à jour)'.format(
            len(matches), patch['class'], block[0].strip()))
    i = matches[0]
    if 'find' in patch:
        lines[i:i + len(block)] = new
    else:
        lines[i + len(block):i + len(block)] = new
    return '\n'.join(lines) + '\n'
