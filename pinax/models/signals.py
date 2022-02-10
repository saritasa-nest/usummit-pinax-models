from django.db.models.signals import ModelSignal

pre_softdelete = ModelSignal()
post_softdelete = ModelSignal()
