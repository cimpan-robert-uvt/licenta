from django.apps import AppConfig
from django.core.signals import request_started
from django.dispatch import receiver


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        """Clear all sessions when the application starts (deferred until first request)"""
        import sys

        if "runserver" in sys.argv or "runserver_plus" in sys.argv:
            _state = {"cleared": False}

            @receiver(request_started)
            def clear_sessions_on_first_request(sender, **kwargs):
                """Clear sessions only on first request to avoid app initialization warnings"""
                if not _state["cleared"]:
                    try:
                        from django.contrib.sessions.models import Session

                        Session.objects.all().delete()
                        _state["cleared"] = True
                        request_started.disconnect(clear_sessions_on_first_request)
                    except Exception:
                        pass
