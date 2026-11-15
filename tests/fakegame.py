"""Faux modules du jeu Les Sims 4, pour tester le mod hors du jeu.

`install()` enregistre les modules factices dans sys.modules puis importe le mod.
`reset()` recrée un monde vide avant chaque test.
"""
import functools
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')

world = None
_installed = False
_tmpdir = tempfile.mkdtemp(prefix='sims_unique_tests_')


# --------------------------------------------------------------------------- #
# Objets du jeu
# --------------------------------------------------------------------------- #

class Age:
    BABY, TODDLER, CHILD, TEEN, YOUNGADULT, ADULT, ELDER = 1, 2, 4, 8, 16, 32, 64


class Genealogy:
    def __init__(self, parents):
        self.parents = list(parents)

    def get_parent_sim_ids_gen(self):
        return iter(self.parents)


class DeathTracker:
    def __init__(self):
        self.death_type = None


class SimInfo:
    def __init__(self, sim_id, first_name, age, parents=(), spouse=None, age_progress=0.0):
        self.sim_id = sim_id
        self.first_name = first_name
        self.last_name = 'Test'
        self.age = age
        self.age_progress = age_progress
        self.genealogy = Genealogy(parents)
        self.spouse_sim_id = spouse
        self.death_tracker = DeathTracker()

    def kill(self):
        self.death_tracker.death_type = 1

    def get_sim_instance(self):
        """Sim instancié (créé à la demande), avec son composant d'émotions."""
        if getattr(self, '_sim', None) is None:
            self._sim = Sim(self)
        return self._sim

    def get_is_enabled_in_skewer(self, consider_active_sim=True):
        """Comme le jeu : les bébés sont dans la barre mais jamais cliquables."""
        return self.age != Age.BABY

    def __repr__(self):
        return 'SimInfo({})'.format(self.first_name)


class Sim:
    """Sim instancié (objet sur le terrain)."""
    is_sim = True

    def __init__(self, sim_info):
        self.sim_info = sim_info
        self.id = sim_info.sim_id
        self.Buffs = BuffComponent(self)


class BuffComponent:
    """Comme le jeu : construit et envoie le message d'émotion (MoodUpdate) du Sim."""
    MOOD_HAPPY = 14632

    def __init__(self, owner):
        self.owner = owner

    def _create_mood_update_msg(self):
        return types.SimpleNamespace(sim_id=self.owner.id, mood_key=self.MOOD_HAPPY, mood_intensity=2)

    def _publish_mood_update(self):
        world.mood_ops.append(self._create_mood_update_msg())


class Household:
    def __init__(self, household_id):
        self.id = household_id
        self.members = []

    def sim_info_gen(self):
        return iter(list(self.members))


class World:
    def __init__(self):
        self.all_sims = {}
        self.household = Household(1000)
        self.client = None  # créé par reset()
        self.zone = None
        self.notifications = []
        self.dialogs = []
        self.console = []
        self.alarms = []
        self.managers = {}
        self.cheats_enabled = False
        self.mood_ops = []

    def add_sim(self, sim_id, name, age, parents=(), spouse=None, in_household=True, **kwargs):
        sim_info = SimInfo(sim_id, name, age, parents, spouse, **kwargs)
        self.all_sims[sim_id] = sim_info
        if in_household:
            self.household.members.append(sim_info)
            self.client.selectable_sims.append(sim_info)
        return sim_info

    def remove_from_household(self, sim_info):
        self.household.members.remove(sim_info)
        if sim_info in self.client.selectable_sims:
            self.client.selectable_sims.remove(sim_info)

    def answer_dialog(self, accept):
        dialog = self.dialogs.pop()
        dialog.accepted = accept
        dialog.on_response(dialog)


# --------------------------------------------------------------------------- #
# Modules factices
# --------------------------------------------------------------------------- #

def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    if '.' in name:
        parent_name, child = name.rsplit('.', 1)
        setattr(_module(parent_name), child, module)
    return module


class Client:
    def __init__(self):
        self.active_sim_info = None
        self.selectable_sims = []
        self.switch_calls = []
        self.bar_updates = 0

    def set_active_sim_info(self, sim_info):
        self.switch_calls.append(sim_info)
        self.active_sim_info = sim_info
        return True

    def add_selectable_sim_info(self, sim_info):
        if sim_info not in self.selectable_sims:
            self.selectable_sims.append(sim_info)

    def remove_selectable_sim_info(self, sim_info):
        self.selectable_sims.remove(sim_info)
        # Comme le jeu : retirer le Sim actif fait passer au suivant.
        if self.active_sim_info is sim_info:
            self.active_sim_info = None
            if self.selectable_sims:
                self.set_active_sim_info(self.selectable_sims[0])

    def _get_selector_visual_type(self, sim_info):
        """Comme le jeu : (type visuel du portrait, catégorie de carrière ou None)."""
        return (2 if sim_info.age == Age.BABY else 0), None

    def bar_data(self, sim_info):
        """Données envoyées à la barre pour un Sim (champs utiles de SimPB)."""
        visual_type, career = self._get_selector_visual_type(sim_info)
        return {'is_selectable': sim_info.get_is_enabled_in_skewer(), 'selector_visual_type': visual_type,
                'career_category': career}

    def send_selectable_sims_update(self):
        self.bar_updates += 1

    def bar(self):
        """Prénoms des Sims du bandeau de portraits."""
        return [s.first_name for s in self.selectable_sims]

    def clickable(self):
        """Prénoms des Sims cliquables dans la barre (is_selectable envoyé à l'interface)."""
        return [s.first_name for s in self.selectable_sims if s.get_is_enabled_in_skewer()]


class Zone:
    def __init__(self):
        self.is_zone_running = True
        self.loaded = 0

    def on_loading_screen_animation_finished(self):
        self.loaded += 1


class InstanceManager:
    def __init__(self, type_, types_=None):
        self.TYPE = type_
        self.types = types_ or {}

    def load_data_into_class_instances(self):
        return 'loaded'

    def get(self, instance_id):
        return self.types.get(instance_id)


class TestResult:
    def __init__(self, result, reason=None):
        self.result = result
        self.reason = reason

    def __bool__(self):
        return self.result


TestResult.TRUE = TestResult(True)


DEFAULT = object()


class flexmethod:
    def __init__(self, func):
        self.func = func

    def __get__(self, inst, owner):
        return functools.partial(self.func, owner if inst is None else type(inst), inst)


class ImmediateSuperInteraction:
    def __init__(self, target, context):
        self.target = target
        self.context = context
        self.sim = context.sim

    @classmethod
    def _test(cls, target, context, **kwargs):
        return TestResult.TRUE

    @flexmethod
    def get_name(cls, inst, target=DEFAULT, context=DEFAULT, **kwargs):
        """Comme le jeu : le nom public délègue à _get_name."""
        inst_or_cls = inst if inst is not None else cls
        return inst_or_cls._get_name(target=target, context=context, **kwargs)


class _Notification:
    def __init__(self, owner, text, title):
        self.text = text()
        self.title = title()

    def show_dialog(self):
        world.notifications.append(self.text)


class _OkCancel:
    def __init__(self, owner, text, title, text_ok, text_cancel):
        self.owner = owner
        self.text = text()
        self.accepted = False
        self.on_response = None

    def show_dialog(self, on_response=None):
        self.on_response = on_response
        world.dialogs.append(self)


def _factory(cls):
    class _Factory:
        @staticmethod
        def TunableFactory():
            return types.SimpleNamespace(default=lambda owner, **kwargs: cls(owner, **kwargs))
    return _Factory


class _Alarm:
    def __init__(self, owner, span, callback, repeating):
        self.callback = callback
        self.repeating = repeating
        self.cancelled = False


def _install_stubs():
    services = _module('services')
    services.client_manager = lambda: types.SimpleNamespace(get_first_client=lambda: world.client)
    services.active_household = lambda: world.household
    services.current_zone = lambda: world.zone
    services.sim_info_manager = lambda: types.SimpleNamespace(get=world.all_sims.get)
    services.get_instance_manager = lambda t: world.managers[t]
    services.active_sim_info = lambda: world.client.active_sim_info
    services.get_cheat_service = lambda: types.SimpleNamespace(cheats_enabled=world.cheats_enabled)

    commands = _module('sims4.commands')
    commands.registry = {}

    def command(*names, command_type=None):
        def decorator(func):
            for name in names:
                commands.registry[name] = func
            return func
        return decorator

    commands.Command = command
    commands.CommandType = types.SimpleNamespace(Live='Live')
    commands.CheatOutput = lambda connection: world.console.append

    _module('sims4.localization').LocalizationHelperTuning = types.SimpleNamespace(get_raw_text=lambda text: text)

    resources = _module('sims4.resources')
    resources.Types = types.SimpleNamespace(OBJECT='OBJECT', INTERACTION='INTERACTION', SNIPPET='SNIPPET')
    resources.get_resource_key = lambda instance, type_: (type_, instance)

    _module('sims4.tuning.instance_manager').InstanceManager = InstanceManager
    _module('sims4.utils').flexmethod = flexmethod
    _module('singletons').DEFAULT = DEFAULT
    _module('server.client').Client = Client
    _module('sims.sim_info').SimInfo = SimInfo
    _module('objects.components.buff_component').BuffComponent = BuffComponent
    _module('zone').Zone = Zone
    _module('event_testing.results').TestResult = TestResult
    _module('interactions.base.immediate_interaction').ImmediateSuperInteraction = ImmediateSuperInteraction
    _module('ui.ui_dialog_notification').UiDialogNotification = _factory(_Notification)
    _module('ui.ui_dialog').UiDialogOkCancel = _factory(_OkCancel)

    alarms = _module('alarms')

    def add_alarm_real_time(owner, span, callback, repeating=False):
        alarm = _Alarm(owner, span, callback, repeating)
        world.alarms.append(alarm)
        return alarm

    def cancel_alarm(alarm):
        alarm.cancelled = True

    alarms.add_alarm_real_time = add_alarm_real_time
    alarms.cancel_alarm = cancel_alarm
    _module('clock').interval_in_real_seconds = lambda seconds: seconds


# --------------------------------------------------------------------------- #
# API pour les tests
# --------------------------------------------------------------------------- #

def data_file():
    return os.path.join(_tmpdir, 'SimsUnique_data.json')


def log_file():
    return os.path.join(_tmpdir, 'SimsUnique.log')


def install():
    global _installed, world
    if _installed:
        return
    world = World()
    world.client = Client()
    world.zone = Zone()
    _install_stubs()
    sys.path.insert(0, SRC)
    import sims_unique.log as log_module
    import sims_unique.storage as storage_module
    log_module._LOG_FILE = log_file()
    storage_module._DATA_FILE = data_file()
    import sims_unique_main  # noqa: F401  (charge hooks, commandes, interactions)
    _installed = True


def reset():
    """Nouveau monde vide, sauvegarde effacée."""
    global world
    install()
    world = World()
    world.client = Client()
    world.zone = Zone()
    from sims_unique import core, storage
    storage._cache = None
    for path in (data_file(), log_file()):
        if os.path.exists(path):
            os.remove(path)
    core._allow_switch = False
    core._last_block_message = 0.0
    return world


def family(w):
    """Foyer type : Mère + Père (mariés), Ado et Enfant (leurs enfants), Tante (sans lien)."""
    mom = w.add_sim(1, 'Mere', Age.ADULT, spouse=2)
    dad = w.add_sim(2, 'Pere', Age.ADULT, spouse=1)
    teen = w.add_sim(3, 'Ado', Age.TEEN, parents=(1, 2))
    kid = w.add_sim(4, 'Enfant', Age.CHILD, parents=(1, 2))
    aunt = w.add_sim(5, 'Tante', Age.ELDER)
    w.client.active_sim_info = mom
    return mom, dad, teen, kid, aunt
