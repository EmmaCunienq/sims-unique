"""Identifiants des tunings du mod (partagés entre le script et build.py).

Ce module ne doit rien importer du jeu : build.py l'utilise pour générer le .package.
"""


def fnv64(text):
    """Hash FNV-1 64 bits utilisé par Les Sims 4, bit de poids fort forcé (convention des mods)."""
    h = 0xCBF29CE484222325
    for byte in text.lower().encode('utf-8'):
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h ^= byte
    return h | 0x8000000000000000


# Nom du tuning -> nom de la classe Python (dans sims_unique.interactions)
INTERACTIONS = {
    'SimsUnique:Interaction_SetHeir': 'SimsUniqueSetHeirInteraction',
    'SimsUnique:Interaction_Abdicate': 'SimsUniqueAbdicateInteraction',
    'SimsUnique:Interaction_Status': 'SimsUniqueStatusInteraction',
    'SimsUnique:Interaction_DefaultHeir': 'SimsUniqueDefaultHeirInteraction',
    'SimsUnique:Interaction_Enable': 'SimsUniqueEnableInteraction',
    'SimsUnique:Interaction_Disable': 'SimsUniqueDisableInteraction',
    'SimsUnique:Interaction_ModeInvisible': 'SimsUniqueModeInvisibleInteraction',
    'SimsUnique:Interaction_ModeHousehold': 'SimsUniqueModeHouseholdInteraction',
    'SimsUnique:Interaction_ModeHouseholdState': 'SimsUniqueModeHouseholdStateInteraction',
}

INTERACTION_IDS = tuple(fnv64(name) for name in INTERACTIONS)

# Menu « Sims unique » (catégorie du pie menu, visible avec testingcheats) : les réglages.
CATEGORY_NAME = 'SimsUnique:PieMenuCategory'
CATEGORY_ID = fnv64(CATEGORY_NAME)
CATEGORY_INTERACTIONS = (
    'SimsUnique:Interaction_ModeInvisible',
    'SimsUnique:Interaction_ModeHousehold',
    'SimsUnique:Interaction_ModeHouseholdState',
    'SimsUnique:Interaction_Disable',
    'SimsUnique:Interaction_Enable',
)
LOGO_NAME = 'SimsUnique:Logo'
LOGO_ID = fnv64(LOGO_NAME)
STRINGS_NAME = 'SimsUnique:Strings'
CATEGORY_LABEL_KEY = 'SimsUnique:CategoryLabel'
CATEGORY_LABEL = 'Sims unique'

# Tuning de l'objet Sim (object_sim) auquel on ajoute les interactions.
SIM_OBJECT_TUNING_ID = 14965
