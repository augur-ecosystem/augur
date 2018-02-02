from munch import munchify

from augur.integrations.objects.base import JiraObject, InvalidData, InvalidId


class JiraIssue(JiraObject):

    def __init__(self, source, **kwargs):
        super(JiraIssue, self).__init__(source, **kwargs)
        self._issue = None
        self.default_fields = self.source.default_fields

    def _load(self):

        if not self.option("key"):
            raise InvalidId("Issue key must be given")

        issue = self.source.jira.issue(self.option('key'))
        if issue:
            self._issue = munchify(issue)
        else:
            self._issue = None
            self.logger.error("JiraIssue: Unable to load issue from Jira")
            return False

    @property
    def status(self):
        return self._issue.fields.status.name if self._issue and \
                                                 'status' in self._issue.fields \
                                                 and self._issue.fields.status else ""

    @property
    def assignee(self):
        return self._issue.fields.assignee.name if self._issue \
                                                   and 'assignee' in self._issue.fields \
                                                   and self._issue.fields.assignee else ""

    @property
    def points(self):
        sp_field_name = self.default_fields["story points"]
        return self._issue.fields[sp_field_name] if self._issue and \
                                                    sp_field_name in self._issue.fields and \
                                                    self._issue.fields[sp_field_name] else 0

    @property
    def resolution(self):
        return self._issue.fields.resolution.name if self._issue and \
                                                     'resolution' in self._issue.fields and \
                                                     self._issue.fields.resolution else ""

    @property
    def key(self):
        return self._issue.key if self._issue else ""

    @property
    def issue(self):
        """
        Returns the issue as a Munch dictionary object.  Meaning that you can access its properties using dot
        notation or dict notation.  This is the raw issue as returned from Jira otherwise.
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
            issues = self.source.jira.search_issues(
                self.option('input_jql'),
                startAt=self.option('paging_start_at'),
                maxResults=self.option('paging_max_results', 500),
                validate_query=True,
                fields=fields.values(),
                expand=None,
                json_result=True)
        elif self.option('input_jira_issue_list'):
            issues = self.option('input_jira_issue_list')

        if issues and 'issues' in issues:
            self._issues = []
            for i in issues['issues']:
                issue_ob = JiraIssue(self.source)
                if issue_ob.prepopulate(i):
                    self._issues.append(issue_ob)

            return True

        else:
            self.logger.error("You must specify one of the input options in order to properly load this object")
            return False
