from jira import Issue
from munch import munchify, DefaultMunch

from augur.integrations.objects.base import JiraObject, InvalidId


class JiraIssue(JiraObject):

    def __init__(self, source, **kwargs):
        super(JiraIssue, self).__init__(source, **kwargs)
        self._issue = None
        self.default_fields = self.source.default_fields

    def _load(self):

        if not self.option("key"):
            raise InvalidId("Issue key must be given")

        self.log_access('issue',self.option('key'))
        issue = self.source.jira.issue(self.option('key'))
        if issue:
            self._issue = munchify(issue)
        else:
            self._issue = None
            self.logger.error("JiraIssue: Unable to load issue from Jira")
            return False

    @property
    def status(self):
        return self.get_field('status.name') or ""

    @property
    def issuetype(self):
        return self.get_field('issuetype.name') or ""

    @property
    def description(self):
        return self.get_field('description') or ""

    @property
    def reporter(self):
        return self.get_field('reporter.name') or ""

    @property
    def assignee(self):
        return self.get_field('assignee.name') or ""

    @property
    def points(self):
        return self.get_field("story points", translate=True) or 0.0

    @property
    def resolution(self):
        return self.get_field('resolution.name') or ""

    @property
    def key(self):
        return self.get_field('key') or ""

    @property
    def team_name(self):
        return self.get_field('dev team.value', translate=True) or ""

    @property
    def issue(self):
        """
        Returns the issue as a Munch dictionary object.  Meaning that you can access its properties using dot
        notation or dict notation.  This is the raw issue as returned from Jira otherwise.
        :return: The issue object as a Munch instance
        """
        return self._issue

    def get_field(self, field, translate=False):
        if translate:
            parts = field.split(".")
            parts[0] = self.default_fields[parts[0].lower()]
            field = '.'.join(parts)

        if self._issue and self._issue.fields:

            if field not in self._issue:
                parts = field.split(".")
                current = self._issue.fields
                val = None
                for p in parts:
                    if p in current and not isinstance(current[p],dict):
                        val = current[p]
                        break
                    else:
                        current = current[p]
                return val
            else:
                return self._issue[field]
        else:
            return None

    def prepopulate(self, data):
        """
        Takes a dictionary as returned from the JSON REST API (in JSON form)
        :param data: The issue dictionary
        :return: Returns the issue populated.
        """

        if isinstance(data, Issue):
            self._issue = munchify(data.raw)
        elif isinstance(data, dict) and 'fields' in data:
            self._issue = munchify(data)
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
        super(JiraIssueCollection, self).__init__(source, **kwargs)

    def count(self):
        return len(self._issues)

    def __iter__(self):
        return iter(self._issues)

    @property
    def issues(self):
        return self._issues

    def _load(self):

        issues = None
        fields = self.source.default_fields

        if self.option('input_jql'):
            self.log_access('search',self.option('input_jql'))
            search_results = self.source.jira.search_issues(
                self.option('input_jql'),
                startAt=self.option('paging_start_at'),
                maxResults=self.option('paging_max_results', 0),
                validate_query=True,
                fields=fields.values(),
                expand="changelog",
                json_result=False)  ## Must set to False to let PyJira manage paging

            if search_results:
                issues = search_results
            else:
                self.logger.error("You must specify one of the input options in order to properly load this object")
                return False

        elif self.option('input_jira_issue_list'):

            if isinstance(self.option('input_jira_issue_list'), list):
                issues = self.option('input_jira_issue_list')
            else:
                self.logger.error("JiraIssueCollection: Received 'input_jira_issue_list' that was not "
                                  "of type JiraIssueCollection")
                return False

        assert (isinstance(issues, list))
        self._issues = []
        for i in issues:
            issue_ob = JiraIssue(self.source)
            result = issue_ob.prepopulate(i)
            if len(result):
                self._issues.append(issue_ob)

        return True
