from copy import copy

import arrow
import datetime
from arrow import Arrow
from jira import Issue
from munch import munchify

from augur.context import AugurContext
from augur.common import POSSIBLE_DATE_TIME_FORMATS
from augur.integrations.objects.base import JiraObject, InvalidId


class JiraIssue(JiraObject):
    """
    Represents a collection of issues

    Options:
        - key (Optional) - The key of the issue to load
    """

    def __init__(self, source, **kwargs):
        super(JiraIssue, self).__init__(source, **kwargs)
        self._issue = None
        self._epic = None
        self._parent = None
        self.default_fields = self.source.default_fields

    def _load(self):

        if not self.option("key"):
            raise InvalidId("Issue key must be given")

        self.log_access('issue',self.option('key'))
        issue = self.source.jira.issue(self.option('key'))
        if issue:
            self._issue = munchify(issue.raw)
            return True
        else:
            self._issue = None
            self.logger.error("JiraIssue: Unable to load issue from Jira")
            return False

    def __eq__(self, issue):
        """
        Override equality to use the issue key (when available) as the compared value as opposed to the object ID
        :param cmp: The JiraIssue object to cmpare against.
        :return:
        """
        if not self.key and not issue.key:
            # when both are empty we compare the object IDs instead
            return id(self) == id(issue)
        else:
            return self.key == issue.key

    def __ne__(self, issue):
        return not self.__eq__(issue)

    def __hash__(self):
        # use the issue key as the hash if the issue exists, otherwise fallback to using the python object id.
        return hash(self.key) if self.key else hash(id(self))

    @property
    def is_subtask(self):
        return self.get_field('issuetype.subtask') is not None

    @property
    def summary(self):
        return self.get_field('summary') or ""

    @property
    def status(self):
        return self.get_field('status.name') or ""

    @property
    def priority(self):
        return self.get_field('priority.name') or ""

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

    def get_parent(self, only_key=True):
        """
        Gets the parent key or issue object
        :param only_key: If True then only returns the key as a string.  Otherwise returns a new JiraIssue object
                            containing parent information
        :return: Return either a parent issue key, the parent issue JiraIssue object or None if not found.
        """
        parent_key = self.get_field('parent.key')
        if not only_key and parent_key:
            if self._parent:
                return self._parent

            self._parent = JiraIssue(source=self.source,key=parent_key)
            if self._parent.load():
                return self._parent
            else:
                return None

        return parent_key

    def get_epic(self, only_key=True):
        """
        Gets the associated epic key or issue object
        :param only_key: If True then only returns the key as a string.  Otherwise returns a new JiraIssue object
                            containing epic information
        :return: Return either an epic issue key, the epic JiraIssue object or None if not found.
        """

        field_name = self.default_fields['epic link']
        epic_key = self.get_field('fields.%s'%field_name)

        if epic_key and not only_key:
            if self._epic:
                return self._epic

            self._epic = JiraEpic(source=self.source,key=epic_key)
            if self._epic.load():
                return self._epic
            else:
                return None

        return epic_key

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
                    if p in current and not isinstance(current[p], dict):
                        val = current[p]
                        break
                    elif p in current:
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


class JiraEpic(JiraIssue):

    def __init__(self, source, **kwargs):
        super(JiraEpic, self).__init__(source, **kwargs)
        self._epic_issues = None

    @property
    def issues(self):
        """
        Gets all the issues contained within the epic as a JiraIssueCollection
        :return:
        """
        if self._epic_issues:
            return self._epic_issues

        self._epic_issues = JiraIssueCollection(source=self.source, input_jql="\"Epic Link\" = %s" % self.key)
        if self._epic_issues.load():
            return self._epic_issues
        else:
            return None


class JiraIssueCollection(JiraObject):
    """
    Represents a collection of issues

    Options:
        - input_jql (Optional) - The JQL used to load the issue set.  Required if jira_issue_list not given.
        - group_id (Optional) - The ID of the group to use for context.  If not provided, then certain features are not
                    available such as "completed_points"
        - input_jira_issue_list (Optional) - A list of json objects as dicts returned from the JIRA REST API. Required
                if jql not given
        - issue_keys (Optional) - A list or comma separated string of issue keys to load
        - paging_start_at (Optional, Default=0) - The issue index to start with
        - paging_max_results (Optional, Default=500) - The maximum number of issues to return
    """

    def __init__(self, source, **kwargs):
        self._issues = None
        super(JiraIssueCollection, self).__init__(source, **kwargs)

    def count(self):
        return len(self._issues)

    def merge(self, collection):
        """
        Creates a new issue collection which contains the set of issues from this and given collection.  Duplicates
        are removed.
        :param collection: JiraIssueCollection to merge
        :return:
        """

        # this will remove duplicates
        issue_set = set(self._issues + collection._issues)

        # convert back to a list.
        merged_list = list(issue_set)

        jic = JiraIssueCollection(source=self.source)
        jic.prepopulate(merged_list)
        return jic

    def dedupe(self):
        issue_set = set(self._issues)
        self._issues = issue_set
        return self

    def __iter__(self):
        return iter(self._issues)

    @property
    def issues(self):
        return self._issues

    @property
    def total_points(self):
        return reduce(lambda x,y: x+y.points, self._issues, 0)

    @property
    def completed_points(self):
        assert(self.option('group_id'))

        points = 0
        context = AugurContext(self.option('group_id'))
        for i in self._issues:
            if context.workflow.is_resolved(status=i.status,resolution=i.resolution):
                points += i.points

        return points

    @property
    def incomplete_points(self):
        assert(self.option('group_id'))

        points = 0
        context = AugurContext(self.option('group_id'))
        for i in self._issues:
            if not context.workflow.is_resolved(status=i.status,resolution=i.resolution):
                points += i.points

        return points

    def prepopulate(self, data):
        """
        Creates a copy of the given JiraIssue objects and populates this with them.  Note that it can take a
        list of JiraIssue objects or another JiraIssueCollection.  In both cases, it makes a copy of the JiraIssues
        within.
        :param data: A list of JiraIssue objects or a JiraIssueCollection
        :return: Returns the given list if successful
        """
        if isinstance(data,list):
            self._issues = copy(data)
            return self._issues
        elif isinstance(data, JiraIssueCollection):
            self._issues = copy(data._issues)

        return self._issues

    def _load(self):

        fields = self.source.default_fields

        jql = None
        if self.option('input_jql'):
            jql = self.option('input_jql')
        elif self.option('issue_keys') is not None:
            if isinstance(self.option('issue_keys'), (str, unicode)):
                keys = self.option('issue_keys').split(',')
            else:
                keys = self.option('issue_keys')

            if len(keys) > 0:
                jql = "key in (%s)"%",".join(keys)
            else:
                # an empty set of keys was given.  This is valid but we can bypass the remaining logic
                self._issues = []
                return True

        if jql:
            self.log_access('search',jql)
            search_results = self.source.jira.search_issues(
                jql,
                startAt=self.option('paging_start_at'),
                maxResults=self.option('paging_max_results', 0),
                validate_query=True,
                fields=fields.values(),
                expand="changelog",
                json_result=False)  ## Must set to False to let PyJira manage paging

            if search_results:
                issues = search_results
            else:
                self.logger.error("Unable to load issues from JQL: %s" % jql)
                return False

        elif self.option('input_jira_issue_list'):

            if isinstance(self.option('input_jira_issue_list'), list):
                issues = self.option('input_jira_issue_list')
            else:
                self.logger.error("JiraIssueCollection: Received 'input_jira_issue_list' that was not "
                                  "of type JiraIssueCollection")
                return False
        else:
            self.logger.error("Unable to load issue collection because no source was specified (jql or list)")
            return False

        assert (isinstance(issues, list))
        self._issues = []
        for i in issues:
            issue_ob = JiraIssue(self.source)
            result = issue_ob.prepopulate(i)
            if len(result):
                self._issues.append(issue_ob)

        return True


class JiraReleaseNotes(JiraIssueCollection):

    def __init__(self, source, **kwargs):
        super(JiraReleaseNotes, self).__init__(source, **kwargs)
        self._issues = None
        self._release_notes = None

    def _load(self):
        
        try:
            start, end = self._get_date_range()

        except (TypeError,LookupError), e:
            self.logger.error(e.message)
            return False

        start_str = start.format("YYYY/MM/DD HH:mm")
        end_str = end.format("YYYY/MM/DD HH:mm")

        context = AugurContext(self.option('group_id'))
        input_jql = "%s AND (status in (\"Resolved\") AND status changed to \"Production\" " \
                    "during ('%s','%s')) order by updated asc" % (context.workflow.get_projects_jql(),
                                                                  start_str, end_str)
        self._set_option('input_jql',input_jql)

        # load the issues that were released during that time
        if not super(JiraReleaseNotes,self)._load():
            return False

        # Collect statistics about those issues and get total points based on parent issues if applicable.
        #   Also, find out which epic it was part of and aggregate the total points released.
        released_tickets = []
        bug_count = 0
        task_story_count = 0
        total_points = 0
        for issue in self._issues:

            if issue.issuetype.lower() in ('bug','defect'):
                bug_count += 1
            else:
                task_story_count += 1

            points = issue.points

            epic = None
            parent = None
            if issue.is_subtask:
                # get the parent ticket instead
                parent = issue.get_parent(only_key=False)
                if parent:
                    epic = parent.get_epic(only_key=False)
                    if not points:
                        points = parent.points
            else:
                epic = issue.get_epic(only_key=False)

            released_tickets.append({
                'issue':issue,
                'parent': parent,
                'epic': epic,
                'points': points,
            })

            total_points += issue.points

        self._release_notes = munchify({
            'start_date': start,
            'end_date': end,
            'total_points': total_points,
            'bug_count': bug_count,
            'feature_count': task_story_count,
            'issues': released_tickets
        })

        return True

    @property
    def start(self):
        return self._release_notes.start_date

    @property
    def end(self):
        return self._release_notes.end_date

    @property
    def total_points(self):
        return self._release_notes.total_points

    @property
    def bug_count(self):
        return self._release_notes.bug_count

    @property
    def feature_count(self):
        return self._release_notes.feature_count

    @property
    def released_issues(self):
        return self._release_notes.issues

    @property
    def release_notes(self):
        return self._release_notes

    def _get_date_range(self):
        """
        Determine the start and end dates to use for the release notes query based on information found
        in the start and end option strings.  These options could be set as strings, Arrow objects or datetime
        objects.  If string, then it can be any one of the formats found in POSSIBLE_DATE_TIME_FORMATS.
        :return: Returns a tuple containing the start and end date as Arrow objects
        """
        start = self.option('start')
        end = self.option('end')
        
        if not start or not end:
            raise LookupError("You must specify a start and end date for releases")
        else:
            if isinstance(start, Arrow):
                calc_start = start
            elif isinstance(start, (str,unicode)):
                calc_start = arrow.get(start, POSSIBLE_DATE_TIME_FORMATS).replace(tzinfo=None)
            elif isinstance(start, datetime.datetime):
                calc_start = arrow.get(start)
            else:
                raise TypeError("Invalid start date type given.  Must be Arrow, string or datetime")

            if isinstance(end, Arrow):
                calc_end = end
            elif isinstance(start, (str,unicode)):
                calc_end = arrow.get(end, POSSIBLE_DATE_TIME_FORMATS).replace(tzinfo=None)
            elif isinstance(end, datetime.datetime):
                calc_end = arrow.get(end)
            else:
                raise TypeError("Invalid start date type given.  Must be Arrow, string or datetime")

        return calc_start, calc_end