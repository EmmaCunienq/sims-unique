"""Localisation du dossier du mod (là où sont écrits la sauvegarde JSON et le log)."""
import os


def mod_folder():
    """Renvoie le dossier qui contient le .ts4script (ou le dossier Scripts en dev)."""
    path = os.path.abspath(__file__)
    current = path
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        if current.lower().endswith('.ts4script'):
            return parent
        current = parent
    # Mode développement (.py en vrac) : remonter au-dessus du package.
    return os.path.dirname(os.path.dirname(path))
