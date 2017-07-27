import copy

import augur
from augur.common import deep_get
from augur.events import EventData


class JiraEventData(EventData):
    """
    Wraps a jira webhook event to make data access easier.
    """
    def __init__(self,data):
        self.data = data

    @staticmethod
    def process_event_data(event):
        """
        Jira events can sometimes contain more than one change.  This will turn a given event into multiple
        events in cases where this is true and return the new set of events.  These events can then be passed into
        during the construction of the JiraEventData object to encapsulate that singular event.
        :param event: The original event object
        :return: A list of events based on the original
        """
        action = None
        if event['issue_event_type_name'] == "issue_commented":
            action = "issue:commented"
        elif event['issue_event_type_name'] == "issue_work_logged":
            action = "issue:commented"
        elif event['issue_event_type_name'] in ("issue_updated", "issue_generic"):
            for change in event['changelog']['items']:
                if change['field'] == "status":
                    action = "issue:transitioned"
                else:
                    action = "issue:field_change"

        events = []
        if action is not None and event is not None:
            if 'changelog' in event:
                if len(event['changelog']['items']) > 1:
                    for e in event['changelog']['items']:
                        e_copy = copy.deepcopy(event)
                        e_copy['changelog']['current'] = copy.deepcopy(e)
                        events.append(e_copy)
                else:
                    event['changelog']['current'] = event['changelog']['items'][0]
                    events.append(event)
            else:
                events.append(event)

        return events

    def get_linked_tickets(self, link_type, linked_project_key=None, direction=None):
        """
        Gets all the tickets that are linked to the given ticket with the given constraints.
        :param link_type: The type of link this is (e.g. "Change Management")
        :param linked_project_key: Filter on only tickets with the given project key (optional)
        :param direction: Filter on only links that are either "in" OR "out".  If none given then
                accept either.(optional)
        :return: Return an array of tickets that are linked given the parameters given.
        """
        linked = self.issue_links or []
        tickets = []
        for l in linked:
            if l['type']['name'].lower() == link_type.lower():
                # this is the type of link we're looking for.
                if direction:
                    direction_arr = ['inwardIssue'] if direction == "in" else ['outwardIssue']
                else:
                    direction_arr = ['inwardIssue', 'outwardIssue']

                for d in direction_arr:
                    if d in l:
                        if linked_project_key:
                            pk = l[d]['key'].split("-")[0].lower()
                            if pk != linked_project_key.lower():
                                continue

                        tickets.append(augur.api.get_issue_details(l[d]['key']))

        return tickets

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
        return deep_get(self.data, 'changelog', 'current', 'fromString') or ""

    @property
    def change_to_string(self):
        return deep_get(self.data, 'changelog', 'current', 'toString') or ""
