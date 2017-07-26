from augur.common import deep_get
from augur.events import EventData


class JiraEventData(EventData):
    """
    Wraps a jira webhook event to make data access easier.
    """
    def __init__(self,data):
        self.data = data

    @property
    def raw(self):
        return self.data

    @property
    def name(self):
        return self.data.get('webhookEvent',None)

    @property
    def project(self):
        return deep_get(self.data,'issue','fields','project','key')

    @property
    def issue_key(self):
        return deep_get(self.data,'issue','key')

    @property
    def issue_assignee(self):
        return deep_get(self.data,'issue','fields','assignee','name')

    @property
    def issue_reporter(self):
        return deep_get(self.data,'issue','fields','reporter','name')

    @property
    def issue_status(self):
        return deep_get(self.data,'issue','fields','status','name')

    @property
    def issue_summary(self):
        return deep_get(self.data,'issue','fields','status','name')

    @property
    def issue_links(self):
        return deep_get(self.data, "issue",'fields',"issuelinks") or []

    @property
    def change_from_string(self):
        current = deep_get(self.data, 'changelog', 'current')
        if not current:
            items = deep_get(self.data, 'changelog', 'items')
            if items:
                return items[0].get('fromString',"")
        else:
            return current.get('fromString',"")

        return ""

    @property
    def change_to_string(self):
        current = deep_get(self.data, 'changelog', 'current')
        if not current:
            items = deep_get(self.data, 'changelog', 'items')
            if items:
                return items[0].get('toString',"")
        else:
            return current.get('toString',"")

        return ""
