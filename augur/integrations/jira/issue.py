from munch import Munch

from augur.integrations.jira.base import JiraObject
from augur.integrations.jira.board import InvalidData, InvalidId


class JiraIssue(JiraObject):
    DEFAULT_FIELDS = ["summary","status","priority","issuetype","parent","resolution","Dev Team",
                      "labels","issuelinks","development","reporter","assignee","issuetype", "project",
                      "priority","status","creator","attachment"]

    def __init__(self, source, **kwargs):
        self._issue = None
        super(JiraIssue, self).__init__(source, **kwargs)

    def _load(self):

        if not self.option("key"):
            raise InvalidId("Issue key must be given")

        issue = self.source.jira.issue(self.option('key'))
        if issue:
            self._issue = Munch(issue)
        else:
            self._issue = None
            raise InvalidData("Unable to load issue from Jira")

    @property
    def issue(self):
        """
        Returns the issue as a Munch dictionary object.  Meaning that you can access its properties using dot
        notation or dict notation.
        :return: The issue object as a Munch instance
        """
        return self._issue

    def prepopulate(self, data):
        """
        Takes a dictionary as returned from the JSON REST API (in JSON form)
        :param data: The issue dictionary
        :return: Returns the issue populated.
        """

        if 'fields' in data:
            self._issue = Munch(data)
        else:
            self._issue = None

        return self._issue


class JiraIssueCollection(JiraObject):
    """
    Represents a collection of issues

    Options:
        - input_jql (Optional) - The JQL used to load the issue set.  Required if jira_issue_list not given.
        - input_jira_issue_list (Optional) - A list of json objects as dicts returned from the JIRA REST API. Required
                if jql not given.
        - paging_start_at (Optional, Default=0) - The issue index to start with
        - paging_max_results (Optional, Default=500) - The maximum number of issues to return
    """

    def __init__(self, source, **kwargs):
        self._issues = None
        self._translated_default_fields = []
        super(JiraIssueCollection, self).__init__(source, **kwargs)

    def _translate_fields(self):

        if not self._translated_default_fields:
            self._translated_default_fields = [self.source.get_field_by_name(f) for f in JiraIssue.DEFAULT_FIELDS]

        return self._translated_default_fields

    def _load(self):

        issues = None
        fields = self._translate_fields()
        if self.option('input_jql'):
            issues = self.source.jira.search_issues(
                self.option('input_jql'),
                startAt=self.option('paging_start_at'),
                maxResults=self.option('paging_max_results',500),
                validate_query=True,
                fields=fields,
                expand=None,
                json_result=True)
        elif self.option('input_jira_issue_list'):
            issues = self.option('input_jira_issue_list')

        if issues:
            self._issues = []
            for i in issues:
                issue_ob = JiraIssue(self.source)
                if issue_ob.prepopulate(i):
                    self._issues.append(issue_ob)

        else:
            raise InvalidData("You must specify one of the input options in order to properly load this object")