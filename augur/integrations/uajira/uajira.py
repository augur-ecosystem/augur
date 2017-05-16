import csv
import datetime

import logging
import os
from dateutil.parser import parse
from jira import JIRA, Issue

from augur import common
from augur import settings
from augur.common import const, cycletimes, audit, cache_store
from augur.common.timer import Timer
from augur.integrations.uatempo import UaTempo

__jira = None


def get_jira():
    global __jira
    if not __jira:
        __jira = UaJira()
    return __jira


class UaJira(object):
    jira = None

    def __init__(self, server=None, username=None, password=None):

        self.logger = logging.getLogger("uajira")

        self.server = server or settings.main.integrations.jira.instance
        self.username = username or settings.main.integrations.jira.username
        self.password = password or settings.main.integrations.jira.password

        self.jira = JIRA(basic_auth=(
            self.username,
            self.password),
            server=self.server)

        self.mongo = cache_store.UaStatsDb()
        self.jiraissues_data_store = cache_store.UaJiraIssueData(self.mongo)

    def get_jira(self):
        """
        Get the JIRA object that is a proxy to the JIRA instance API.
        :return:
        """
        return self.jira

    def get_username(self):
        return self.username

    def get_password(self):
        return self.password

    ######################################################################
    # COMPONENTS AND VERSIONS
    #  Get project related information
    ######################################################################

    def get_project_components(self, project):
        """
        Simply returns all the components associated with the given project.
        :param project:  The project key (e.g. ENG)
        :return: Returns the component objects as returned by the JIRA object.
        """
        return self.jira.project_components(project)

    def get_group_data(self):
        return self.jira.groups("Team ")

    def get_group_members(self, group_ob):
        return self.jira.group_members(group_ob)

    ######################################################################
    # ISSUES
    #  Methods for basic querying using JQL with some additional helpers
    ######################################################################

    def execute_jql(self, jql, expand=None, max_results=500):
        """
        Simply a pass through to the JIRA search_issues call.
        :param max_results: The maximum number of results to return.  If you pass 0 then this will only get the count
                of issues and not return any of their content.
        :param jql:  The jql to execute
        :param expand: A string containing a list of fields that should be expanded. This could take longer.
        :return: Returns an array of JIRA objects.
        """
        if max_results == 0:
            # this is necessary because of a bug in the Jira python library where it interprets 0 as None
            #   and returns all the results.
            max_results = "0"

        with Timer("Executing jql: %s"%jql) as t:
            return self.jira.search_issues(jql, expand=expand, maxResults=max_results)

    def execute_jql_with_team_analysis(self, query):
        """
        Returns an object containing completed stories, incomplete stories and the percent complete
        :param query: The JQL to return the tickets to get the stats for
        :return: Return a dict with the following keys: complete, incomplete, total_points,percent_complete
        """
        issues = self.execute_jql(query, expand="changelog")

        result = {
            "complete": 0.0,
            "incomplete": 0.0,
            "abandoned": 0,
            "total_points": 0.0,
            "percent_complete": 0,
            "open": 0,
            "blocked": 0,
            "production": 0,
            "staging": 0,
            "integration": 0,
            "remaining_ticket_count": 0,
            "in_progress": 0,
            "resolved": 0,
            "closed": 0,
            "quality_review": 0,
            "unpointed": 0,
            "config_issue": "",
            "ticket_count": len(issues),
            "unpointed_complete_issues": 0,
            'color': const.COLOR_OK,
            'developer_stats': {}
        }

        for issue in issues:
            new_issue = self._analytics_issue_details(issue)

            ########
            # Completion calculations
            ########
            self._analytics_point_completion(result, new_issue, include_dev_stats=False)

            ########
            # Status counts
            ########
            self._analytics_status_counts(result, new_issue)

        ####
        # COMPLETION STATUS
        ####
        self._analytics_completion_status(result, include_dev_stats=False)

        ####
        # SOME WARNINGS AND NOTES
        ####
        self._analytics_feedback(result)

        return result

    def execute_jql_with_totals(self, query):
        """
        This is a very of analytics that returns less information but will run more quickly.
        :param query: The JQL
        :return: The result object.
        """
        issues = self.execute_jql(query, expand="changelog")
        result = {
            "complete": 0.0,
            "incomplete": 0.0,
            "total_points": 0.0,
            "abandoned": 0.0,
            "unpointed": 0.0
        }

        for issue in issues:
            new_issue = self._analytics_issue_details(issue)
            self._analytics_point_completion(result, new_issue, False)

        return result

    def execute_jql_with_analysis(self, query):
        """
        Returns an object containing completed stories, incomplete stories and the percent complete
        :param query: The JQL to return the tickets to get the stats for
        :return: Return a dict with the following keys: complete, incomplete, total_points,percent_complete
        """
        issues = self.execute_jql(query, expand="changelog")

        result = {
            "complete": 0.0,
            "incomplete": 0.0,
            "total_points": 0.0,
            "abandoned": 0,
            "percent_complete": 0,
            "open": 0,
            "blocked": 0,
            "in_progress": 0,
            "production": 0,
            "staging": 0,
            "integration": 0,
            "resolved": 0,
            "closed": 0,
            "quality_review": 0,
            "unpointed": 0,
            "config_issue": "",
            "ticket_count": len(issues),
            "remaining_ticket_count": 0,
            "unpointed_complete_issues": 0,
            'color': const.COLOR_OK,
            'inprog_cycle_violations': {},
            'blocked_cycle_violations': {},
            'quality_review_cycle_violations': {},
            'developer_stats': {},
            'issues': {}
        }

        for issue in issues:

            new_issue = self._analytics_issue_details(issue)

            if new_issue['assignee'] not in result['developer_stats']:
                result['developer_stats'][UaJira._clean_username(new_issue['assignee'])] = {
                    "info": issue.raw['fields']['assignee'] if issue.fields.assignee else {},
                    "complete": 0,
                    "incomplete": 0,
                    "abandoned": 0,
                    "percent_complete": 0,
                    "issues": []
                }

            # Add this issue to the list of issues for the user
            result['developer_stats'][UaJira._clean_username(new_issue['assignee'])]['issues'].append(issue.key)

            ########
            # Completion calculations
            ########
            self._analytics_point_completion(result, new_issue, include_dev_stats=True)
            # NOTE: we don't count the points that marked as resolved but not "done"

            ########
            # Cycle time violation calculations
            ########
            self._analytics_cycle_violations(result, issue, new_issue)

            ########
            # Status counts
            ########
            self._analytics_status_counts(result, new_issue)

            result['issues'][new_issue['key']] = new_issue

        ####
        # COMPLETION STATUS
        ####
        self._analytics_completion_status(result, include_dev_stats=True)

        ####
        # SOME WARNINGS AND NOTES
        ####
        self._analytics_feedback(result)

        return result

    ######################################################################
    # Defects
    #  Methods for retrieving defect data
    ######################################################################


    ######################################################################
    # Releases
    #  Methods for retrieving release data
    ######################################################################


    ######################################################################
    # FIELDS
    ######################################################################
    def get_issue_field_from_custom_name(self, name):
        for f in self.jira.fields():
            if f['name'].lower() == name.lower():
                return f['id']
        return None

    ######################################################################
    # FILTERS
    #  Methods for gathering and reporting on JIRA filters
    ######################################################################

    ######################################################################
    # EPICS
    #  Methods for gathering and reporting on JIRA epics
    ######################################################################


    def get_associated_epic(self, issue):
        """
        Finds the epic issue associated with the given top level non-epic ticket.
        :param issue:  The issue object (in the form of a JIRA object)
        :return: Return an issue object as a dict
        """
        key = issue.fields.customfield_10008
        if key is not None:
            return self.get_issue_details(key)
        else:
            return None

    ######################################################################
    # WORKLOGS
    #  Gets worklog data based on certain input data
    ######################################################################

    def get_worklog_raw(self, start, end, team_id, username, project_key=None):
        """
        Gets worklogs as JSON for the given criteria


        :param start: The start time as an arrow object (required)
        :param end: The end time as an arrow object (required)
        :param team_id: The Tempo team ID to restrict the results to (required)
        :param username: The username to restrict the results to (optional)
        :param project_key: The project key to restrict the results to (optional)
        :return:
        """

        tempo = UaTempo(self)
        result_json = tempo.get_worklogs(start, end, team_id, username=username, project_key=project_key)
        team_info = tempo.get_team_details(team_id)

        consultants = UaJira.load_consultants()

        final_consultants = {}
        for log in result_json:
            username = log['author']['name']
            if username in consultants:
                log['author']['consultant_info'] = consultants[username]
            else:
                log['author']['consultant_info'] = None

            if username not in final_consultants:
                if username not in consultants:
                    consultants[username] = {
                        "first_name": "",
                        "last_name": "",
                        "email": "",
                        "active": "",
                        "company": "",
                        "rate": 0.0,
                        "status": "",
                        "role": "",
                        "ua": "",
                        "jira": "",
                        "github": "",
                        "start_date": None
                    }
                # keep a list of consultants in this result
                consultants[username]['total_hours'] = 0.0
                final_consultants[username] = consultants[username]

            consultants[username]['total_hours'] += float(log['timeSpentSeconds'] / 3600.0)

        return {
            "logs": result_json,
            "consultants": final_consultants,
            "tempo_team_info": team_info
        }

    @staticmethod
    def load_consultants():

        path_to_consultants_csv = os.path.join(settings.main.project.augur_base_dir,
                                               'data/consultants/engineering_consultants.csv')
        with open(path_to_consultants_csv, 'rU') as csvfile:
            reader = csv.DictReader(csvfile)
            consultants = {}
            for row in reader:
                if row['status'].lower() == 'active':
                    row['base_daily_cost'] = float(row['rate']) * 8
                    row['base_weekly_cost'] = row['base_daily_cost'] * 5
                    row['base_annual_cost'] = row['base_weekly_cost'] * 50  # assume two weeks of vacation
                else:
                    row['base_daily_cost'] = 0.0
                    row['base_weekly_cost'] = 0.0
                    row['base_annual_cost'] = 0.0

                consultants[row['jira']] = row

        return consultants

    ###########################
    # WORKLOGS
    ###########################
    @staticmethod
    def get_total_time_for_user(issue, username):
        """
        Returns the total time spent on this issue by this user in seconds
        :param issue: The issue to look at
        :param username: The username for the user to check time spent
        :return: timedelta -- The total amount of time spent on this issue by the user
        """
        total_time_spent_seconds = 0
        issue_json = issue.raw if type(issue) is Issue else issue
        if 'worklog' in issue_json:
            worklogs = issue_json['worklog']['worklogs']
            for wl in worklogs:
                if wl['author']['name'] == username:
                    total_time_spent_seconds += wl['timeSpentSeconds']

        return datetime.timedelta(seconds=total_time_spent_seconds)

    ###########################
    # DEV STATS
    ###########################


    def get_team_devs_stats(self, team, look_back_days=30):
        """
        This will get information about an entire team including individual develeper stats
        as well standard deviation in terms of point output.
        :param team: The ID of the team to get info about
        :param look_back_days: How many days to look back to pull stats.
        :return:
        """
        devs = self.get_all_developer_info()
        teams = common.teams.get_all_teams()
        team = devs['teams'][teams[team]] if teams[team] in devs['teams'] else None

        if not team:
            return None

        return_value = {
            "standard_deviation": 0,
            "devs": {}
        }

        standard_dev_list = []
        for username, dev in team['members'].iteritems():
            stats = self.get_dev_stats(username, look_back_days=look_back_days)
            return_value['devs'][username] = stats
            standard_dev_list.append(stats['recently_resolved']['total_points'])

        return_value['standard_deviation'] = common.standard_deviation(standard_dev_list)
        return return_value

    ###########################
    # TICKET CREATION/UPDATING
    ###########################
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

        assert (isinstance(outward, (str, unicode)))
        self.jira.create_issue_link(link_type, inward_key, outward_key, comment)

    def create_ticket(self, project_key, summary, description, issuetype, reporter, **kwargs):
        """
        Create the ticket with the required fields above.  The other keyword arguments can be used for other fields
           although the values must be in the correct format.
        :param project_key: A string with project key name
        :param summary: A string
        :param description: A string
        :param issuetype: A dictionary containing issuetype info (see Jira API docs)
        :param reporter: A dictionary containing reporter info  (see Jira API docs)
        :param kwargs:
        :return:
        """
        try:
            ticket = self.jira.create_issue(
                project=project_key,
                summary=summary,
                description=description,
                issuetype=issuetype
            )

            if ticket:
                # now update the remaining values (if any)
                # we can't do this earlier because assignee and reporter can't be set during creation.
                if reporter or len(kwargs) > 0:
                    ticket.update(
                        reporter=reporter,
                        **kwargs
                    )

            return ticket

        except Exception, e:
            audit.error("Failed to create ticket: %s", e.message)
            return None

    ###########################
    # USED INSTEAD OF NATIVE JIRA OBJECT'S METHOD TO ALLOW ACCESS TO REST API CALL.
    #  There was no way in the JIRA.sprints call to exclude historic sprints so
    #  I made a new one based on that implementation with only one change.
    ###########################

    def _sprints(self, boardid):
        """
        Replaces the jira module version of the by the same name to prevent historic and future sprints from being
        returned (not an option in the current implementation)
        :param boardid:
        :return:
        """
        r_json = self.jira._get_json('sprintquery/%s?includeHistoricSprints=false&includeFutureSprints=false' % boardid,
                                     base=self.jira.AGILE_BASE_URL)

        return r_json['sprints']

    def sprint_info(self, board_id, sprint_id):
        """
        Return the information about a sprint.

        :param board_id: the board retrieving issues from
        :param sprint_id: the sprint retieving issues from
        """
        return self.jira._get_json('rapid/charts/sprintreport?rapidViewId=%s&sprintId=%s' % (board_id, sprint_id),
                                   base=self.jira.AGILE_BASE_URL)

    @staticmethod
    def _analytics_feedback(result):
        notes = []
        questionable_state = False

        result["average_point_size"] = (result['total_points'] / result['ticket_count']) if result[
            'ticket_count'] else 0

        if result["percent_complete"] >= 99.0 and result['unpointed'] > 0:
            questionable_state = True
            notes.append(
                "There's a high completion rate but probably because there are some issues that are unpointed.")
        if result['unpointed'] > 8:
            notes.append("There are a high number of unpointed issues")
        if result['ticket_count'] < 3:
            notes.append("There are less than three issues in this collection")
        if result['unpointed_complete_issues'] > 0:
            notes.append("There are unpointed issues that are marked as complete")
        if not questionable_state:
            result['color'] = const.COLOR_BAD if result["percent_complete"] < 50 else \
                const.COLOR_OK if result["percent_complete"] < 75 else const.COLOR_GOOD
        else:
            result['color'] = const.COLOR_QUESTIONABLE
        result['notes'] = "<ul><li>" + "</li><li>".join(notes) + "</li></ul>"

    @staticmethod
    def _analytics_is_complete(status, resolution):
        status = status.lower()
        resolution = resolution.lower()
        return (status in common.COMPLETE_STATUSES) or \
               (status == "resolved" and resolution in common.POSITIVE_RESOLUTIONS)

    @staticmethod
    def _analytics_is_inprogress_or_open(status):
        status = status.lower()
        return UaJira._analytics_is_inprogress(status) or status == "open"

    @staticmethod
    def _analytics_is_inprogress(status):
        status = status.lower()
        return status in ["in progress", "quality review", "blocked"]

    @staticmethod
    def _analytics_is_abandoned(status, resolution):
        status = status.lower()
        resolution = resolution.lower()
        return status == "resolved" and resolution not in common.POSITIVE_RESOLUTIONS

    @staticmethod
    def _get_issue_sprints(new_issue):

        sprints = []
        sprints_info = new_issue['fields']['customfield_10007']
        now = datetime.datetime.now().replace(tzinfo=None)
        if sprints_info:
            for s in sprints_info:
                sprint_ob = common.parse_sprint_info(s)
                sprint_ob['expected_length'] = sprint_ob['endDate'] - sprint_ob['startDate']

                if sprint_ob['completeDate']:
                    sprint_ob['actual_length'] = sprint_ob['completeDate'] - sprint_ob['startDate']
                    sprint_ob['overdue'] = False
                else:
                    sprint_ob['actual_length'] = now - sprint_ob['startDate']
                    sprint_ob['overdue'] = sprint_ob['expected_length'] < sprint_ob['actual_length']

                sprints.append(sprint_ob)

        # sort by end date
        sprints.sort(key=lambda x: x['endDate'], reverse=True)

        return sprints

    @staticmethod
    def _analytics_issue_details(issue):
        points = issue.fields.customfield_10002
        new_issue = {
            'key': issue.key,
            'summary': issue.fields.summary,
            'assignee': issue.fields.assignee.name if issue.fields.assignee else"unassigned",
            'description': issue.fields.description,
            'fields': common.remove_null_fields(issue.raw['fields']),
            'points': float(points if points else 0.0),
            'status': str(issue.fields.status).lower(),
            'resolution': str(issue.fields.resolution).lower(),
        }
        return new_issue

    @staticmethod
    def _clean_username(username):
        return username.replace(".", "_")

    @staticmethod
    def _analytics_completion_status(result, include_dev_stats=True):

        # get ticket group stats
        total_points = result['complete'] + result['incomplete'] + result['abandoned']
        result["percent_complete"] = int(((result['complete'] / total_points) if total_points > 0 else 0) * 100.0)
        result['total_points'] = total_points

        # get dev specific stats
        if include_dev_stats:
            for assignee, dev in result['developer_stats'].iteritems():
                total = dev['complete'] + dev['incomplete'] + dev['abandoned']
                dev['percent_complete'] = int((dev['complete'] / total if total > 0 else 0) * 100.0)
                dev['total_points'] = total

    @staticmethod
    def _analytics_status_counts(result, new_issue):
        status = new_issue['status']
        resolution = new_issue['resolution']
        result["remaining_ticket_count"] += 1

        if status == "production":
            result["production"] += 1

        if status == "staging":
            result["staging"] += 1

        if status == "integration":
            result["integration"] += 1

        elif status == "open":
            result["open"] += 1

        elif status == "in progress":
            result["in_progress"] += 1

        elif status == "quality review":
            result["quality_review"] += 1

        elif status == "blocked":
            result["blocked"] += 1

        elif status == "resolved" and resolution in common.POSITIVE_RESOLUTIONS:
            result["resolved"] += 1
            result["remaining_ticket_count"] -= 1

        elif status == "resolved":
            result["remaining_ticket_count"] -= 1

        elif status == "closed":
            result["closed"] += 1
            result["remaining_ticket_count"] -= 1

    @staticmethod
    def get_time_in_status(issue, status):
        history_list = issue.changelog.histories
        track_time = None
        total_time = datetime.timedelta()

        for history in history_list:
            items = history.items

            for item in items:
                if item.field == 'status' and item.toString.lower() == status.lower():
                    # start status
                    track_time = parse(history.created)
                    break
                elif track_time and item.field == 'status' and item.fromString.lower() == status.lower():
                    # end status
                    total_time += (parse(history.created) - track_time)
                    break

        if track_time and not total_time:
            # In this case the issue is currently in the requested status which means we need to set the "end" time to
            #   NOW because there's no record of the *next* status to subtract from.
            total_time = common.utc_to_local(datetime.datetime.now()) - track_time

        return total_time

    @staticmethod
    def _analytics_point_completion(result, new_issue, include_dev_stats=True):
        """

        :param result:
        :param new_issue:
        :param include_dev_stats:
        """
        points = new_issue['points']
        status = new_issue['status']
        resolution = new_issue['resolution']

        if UaJira._analytics_is_complete(status, resolution):
            result["complete"] += points
            if include_dev_stats:
                result['developer_stats'][UaJira._clean_username(new_issue['assignee'])]['complete'] += points

        elif UaJira._analytics_is_abandoned(status, resolution):
            result["abandoned"] += points
            if include_dev_stats:
                result['developer_stats'][UaJira._clean_username(new_issue['assignee'])]['abandoned'] += points

        else:
            result["incomplete"] += points
            if include_dev_stats:
                result['developer_stats'][UaJira._clean_username(new_issue['assignee'])]['incomplete'] += points

        if not points:
            result['unpointed'] += 1

    @staticmethod
    def _analytics_cycle_violations(result, issue, new_issue):
        rtd = cycletimes.get_recommended_cycle_timedelta(new_issue['points'])

        new_issue['time_in_progress'] = UaJira.get_time_in_status(issue, "in progress")
        new_issue['time_blocked'] = UaJira.get_time_in_status(issue, "blocked")
        new_issue['time_quality_review'] = UaJira.get_time_in_status(issue, "quality review")
        new_issue['time_open'] = UaJira.get_time_in_status(issue, "open")
        new_issue['time_integration'] = UaJira.get_time_in_status(issue, "integration")
        new_issue['time_staging'] = UaJira.get_time_in_status(issue, "staging")
        new_issue['time_production'] = UaJira.get_time_in_status(issue, "production")

        if rtd < new_issue['time_in_progress'] and new_issue['status'].lower() == "in progress":
            cv = cycletimes.CycleViolation(key=new_issue['key'],
                                           status="in progress",
                                           summary=new_issue['summary'],
                                           time_in_status=new_issue['time_in_progress'],
                                           overage=new_issue['time_in_progress'] - rtd)

            result['inprog_cycle_violations'][new_issue['key']] = cv

        if cycletimes.CYCLE_LIMIT_BLOCKED < new_issue['time_blocked'] and new_issue['status'].lower() == "blocked":
            cv = cycletimes.CycleViolation(key=new_issue['key'], summary=new_issue['summary'],
                                           status="blocked",
                                           time_in_status=new_issue['time_blocked'],
                                           overage=new_issue['time_blocked'] - cycletimes.CYCLE_LIMIT_BLOCKED)
            result['blocked_cycle_violations'][new_issue['key']] = cv

        if cycletimes.CYCLE_LIMIT_BLOCKED < new_issue['time_quality_review'] and new_issue['status'].lower() == \
                "quality review":
            cv = cycletimes.CycleViolation(key=new_issue['key'], summary=new_issue['summary'],
                                           status="quality review",
                                           time_in_status=new_issue['time_quality_review'],
                                           overage=new_issue['time_quality_review'] - cycletimes.CYCLE_LIMIT_BLOCKED)
            result['quality_review_cycle_violations'][new_issue['key']] = cv
