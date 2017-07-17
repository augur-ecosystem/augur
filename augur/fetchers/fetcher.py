import logging

import augur


class AugurDataFetcher(object):
    """
    Provides a convenient mechanism for returning a well-defined slice of data from Jira.  Supports fetching the
    data, caching the data, retrieving data from the cache, and validation of input
    """
    def __init__(self,augurjira, context=None, force_update=False):

        if not context:
            self.context = augur.api.get_default_context()
        else:
            self.context = context

        self.augurjira = augurjira
        self.recent_data = None
        self.force_update = force_update
        self.logger = logging.Logger("fetcher")
        self.cache = None

        self.init_cache()

    def fetch(self, **args):

        self.validate_input(**args)

        if not self.allow_caching() or not self.get_cached_data():
            self._fetch()

        return self.recent_data

    def init_cache(self):
        pass

    def allow_caching(self):

        if self.force_update:
            return False
        else:
            return True

    def get_cached_data(self):
        return None

    def cache_data(self, data):
        pass

    def _fetch(self):
        raise NotImplementedError("Derived class of AugurDataFetcher must implement the _fetch method")

    def validate_input(self, **args):
        return False


