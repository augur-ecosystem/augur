import logging
import augur


class EventData(object):
    """
    Base class for event data that is passed to event listener objects
    """
    pass


class AugurEventListener(object):
    """
    An event listener is a simple object that has two primary overridden methods:
        * should_handle : This takes an AugurEventData parameter.  The overriding method should use that data
                            to determine if it should handle the event by returning True or False.
        * handle - This is called when should_handle returns True.  Here you can perform whatever actions
                    need to be performed as a consequence of the event.
    """
    def __init__(self, context):
        """
        :type context AugurContext
        :param context:
        """
        self.context = context
        self.logger = logging.getLogger("jira_event_handler")

    def should_handle(self, event_data):
        """
        Return True if the given event data should be processed by this event
        :type event_data: EventData
        :param event_data: The event data received.
        :return: Returns True if this object should handle the given event, False otherwise.
        """
        pass

    def handle(self, event_data):
        """
        Uses the event data to perform actions when the event has occured
        :type event_data: EventData
        :param event_data: The event data received.
        :return:
        """
        pass

    @staticmethod
    def get_linked_tickets(event_data, link_type, linked_project_key=None, direction=None):
        """
        Gets all the tickets that are linked to the given ticket with the given constraints.
        :param event_data: The JiraEventData object
        :param link_type: The type of link this is (e.g. "Change Management")
        :param linked_project_key: Filter on only tickets with the given project key (optional)
        :param direction: Filter on only links that are either "in" OR "out".  If none given then
                accept either.(optional)
        :return: Return an array of tickets that are linked given the parameters given.
        """
        linked = event_data.issue_links or []
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


class AugurEventManager(object):
    """
    A singleton that manages event handlers.
    """
    def __init__(self):
        self._event_handlers = []

    def add_event_handler(self,handler):
        self._event_handlers.append(handler)

    def handle(self, event):
        handled_by_count = 0
        for et in self._event_handlers:
            if et.should_handle(event):
                handled_by_count += 1 if et.handle(event) else 0
        return handled_by_count
