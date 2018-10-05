import logging

from jira import JIRA, Issue
from jira.resources import Board
from munch import munchify

from augur import api
from augur import settings


class AugurJira(object):
    """
    A thin wrapper around the Jira module providing some refinement for things like fields, convenience methods
    for ticket actions and awareness for Augur-specific data types.
    """
    jira = None

    def __init__(self, server=None, username=None, password=None):

        self.logger = logging.getLogger("augurjira")
        self.server = server or settings.main.integrations.jira.instance
        self.username = username or settings.main.integrations.jira.username
        self.password = password or settings.main.integrations.jira.password
        self.fields = None

        self.jira = JIRA(basic_auth=(
            self.username,
            self.password),
            server=self.server,
            options={"agile_rest_path": "agile"})

        self._field_map = {}

        self._default_fields = munchify({
            "summary": None,
            "description": None,
            "status": None,
            "priority": None,
            "parent": None,
            "resolution": None,
            "epic link": None,
            "dev team": None,
            "labels": None,
            "issuelinks": None,
            "development": None,
            "reporter": None,
            "assignee": None,
            "issuetype": None,
            "project": None,
            "creator": None,
            "attachment": None,
            "worklog": None,
            "story points": None,
            "changelog": None
        })

        self.fields = api.get_memory_cached_data('custom_fields')
        if not self.fields:
            fields = api.memory_cache_data(self.jira.fields(), 'custom_fields')
            self.fields = {f['name'].lower(): munchify(f) for f in fields}

        default_fields = {}
        for df, val in self._default_fields.iteritems():
            default_fields[df] = self.get_field_by_name(df)

        self._default_fields = munchify(default_fields)

    @property
    def default_fields(self):
        """
        Returns a dict containing the friendly name of fields as keys and jira's proper field names as values.
        :return: dict
        """
        return self._default_fields

    def get_field_by_name(self, name):
        """
        Returns the true field name of a jira field based on its friendly name
        :param name: The friendly name of the field
        :return: A string with the true name of a field.
        """
        assert self.fields

        try:
            _name = name.lower()
            if _name.lower() in self.fields:
                return self.fields[_name]['id']

            else:
                return name

        except (KeyError, ValueError):
            return name

    def link_issues(self, link_type, inward, outward, comment=None):
        """
        Establishes a link in jira between two issues
        :param link_type: A string indicating the relationship from the inward to the outward
         (Example: "is part of this release")
        :param inward: Can be one of: Issue object, Issue dict, Issue key string
        :param outward: Can be one of: Issue object, Issue dict, Issue key string
        :param comment: None or a string with the comment associated with the link
        :return: No return value.
        """
        ""
        if isinstance(inward, dict):
            inward_key = inward['key']
        elif isinstance(inward, Issue):
            inward_key = inward.key
        elif isinstance(inward, (str, unicode)):
            inward_key = inward
        else:
            raise TypeError("'inward' parameter is not of a valid type")

        if isinstance(outward, dict):
            outward_key = outward['key']
        elif isinstance(outward, Issue):
            outward_key = outward.key
        elif isinstance(outward, (str, unicode)):
            outward_key = outward
        else:
            raise TypeError("'outward' parameter is not of a valid type")

        self.jira.create_issue_link(link_type, inward_key, outward_key, comment)

    def create_ticket(self, create_fields, update_fields=None, watchers=None):
        """
        Create the ticket with the required fields above.  The other keyword arguments can be used for other fields
           although the values must be in the correct format.
        :param update_fields:
        :param create_fields: All fields to include in the creation of the ticket. Keys include:
                project: A string with project key name (required)
                issuetype: A dictionary containing issuetype info (see Jira API docs) (required)
                summary: A string (required)
                description: A string
        :param update_fields: A dictionary containing reporter info  (see Jira API docs)
        :param watchers: A list of usernames that will be added to the watch list.

        :return: Return an Issue object or None if failed.
        """
        try:
            ticket = self.jira.create_issue(create_fields)

            if ticket:
                try:
                    # now update the remaining values (if any)
                    # we can't do this earlier because assignee and reporter can't be set during creation.
                    if update_fields and len(update_fields) > 0:
                        ticket.update(
                            update_fields
                        )
                except Exception, e:
                    self.logger.warning("Ticket was created but not updated due to exception: %s" % e.message)

                try:
                    if watchers and isinstance(watchers, (list, tuple)):
                        [self.jira.add_watcher(ticket, w) for w in watchers]
                except Exception, e:
                    self.logger.warning("Unable to add watcher(s) due to exception: %s" % e.message)

            return ticket

        except Exception, e:
            self.logger.error("Failed to create ticket: %s", e.message)
            return None
