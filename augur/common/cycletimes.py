import datetime
import formatting

CYCLE_LIMITS = {
    1: datetime.timedelta(days=1),
    2: datetime.timedelta(days=2),
    3: datetime.timedelta(days=3),
    4: datetime.timedelta(days=4),
    5: datetime.timedelta(days=5),
    6: datetime.timedelta(days=6),
    7: datetime.timedelta(days=7),
    8: datetime.timedelta(days=10),
    "max": datetime.timedelta(days=10)
}

CYCLE_LIMIT_BLOCKED = datetime.timedelta(days=3)
CYCLE_LIMIT_QR = datetime.timedelta(days=2)

# Global caching of whatever you want - to help reduce the number of requests to JIRA
_CACHE = {}


def get_recommended_cycle_timedelta(points):
    if int(points) in CYCLE_LIMITS:
        return CYCLE_LIMITS[int(points)]
    else:
        return CYCLE_LIMITS["max"]


class CycleViolation:
    key = ""
    summary = ""
    status = ""
    time_in_status = None
    overage = None
    issue = None

    def __init__(self, key="", summary="", status="", time_in_status=None, overage=None):
        self.key = key
        self.summary = summary
        self.status = status
        self.time_in_status = time_in_status
        self.overage = overage

        # purposely don't serialize this because of it's size.
        self.issue = None

    def get_time_in_status(self):
        return formatting.format_timedelta(self.time_in_status, "{days}d,{hours}h")

    def get_overage(self):
        return formatting.format_timedelta(self.overage, "{days}d,{hours}h")

    def to_dict(self):
        d = self.__dict__
        d['time_in_status'] = self.get_time_in_status()
        d['overage'] = self.get_overage()
        return d

    def set_issue(self, issue):
        self.issue = issue

    def get_issue(self):
        return self.issue

    def from_dict(self, d):
        for k, v in d.iteritems():

            if k in ['time_in_status', 'overage']:
                # timedelta values
                td = formatting.unformat_timedelta(v)
                setattr(self, k, td)
            else:
                # all other values
                setattr(self, k, v)
