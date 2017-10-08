import django.dispatch


cache_updated = django.dispatch.Signal(providing_args=["cache_name", "key_count"])
cache_item_loaded = django.dispatch.Signal(providing_args=["cache_name", "cached_date", "key_count"])

