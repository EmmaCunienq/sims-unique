"""Remplacement (injection) de méthodes du jeu, technique standard des script mods."""
import functools

from sims_unique.log import log_exception


def inject(target_object, target_function_name):
    """Décorateur : la nouvelle fonction reçoit l'originale en premier argument."""

    def _decorator(new_function):
        original = getattr(target_object, target_function_name)

        @functools.wraps(original)
        def _wrapped(*args, **kwargs):
            try:
                return new_function(original, *args, **kwargs)
            except Exception:
                log_exception('{}.{}'.format(getattr(target_object, '__name__', target_object), target_function_name))
                return original(*args, **kwargs)

        setattr(target_object, target_function_name, _wrapped)
        return new_function

    return _decorator
