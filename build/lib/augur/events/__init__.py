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


class AugurEventManager(object):
    """
    A singleton that manages event handlers.
    """
    def __init__(self):
        self._event_listeners = []

    def add_event_listener(self, handler):
        """
        Add a new event listener
        :param handler: The new listener
        :return:
        """
        self._event_listeners.append(handler)

    def handle(self, event):
        handled_by_count = 0
        for et in self._event_listeners:
            if et.should_handle(event):
                handled_by_count += 1 if et.handle(event) else 0
        return handled_by_count
