"""
The audit module is used to gather data about activities that occur during the execution of
various methods within the Augur library.  This information can be interrogated later to gather
information about issues that occured without having to rely entirely on return  values or
exceptions.
"""
from django.dispatch import receiver
from augur.signals.cache_signals import cache_updated, cache_item_loaded
from augur.common import Struct
import logging

REQUEST_AUDIT = Struct(**{
    "cache": Struct(**{
        "hits": [],
        "updates": []
    }),
})


def get_audit():
    """
    Retrives the audit object
    @return: A dictionary containing audit information
    """
    return REQUEST_AUDIT


@receiver(cache_updated)
def add_cache_update_to_request(sender, **kwargs):
    """
    Listens for cache update signals and updates the audit object with
     information from the signal.
    """
    
    cache_name = kwargs.get("cache_name", "")
    key_count = kwargs.get("key_count", 0)
    update_info = kwargs.get("update_info", 0)

    logging.info("Received cache update signal:\n\tcache_name=%s\n\tkey_count=%s"%(cache_name,key_count))

    REQUEST_AUDIT.cache.updates.append({
        "cache_name": cache_name,
        "key_count": key_count,
        "update_info": update_info
    })


@receiver(cache_item_loaded)
def add_cache_hit_to_request(sender, **kwargs):
    """
    Listens for cache hit signals and updates the audit object with
     information from the signal.
    """

    cache_name = kwargs.get("cache_name", "")
    cache_date = kwargs.get("cache_date", None)
    key_count = kwargs.get("key_count", 0)
    query_object = kwargs.get("query_object", 0)

    logging.info("Received cache hit signal:\n\tcache_name=%s\n\tkey_count=%s\n\tquery=%s"%(cache_name,key_count,str(query_object)))

    cache_date_formatted = cache_date.strftime("%m/%d/%Y @ %I:%M %p") \
        if cache_date else "<unknown date>",

    REQUEST_AUDIT.cache.hits.append({
        "cache_name": cache_name,
        "query_object": query_object,
        "cache_date": cache_date_formatted,
        "key_count": key_count
    })
