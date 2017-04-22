import copy

from augur.events.handler import WebhookHandler


class JiraWebhookHandler(WebhookHandler):
    def __init__(self):
        super(JiraWebhookHandler, self).__init__()

    def _process_event(self, event):
        """
        Takes the given event and generates a list of 0 or more events that have been processed and validated.
        :param event: The event received
        :return: Returns an array of events.  In some cases, a single event is actually a combination of
                    multiple actions.  In these cases, more than one event will be returned.  In some cases, the event
                    is not understood as an event by the logic and will return an empty array.
        """
        self.action = None
        self.event = event

        if event['issue_event_type_name'] == "issue_commented":
            self.action = "issue:commented"
        elif event['issue_event_type_name'] == "issue_work_logged":
            self.action = "issue:commented"
        elif event['issue_event_type_name'] in ("issue_updated", "issue_generic"):
            for change in event['changelog']['items']:
                if change['field'] == "status":
                    self.action = "issue:transitioned"
                else:
                    self.action = "issue:field_change"

        events = []
        if self.action is not None and self.event is not None:
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
