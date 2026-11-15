"""Notifications en jeu (bulle en haut à droite)."""
from sims_unique.log import log, log_exception

TITLE = 'Sims unique'


def notify(text, title=TITLE):
    log('Notification: ' + text.replace('\n', ' | '))
    try:
        from sims4.localization import LocalizationHelperTuning
        from ui.ui_dialog_notification import UiDialogNotification

        notification = UiDialogNotification.TunableFactory().default(
            None,
            text=lambda *_, **__: LocalizationHelperTuning.get_raw_text(text),
            title=lambda *_, **__: LocalizationHelperTuning.get_raw_text(title),
        )
        notification.show_dialog()
    except Exception:
        log_exception('notify')


def confirm(text, on_ok, owner=None, title=TITLE, ok_text='Oui', cancel_text='Annuler'):
    """Boîte de dialogue Oui / Annuler ; `on_ok()` est appelé si le joueur accepte."""
    try:
        import services
        from sims4.localization import LocalizationHelperTuning
        from ui.ui_dialog import UiDialogOkCancel

        def raw(value):
            return lambda *_, **__: LocalizationHelperTuning.get_raw_text(value)

        if owner is None:
            owner = services.active_sim_info()
        dialog = UiDialogOkCancel.TunableFactory().default(
            owner, text=raw(text), title=raw(title), text_ok=raw(ok_text), text_cancel=raw(cancel_text))

        def _on_response(d):
            try:
                if d.accepted:
                    on_ok()
            except Exception:
                log_exception('confirm.on_response')

        dialog.show_dialog(on_response=_on_response)
    except Exception:
        log_exception('confirm')


def sim_name(sim_info):
    if sim_info is None:
        return '(personne)'
    try:
        return '{} {}'.format(sim_info.first_name, sim_info.last_name).strip()
    except Exception:
        return str(getattr(sim_info, 'sim_id', '?'))
