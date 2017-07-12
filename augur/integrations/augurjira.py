import datetime
import hashlib

import logging
from dateutil.parser import parse
from jira import JIRA, Issue, Project

from augur import api
from augur import common
from augur import settings
from augur.common import cache_store
from augur.common.timer import Timer
from augur.integrations.augurtempo import AugurTempo
from augur.models import AugurModel


class TeamSprintNotFoundException(Exception):
    pass


class DeveloperNotFoundException(Exception):
    pass


class AugurJira(object):
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

    def get_jira_proxy(self):
        """
        Get the JIRA object that is a proxy to the JIRA instance API.
        :return:
        """
        return self.jira

    ######################################################################
    # PROJECTS, COMPONENTS AND VERSIONS
    #  Get project related information
    ######################################################################

    def get_projects(self):
        """Get a list of project Resources from the server visible to the current authenticated user."""
        return self.jira._get_json('project', {"expand": "category"})

    def get_projects_with_category(self, category):
        """
        Finds all the projects that have the category given
        :param category: A string containing the project category name or a list of category strings
        :return: An array of project dictionaries.
        """
        if isinstance(category,(str,unicode)):
            category = [category]

        category = [c.lower() for c in category]
        projects = self.get_projects()

        return [p for p in
                filter(lambda x: 'projectCategory' in x and x['projectCategory']['name'].lower() in category,
                       projects)]

    def get_projects_with_key(self, key):
        """
        Finds all the projects that have the key (or keys) given
        :param category: A string containing the project key or a list of ketys
        :return: An array of project dictionaries.
        """
        if isinstance(key,(str,unicode)):
            key = [key]

        key = [c.lower() for c in key]
        projects = self.get_projects()

        return [p for p in filter(lambda x: x['key'].lower() in key, projects)]

    def get_project_components(self, project):
        """
        Simply returns all the components associated with the given project.
        :param project:  The project key (e.g. ENG)
        :return: Returns the component objects as returned by the JIRA object.
        """
        return self.jira.project_components(project)

    def get_group_data(self, starts_with="Team "):
        return self.jira.groups(starts_with)

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

        hashed_query = hashlib.md5(jql).hexdigest()
        with Timer("Executing jql: %s" % jql):
            result = api.get_cached_data(hashed_query, override_ttl=datetime.timedelta(hours=2))
            if not result:
                if not expand:
                    expand = "changelog"
                else:
                    expand += ",changelog"

                result = self.jira.search_issues(jql, expand=expand, maxResults=max_results)
                results_json = [common.clean_issue(r.raw) for r in result]

                if len(results_json) < 100:
                    api.cache_data({
                        "data": results_json
                    }, hashed_query)
                return results_json
            else:
                return result[0]['data']

    def execute_jql_with_analysis(self, query, group_id=None):
        """
        Returns an object containing completed stories, incomplete stories and the percent complete
        :param group_id: The ID of the group to associate with the analysis (required for status counters and
                workflow specific statistics)
        :param query: The JQL to return the tickets to get the stats for
        :return: Return a dict with the following keys: complete, incomplete, total_points,percent_complete
        """
        workflow = AugurJira._get_workflow_from_group_id(group_id)

        issues = self.execute_jql(query)

        # Initialize the general analytics
        result = {
            "ticket_count": len(issues),
            "remaining_ticket_count": 0,
            "unpointed": 0.0,
            'developer_stats': {},
            'issues': {},
        }

        # Initialize the status counters
        result.update({AugurJira._status_to_dict_key(x): 0 for x in workflow.statuses})

        # Initialize point totals
        result.update({
            "complete": 0.0,
            "incomplete": 0.0,
            "total_points": 0.0,
            "percent_complete": 0,
            "abandoned": 0.0,
        })

        for issue in issues:
            assignee_cleaned = AugurJira._clean_username(issue['assignee'])

            if issue['assignee'] not in result['developer_stats']:
                result['developer_stats'][assignee_cleaned] = {
                    "info": common.deep_get(issue, "assignee") or {},
                    "complete": 0,
                    "incomplete": 0,
                    "abandoned": 0,
                    "percent_complete": 0,
                    "issues": []
                }

            # Add this issue to the list of issues for the user
            result['developer_stats'][AugurJira._clean_username(issue['assignee'])]['issues'].append(issue['key'])

            ########
            # Point Counters
            ########
            points = issue['points']
            status = issue['status']
            resolution = issue['resolution']

            if workflow.is_resolved(status, resolution):
                result["complete"] += points
                result['developer_stats'][assignee_cleaned ]['complete'] += points

            elif workflow.is_abandoned(status, resolution):
                result["abandoned"] += points
                result['developer_stats'][assignee_cleaned]['abandoned'] += points

            else:
                result["incomplete"] += points
                result['developer_stats'][assignee_cleaned ]['incomplete'] += points

            if not points:
                result['unpointed'] += 1

            ########
            # Times in Status
            #########
            for s in workflow.in_progress_statuses:
                status_str_prepped = "time_%s" % AugurJira._status_to_dict_key(s)
                issue[status_str_prepped]= AugurJira.get_time_in_status(issue, s)

            ########
            # Status counts
            ########
            status_as_key = AugurJira._status_to_dict_key(issue['status'])
            if status_as_key not in result:
                result[status_as_key] = 0
            result[status_as_key] += 1

            if not workflow.is_resolved(issue['status'], issue['resolution']):
                result['remaining_ticket_count'] += 1

            result['issues'][issue['key']] = issue

        ####
        # COMPLETION STATUS
        ####
        total_points = result['complete'] + result['incomplete'] + result['abandoned']
        result["percent_complete"] = int(((result['complete'] / total_points) if total_points > 0 else 0) * 100.0)
        result['total_points'] = total_points

        # get dev specific stats
        for assignee, dev in result['developer_stats'].iteritems():
            total = dev['complete'] + dev['incomplete'] + dev['abandoned']
            dev['percent_complete'] = int((dev['complete'] / total if total > 0 else 0) * 100.0)
            dev['total_points'] = total

        return result

    ######################################################################
    # EPICS
    #  Methods for gathering and reporting on JIRA epics
    ######################################################################
    def get_associated_epic(self, issue):
        """
        Finds the epic issue associated with the given top level non-epic ticket.
        :param issue:  The issue object (in the form of a dict)
        :return: Return an issue object as a dict
        """
        key = issue['fields'][api.get_issue_field_from_custom_name('Epic Link')]
        if key is not None:
            from augur.fetchers import UaIssueDataFetcher
            fetcher = UaIssueDataFetcher(uajira=self)
            return fetcher.fetch(issue_key=key)
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

        tempo = AugurTempo(self)
        result_json = tempo.get_worklogs(start, end, team_id, username=username, project_key=project_key)
        team_info = tempo.get_team_details(team_id)

        consultants = api.get_consultants()

        final_consultants = {}

        for log in result_json:
            username = log['author']['name']
            staff_member = AugurModel.find_model_in_collection(consultants, "jira_username", username)
            log['author']['consultant_info'] = staff_member.get_props_as_dict() if staff_member else None

            if username not in final_consultants:
                final_consultants[username] = log['author']['consultant_info'] or {}
                final_consultants[username]['total_hours'] = 0.0

            final_consultants[username]['total_hours'] += float(log['timeSpentSeconds'] / 3600.0)

        return {
            "logs": result_json,
            "consultants": final_consultants,
            "tempo_team_info": team_info
        }

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
                except Exception,e:
                    self.logger.warning("Ticket was created but not updated due to exception: %s"%e.message)

                try:
                    if watchers and isinstance(watchers, (list, tuple)):
                        [self.jira.add_watcher(ticket, w) for w in watchers]
                except Exception,e:
                    self.logger.warning("Unable to add watcher(s) due to exception: %s"%e.message)

            return ticket

        except Exception, e:
            self.logger.error("Failed to create ticket: %s", e.message)
            return None

    def delete_ticket(self,key):
        """
        Deletes a ticket with the given key
        :param key: The key of the ticket to delete
        :return: Returns True if the ticket was deleted, False otherwise.
        """
        issue = self.jira.issue(key)
        if issue:
            issue.delete(True)
            return True
        else:
            return False

    ###########################
    # USED INSTEAD OF NATIVE JIRA OBJECT'S METHOD TO ALLOW ACCESS TO REST API CALL.
    #  There was no way in the JIRA.sprints call to exclude historic sprints so
    #  I made a new one based on that implementation with only one change.
    ###########################

    def get_sprints_from_board(self, boardid):
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
    def _clean_username(username):
        return username.replace(".", "_")


    @staticmethod
    def get_time_in_status(issue, status):
        """
        Gets a single tickets time in a given status.  Calculates by looking at the history for the issue
        and adding up all the time that the ticket was in the given status.
        :param issue: The ticket in dictionary form
        :param status: The status string to look for.
        :return: Returns the datetime.timedelta time in status.
        """
        history_list = issue['changelog']['histories']
        track_time = None
        total_time = datetime.timedelta()

        for history in history_list:
            items = history['items']

            for item in items:
                if item['field'] == 'status' and item['toString'].lower() == status.lower():
                    # start status
                    track_time = parse(history['created'])
                    break
                elif track_time and item['field'] == 'status' and item['fromString'].lower() == status.lower():
                    # end status
                    total_time += (parse(history['created']) - track_time)
                    break

        if track_time and not total_time:
            # In this case the issue is currently in the requested status which means we need to set the "end" time to
            #   NOW because there's no record of the *next* status to subtract from.
            total_time = common.utc_to_local(datetime.datetime.now()) - track_time

        return total_time

    @staticmethod
    def _get_workflow_from_group_id(group_id):
        if not group_id:
            group_id = 'b2c'
        group = api.get_group(group_id)
        if not group:
            group = api.get_group('b2c')

        workflow = group.get_workflow()
        if not workflow:
            raise LookupError("Unable to find workflow for current group")

        return workflow

    @staticmethod
    def _status_to_dict_key(status):
        return "%s"%status.lower().replace(" ","_")
