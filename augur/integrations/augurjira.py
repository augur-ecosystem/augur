import logging

from jira import JIRA, Issue
from jira.resources import Resource, GreenHopperResource
from jira.utils import json_loads
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

    def get_projects(self):
        return self.jira._get_json('project', {"expand": "category"})

    def get_board(self, board_id):
        import augur
        found_board = None
        boards_raw = augur.api.get_memory_cached_data('boards')
        if not boards_raw:
            boards = self.jira.boards(maxResults=0)
            found_board = None
            boards_raw = []
            for b in boards:
                boards_raw.append(b.raw)
                if b.id == board_id:
                    found_board = b.raw

            augur.api.memory_cache_data(boards_raw, 'boards')

        if not found_board:
            for b in boards_raw:
                if b['id'] == board_id:
                    return b
            return None
        else:
            return found_board

    def get_sprint_report(self, board_id, sprint_id):
        return self.custom_get_json(path='rapid/charts/sprintreport?rapidViewId=%s&sprintId=%s' % (board_id, sprint_id),
                                    base=GreenHopperResource.AGILE_BASE_URL,
                                    replacement_options={'agile_rest_path': GreenHopperResource.GREENHOPPER_REST_PATH})

    def custom_get_url(self, path, base, replacement_options=None):
        options = self.jira._options.copy()
        options.update({'path': path})

        if replacement_options:
            options.update(replacement_options)

        return base.format(**options)

    def custom_get_json(self, path, params=None, base=Resource.JIRA_BASE_URL, replacement_options=None):
        url = self.custom_get_url(path=path, base=base, replacement_options=replacement_options)
        r = self.jira._session.get(url, params=params)
        try:
            r_json = json_loads(r)
        except ValueError as e:
            self.jira.logging.error("%s\n%s" % (e, r.text))
            raise e
        return r_json
