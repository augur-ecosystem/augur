import datetime
import json

from bson import ObjectId
from jira.client import ResultList
from jira.resources import Component, Issue

from augur.models import AugurModelProp


class AugurJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AugurModelProp):
            return obj.value
        elif isinstance(obj, datetime.timedelta):
            return obj.total_seconds()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, Component):
            return obj.raw
        elif isinstance(obj, Issue):
            return obj.raw

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class AugurMongoSerializer(object):
    """
    Used to convert types of objects that are not supported by Mongo's BSON for data that is
    going into Mongo and data that is coming from Mongo
    """

    def transform_incoming(self, d):
        if not isinstance(d, dict):
            return d

        for (key, value) in d.iteritems():
            if isinstance(value, Issue):
                d[key] = value.raw
            if isinstance(value, ResultList):
                d[key] = [v.raw for v in value]
            if isinstance(value, AugurModelProp):
                d[key] = value.value
            elif isinstance(value, datetime.timedelta):
                d[key] = AugurMongoSerializer._encode_timedelta(value)
            elif isinstance(value, datetime.date):
                # BSON does not recognize date formats but we can initialize a datetime when a zero time.
                d[key] = datetime.datetime.combine(value, datetime.datetime.min.time())
            elif isinstance(value, dict):
                d[key] = self.transform_incoming(value)
            elif isinstance(value, list):
                for item in value:
                    self.transform_incoming(item)

        return d

    def transform_outgoing(self, d):
        if not isinstance(d, dict):
            return d

        for (key, value) in d.iteritems():
            if isinstance(value, dict) and "_type" in value and value["_type"] == "time_delta":
                d[key] = AugurMongoSerializer._decode_timedelta(value)
            elif isinstance(value, dict):
                d[key] = self.transform_outgoing(value)

        return d

    @staticmethod
    def _encode_timedelta(td):
        return td.total_seconds()

    @staticmethod
    def _decode_timedelta(d):
        from common.formatting import unformat_timedelta
        return unformat_timedelta(d['timedelta'])


def to_mongo(doc):
    t = AugurMongoSerializer()
    return t.transform_incoming(doc)


def from_mongo(doc):
    t = AugurMongoSerializer()
    return t.transform_outgoing(doc)
