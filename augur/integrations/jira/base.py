import logging

from dateutil.parser import parse


class JiraObject(object):

    def __init__(self, source, **kwargs):
        self.source = source
        self.logger = logging.getLogger("augurjira")
        if not self._options:
            self._options = kwargs
        else:
            self._options.update(kwargs)

    def option(self, key, default=None):
        return self._options[key] if key in self._options else default

    def load(self, **kwargs):
        self._options.update(kwargs)
        self._load()

    def _load(self):
        raise NotImplemented()

    def _convert_date_string_to_date_time(self, date_str):
        try:
            dt = parse(date_str)
            return dt
        except ValueError,e:
            self.logger.warning("JiraObject: Unable to parse string %s"%date_str)
            return None

    def prepopulate(self,data):
        raise NotImplemented()