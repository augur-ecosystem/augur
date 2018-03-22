import datetime
import json

from jira.resources import Resource


class AugurJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        from augur.context import AugurContext

        if isinstance(obj, datetime.timedelta):
            return obj.total_seconds()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, Resource):
            return obj.raw
        elif isinstance(obj, AugurContext):
            return {
                "group_id": obj.group.id
            }

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

