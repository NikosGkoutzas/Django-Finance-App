from django.apps import AppConfig

class TransactionsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactionsApp'

    #def ready(self):
    #    import transactionsApp.default_categories