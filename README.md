# Sims unique (mod Les Sims 4)

Dans chaque foyer, vous ne jouez **qu'un seul Sim**. Les autres membres vivent leur vie
en autonomie : impossible de les sélectionner ou de leur donner des ordres.
Chaque Sim joué a un **héritier**. Quand il meurt (ou quitte le foyer), on continue avec l'héritier.

> [!WARNING]
> **Mod en cours de test.** Il n'a pas encore été entièrement testé en jeu et **peut causer
> des problèmes sur vos sauvegardes**. Faites une copie de votre dossier
> `Documents\Electronic Arts\Les Sims 4\saves` avant de l'utiliser, et testez-le de
> préférence sur une partie dont vous pouvez vous passer.

## Installation

1. `python build.py --install` (ou copier `build/SimsUnique/` dans `Documents/Electronic Arts/Les Sims 4/Mods/`)
2. En jeu : Options > Options de jeu > Autres > cocher **Activer le contenu personnalisé et les mods**
   et **Mods de script autorisés**, puis relancer le jeu.

## Fonctionnement

- Au premier chargement d'un foyer, le Sim joué est **le Sim actif** à ce moment-là.
- **Seul le Sim joué apparaît dans le bandeau de portraits.** Les autres membres restent dans le
  foyer mais ne sont plus sélectionnables : ils vivent en autonomie, comme des PNJ qui habitent chez vous.
  On peut toujours cliquer sur eux dans le monde (pour interagir, ou les désigner héritier).
- Si le jeu tente de passer à un autre Sim, c'est refusé (un message le rappelle).
- Quand le mod est désactivé (ou que la lignée s'arrête), tout le foyer revient dans le bandeau.
- **Héritier par défaut**, parmi les Sims vivants du foyer :
  1. l'enfant le plus âgé du Sim joué
  2. sinon le conjoint
  3. sinon un petit-enfant, puis un frère/une sœur, puis un parent
  4. sinon le membre du foyer le plus âgé
- L'héritier par défaut est recalculé automatiquement (naissance, mort, départ...).
  Un héritier choisi à la main est conservé tant qu'il reste dans le foyer.
- Si aucun héritier n'est disponible à la mort du Sim joué, la lignée s'arrête et le mod
  se désactive pour ce foyer.

## Modes d'affichage

| Mode | Barre de portraits |
|---|---|
| 1. Invisible (par défaut) | Seul le Sim joué apparaît |
| 2. Vision du foyer | Sim joué en taille normale ; les autres en petit, grisés, sans couleur d'émotion, non cliquables |
| 3. État du foyer | Comme le mode 2, mais avec la couleur d'émotion de chaque Sim |

Changer : **Maj+clic** sur son Sim > Sims unique > « Affichage : … », ou `unique.mode 1|2|3`.
Le réglage est enregistré par foyer.

Les modes 2 et 3 utilisent le mécanisme natif du jeu (`SimInfo.get_is_enabled_in_skewer`,
le même que pour les bébés). L'aspect « petit et grisé » demande en plus
`SimsUnique_UI.package`, une version modifiée de l'interface du mode Vie (voir Développement).

## Menu en jeu

**Actions de jeu**, toujours disponibles (préfixées « Sims unique : ») :

| Où cliquer | Option | Effet |
|---|---|---|
| Sur un autre Sim du foyer | Désigner comme héritier | Il devient l'héritier |
| Sur son propre Sim | Voir la succession | Notification : héritier et ordre de succession |
| Sur son propre Sim | Passer la main à X | Après confirmation, on joue l'héritier |
| Sur son propre Sim | Revenir à l'héritier par défaut (X) | Visible si l'héritier a été choisi à la main |

**Réglages**, regroupés dans le menu **Sims unique** (logo plumbob couronné), visible
uniquement au **Maj+clic** sur son Sim (avec ou sans `testingcheats`) :

| Option | Effet |
|---|---|
| Affichage : Invisible / Vision du foyer / État du foyer | Change le mode d'affichage de la barre |
| Désactiver pour ce foyer | Après confirmation, tous les Sims redeviennent jouables |
| Ne jouer que ce Sim (mod désactivé) | Réactive le mod avec ce Sim |

La catégorie est fournie par `SimsUnique.package` : tuning (0x03E9D964), SimData lue par
l'interface (groupe 0x00E9D967), nom dans une table de textes par langue, logo DDS 46x46
généré par `uimod/logo.py`.

## Commandes (console : Ctrl+Maj+C)

Les mêmes actions existent aussi en commandes :

| Commande | Effet |
|---|---|
| `unique.statut` | Sim joué et héritier |
| `unique.heritier` | Liste numérotée des héritiers possibles |
| `unique.heritier 2` | Choisit l'héritier n°2 de la liste |
| `unique.heritier_defaut` | Revient à l'héritier par défaut |
| `unique.abdiquer` | Arrête de jouer ce Sim et passe à son héritier |
| `unique.off` | Désactive le mod pour ce foyer |
| `unique.on` | Réactive le mod avec le Sim actif comme Sim joué |
| `unique.aide` | Rappel des commandes |

Pour changer de Sim de départ : `unique.off`, sélectionner le Sim voulu, puis `unique.on`.

## Fichiers créés à côté du mod

- `SimsUnique_data.json` : Sim joué et héritier de chaque foyer.
- `SimsUnique.log` : journal (à joindre en cas de bug).

## Développement

- `src/sims_unique_main.py` : point d'entrée chargé par le jeu.
- `src/sims_unique/hooks.py` : injections (`Client.set_active_sim_info`, chargement de zone).
- `src/sims_unique/core.py` : verrou, succession, commandes.
- `src/sims_unique/lineage.py` : liens familiaux et héritier par défaut.
- `src/sims_unique/interactions.py` : options du menu (texte, conditions, action).
- `src/sims_unique/ids.py` : noms et identifiants des tunings, partagés avec `build.py`.

### Package d'interface (`uimod/`)

`build.py` génère `SimsUnique_UI.package` à partir des fichiers **du jeu installé** :
extraction du GFX de l'interface du mode Vie (`5F9A8D994447F9C9` dans `UI.package`),
export du P-code (bytecode AS3 en texte) des classes visées avec JPEXS, modification des
seules méthodes concernées (`uimod/patches.py`), puis remplacement de ces corps de méthode
uniquement (`uimod/abc.py` calcule leur index). Un garde-fou vérifie que tous les autres
corps de méthode sont restés identiques à l'octet près.

> Ne pas recompiler une classe entière depuis l'ActionScript décompilé : le fichier obtenu
> faisait planter le moteur du jeu au chargement d'une partie.

- Prérequis : Java et [JPEXS](https://github.com/jindrapetrik/jpexs-decompiler/releases) décompressé dans `tools/jpexs/`.
  Sinon le package d'interface est simplement ignoré. `python build.py --no-ui` le désactive (et le retire de Mods).
- Après un patch du jeu : relancer `python build.py --install`. Si le code d'origine a changé,
  le build s'arrête sur la ligne repère introuvable au lieu de produire une interface cassée.
- Conflit : tout autre mod qui remplace ce même fichier d'interface (ex. UI Cheats Extension).
- Modifications (`uimod/patches.py`) : un portrait non cliquable (hors bébés) passe en taille mini
  et grisé. En mode 2, le script marque ces Sims dans les données de la barre (champ
  `career_category` via `Client._get_selector_visual_type`) ; la barre masque alors leur fond
  d'émotion et l'expression de leur miniature. Les vraies émotions restent envoyées à toute
  l'interface (panneau de discussion, relations...) : ne jamais modifier les messages d'émotion.

### Release

`python build.py --release` crée `build/SimsUnique_vX.Y.Z.zip` : le dossier `SimsUnique/`
(les 3 fichiers à copier dans Mods) et `LISEZMOI.txt` (mode d'emploi pour les joueurs, généré
depuis `LISEZMOI.txt` avec la version du mod et celle du jeu utilisée pour l'interface).
La version du mod est dans `src/sims_unique/ids.py` (`VERSION`).

L'interface (`SimsUnique_UI.package`) dépend de la version du jeu : refaire une release
après chaque mise à jour du jeu qui touche l'interface du mode Vie.

### Tests

```
python -m unittest discover -s tests -v
```

Les tests tournent hors du jeu : `tests/fakegame.py` imite les modules du jeu utilisés par le mod
(Sims, foyer, client, zone, notifications, dialogues, commandes...).
Ils vérifient la logique du mod, pas l'exactitude des API du vrai jeu : un test en jeu reste nécessaire.

`build.py` génère aussi `SimsUnique.package` (tuning XML des interactions, format DBPF).
Les deux fichiers (`.ts4script` et `.package`) doivent être installés ensemble.

**Python 3.7 est obligatoire pour construire le mod** : le jeu n'exécute que des `.pyc`
compilés en 3.7 et ignore les sources `.py`. Deux possibilités :
- décompresser [python-3.7.9-embed-amd64.zip](https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip)
  dans `tools/python37/` (aucune installation, dossier ignoré par git) ;
- ou installer Python 3.7 (utilisé via `py -3.7`).

Sans Python 3.7, `build.py` s'arrête avec une erreur.
