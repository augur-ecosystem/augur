import logging

from dateutil.parser import parse
from munch import munchify


class InvalidId(Exception):
    pass


class InvalidData(Exception):
    pass


class JiraObject(object):

    def __init__(self, source, **kwargs):
        self.source = source
        self.logger = logging.getLogger("augurjira")
        self._options = munchify(kwargs)

    def option(self, key, default=None):
        return self._options[key] if key in self._options else default

    def load(self, **kwargs):
        self._options.update(kwargs)
        return self._load()

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

    def log_access(self, api, *parameters):
        self.logger.error("jira:{api}:{parameters}".format(api=api, parameters=",".join([str(p) for p in parameters])))
