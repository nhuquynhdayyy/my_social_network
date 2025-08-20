from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    # Thêm hàm này để import signals
    def ready(self):
        import accounts.signals
