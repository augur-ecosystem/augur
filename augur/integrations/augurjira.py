import datetime
import hashlib

import logging

from collections import defaultdict
from dateutil.parser import parse
from jira import JIRA, Issue
from jira.exceptions import JIRAError
from munch import Munch, munchify

from augur import api, db, const
from augur import common
from augur import settings
from augur.common import cache_store, calc_weekends, clean_detailed_sprint_info
from augur.common.timer import Timer
from augur.integrations.augurtempo import AugurTempo
from augur.integrations.objects.board import JiraBoard
from augur.integrations.objects.metrics import BoardMetrics


class TeamSprintNotFoundException(Exception):
    pass


class DeveloperNotFoundException(Exception):
    pass


def positive_resolution_jql(workflow):
    """
    Returns a JQL segment that filters based on done statuses and positive resolutions for the given workflow.
     > e.g. ((status in (resolve,closed) and resolution in ("fixed","done", "complete")
    :param workflow: The workflow object to use as a source for information about what constitutes positive resolution
    :return: Returns the JQL
    """
    done_statuses = [d.tool_issue_status_name for d in workflow.done_statuses()]
    done_resolutions = [d.tool_issue_resolution_name for d in workflow.positive_resolutions()]

    return "(status in (\"%s\") and resolution in (\"%s\"))"%('","'.join(done_statuses), '","'.join(done_resolutions))


def project_key_from_issue_key(issue_key):
    """
    Gets the project key from an issue key
    :param issue_key: The issue key to parse
    :return: Returns None if invalid issue key given.
    """
    try:
        project_key, val = issue_key.split("-")
        return project_key
    except ValueError:
        return None


def defect_filter_to_jql(defect_filters, include_issue_types=True):
    jql_list = []
    for d in defect_filters:
        if include_issue_types:
            jql_list.append("(project = %s and issuetype in ('%s'))" %
                            (d.project_key, "','".join(d.get_issue_types_as_string_list())))
        else:
            jql_list.append("(project = %s)" % d.project_key)

    return "((%s))" % ") OR (".join(jql_list)


def projects_to_jql(workflow):
    """
    Gets the projects information and returns a jql string that can be embedded directly into a larger jql
    :return: Returns a string containing the jql
    """
    keys = []
    for p in workflow.projects:
        keys.append(p.tool_project_key)

    categories = []
    for c in workflow.categories:
        categories.append(c.tool_category_name)

    jql_projects = ""
    jql_categories = ""
    if len(keys) > 0:
        jql_projects = "project in (%s)"%",".join(keys)

    if len(categories) > 0:
        jql_categories = "category in ('%s')" % "','".join(categories)

    if jql_projects and jql_categories:
        return "((%s) OR (%s))" % (jql_projects,jql_categories)
    else:
        return jql_projects if jql_projects else jql_categories


class AugurJira(object):
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
            options={"agile_rest_path":"agile"})

        self.mongo = cache_store.AugurStatsDb()
        self.general_cache = cache_store.AugurCachedResultSets(self.mongo)

        self._field_map = {}

        self._default_fields = munchify({
            "summary": None,
            "status": None,
            "priority": None,
            "parent": None,
            "resolution": None,
            "Dev Team": None,
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
            "story points": None
        })

        self._initialize_field_map()

        default_fields = {}
        for df,val in self._default_fields.iteritems():
            default_fields[df] = self.get_field_by_name(df)

        self._default_fields = munchify(default_fields)

    @property
    def default_fields(self):
        """
        Returns a dict containing the friendly name of fields as keys and jira's proper field names as values.
        :return: dict
        """
        return self._default_fields

    def get_jira_proxy(self):
        """
        Get the JIRA object that is a proxy to the JIRA instance API.
        :return:
        """
        return self.jira

    ######################################################################
    # PROJECTS, FIELDS, COMPONENTS AND VERSIONS
    #  Get project related information
    ######################################################################

    def _initialize_field_map(self):
        # if we have already stored fields, re-use
        self.fields = api.get_memory_cached_data('custom_fields')
        if not self.fields:
            # cache the fields for later
            fields = api.memory_cache_data(self.jira.fields(), 'custom_fields')
            self.fields = {f['name'].lower(): munchify(f) for f in fields }

    def get_field_by_name(self, name):
        """
        Returns the true field name of a jira field based on its friendly name
        :param jira: The JIRA object to use to retrieve field data if necessary
        :param name: The friendly name of the field
        :return: A string with the true name of a field.
        """
        if not self.fields:
            self._initialize_field_map()

        try:
            _name = name.lower()
            if _name.lower() in self.fields:
                return self.fields[_name]['id']
        except (KeyError,ValueError):
            return name

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

    def get_issue(self,key):
        issue = self.jira.issue(key)
        if issue:
            return issue.raw
        else:
            return None

    def execute_jql(self, jql, expand=None, include_changelog=False, max_results=100):
        """
        Simply a pass through to the JIRA search_issues call.
        :param include_changelog: If true, then regardless of what expand is set to, the changelog will be included.
                    Otherwise the changelog will be excluded.
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
        elif max_results > 100:
            max_results = 100

        hashed_query = hashlib.md5(jql).hexdigest()
        with Timer("Executing jql: %s" % jql):
            result = api.get_cached_data(hashed_query, override_ttl=datetime.timedelta(hours=2))
            if not result:

                if not isinstance(expand,(str,unicode)):
                    expand = ""

                if include_changelog and expand.find("changelog") == -1:
                    expand += "changelog" if expand == "" else ",changelog"
                elif not include_changelog and expand.find("changelog") >= 0:
                    expand = expand.replace("changelog", "")

                results_json = self.jira.search_issues(jql, expand=expand, maxResults=max_results, json_result=True)
                cnt = len(results_json['issues'])
                maxi = max_results
                idx = 0
                while cnt == maxi:
                    idx += maxi
                    resource = self.jira.search_issues(jql, expand=expand, maxResults=maxi, json_result=True, startAt=idx)
                    results_json['issues'].extend(resource['issues'])
                    cnt = len(resource['issues'])

                issues_json = [common.clean_issue(r) for r in results_json['issues']]

                if len(issues_json) < 100:
                    api.cache_data({
                        "data": issues_json
                    }, hashed_query)
                return issues_json
            else:
                return result[0]['data']

    def execute_jql_with_analysis(self, query, context=None, total_only=False):
        """
        Returns an object containing completed stories, incomplete stories and the percent complete
        :param total_only:
        :param context: The context associated with the current request.
        :param query: The JQL to return the tickets to get the stats for
        :return: Return a dict with the following keys: complete, incomplete, total_points,percent_complete
        """

        if not context:
            context = api.get_default_context()

        assert context

        issues = self.execute_jql(query, include_changelog=(total_only is False))

        # Initialize the general analytics
        result = {
            "ticket_count": len(issues),
            "remaining_ticket_count": 0,
            "unpointed": 0.0,
            'developer_stats': {},
            'issues': {},
        }

        # Initialize the status counters
        result.update({AugurJira._status_to_dict_key(x): 0 for x in context.workflow.statuses})

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

            if context.workflow.is_resolved(status, resolution):
                result["complete"] += points
                result['developer_stats'][assignee_cleaned ]['complete'] += points

            elif context.workflow.is_abandoned(status, resolution):
                result["abandoned"] += points
                result['developer_stats'][assignee_cleaned]['abandoned'] += points

            else:
                result["incomplete"] += points
                result['developer_stats'][assignee_cleaned ]['incomplete'] += points

            if not points and not context.workflow.is_abandoned(status, resolution):
                result['unpointed'] += 1

            ########
            # Times in Status
            #########
            if not total_only:

                # initialize all the keys for stats
                total_time_to_complete = 0
                for s in context.workflow.in_progress_statuses():
                    total_status_str_prepped = "time_%s" % AugurJira._status_to_dict_key(s)
                    start_status_str_prepped = "start_time_%s" % AugurJira._status_to_dict_key(s)
                    end_status_str_prepped = "end_time_%s" % AugurJira._status_to_dict_key(s)
                    timing = AugurJira.get_issue_status_timing_info(issue, s)
                    total_time_to_complete += timing['total_time'].total_seconds()
                    issue[total_status_str_prepped] = timing['total_time']
                    issue[start_status_str_prepped] = timing['start_time']
                    issue[end_status_str_prepped] = timing['end_time']

                issue['total_time_to_complete'] = datetime.timedelta(seconds=total_time_to_complete)

            ########
            # Status counts
            ########
            status_as_key = AugurJira._status_to_dict_key(issue['status'])
            if status_as_key not in result:
                result[status_as_key] = 0
            result[status_as_key] += 1

            if not context.workflow.is_resolved(issue['status'], issue['resolution']):
                result['remaining_ticket_count'] += 1

            if not total_only:
                result['issues'][issue['key']] = issue

        if total_only:
            result.pop('issues')

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
            return self.get_issue(key)
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

        staff = {c.jira_username: c for c in api.get_all_staff(context=None)}
        final_consultants = {}

        for log in result_json:
            username = log['author']['name']
            staff_member = staff[username] if username in staff else None

            if staff_member:
                log['author']['consultant_info'] = staff_member.to_dict()
                final_consultants[username] = staff_member.to_dict()
            else:
                log['author']['consultant_info'] = {}
                final_consultants[username] = log['author']['consultant_info'] or {}

            if 'total_hours' not in final_consultants:
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

    def get_team_sprints_simple(self, team_id, limit=None):
        """
        Gets a list of sprints for the given team.  Will always load this from Jira.  It will also add some data. The
        list is returned in sequence order which is usually the order in which the sprints occured in time.
        :param team_id: The ID of the team to retrieve sprints for.
        :param limit: The number of sprints back to go (limit=5 would mean only the last 5 sprints)
        :return: Returns an array of sprint objects.
        """

        team_ob = api.get_team_by_id(team_id)
        if team_ob.agile_board:
            try:
                team_sprints_abridged = self.get_sprints_from_board(team_ob.agile_board.jira_id)
            except JIRAError, e:
                if e.status_code == 404:
                    self.logger.error("Could not find the Agile Board with ID %d"%team_ob.agile_board.jira_id)
                    team_sprints_abridged = []
                else:
                    raise e
        else:
            team_sprints_abridged = []
            self.logger.warning("No agile board has been defined for this team")

        # the initial list can contain sprints from other boards in cases where tickets spent time on
        # both boards.  So we filter out any that do not belong to the team.
        if team_sprints_abridged:
            filtered_sprints = [sprint for sprint in team_sprints_abridged if common.sprint_belongs_to_team(sprint, team_id)]
            filtered_sorted_list = sorted(filtered_sprints, key=lambda k: k['sequence'])
        else:
            filtered_sorted_list = []

        if limit:
            return filtered_sorted_list[-limit:]
        else:
            return filtered_sorted_list

    def get_sprints_by_team(self, team_id, sort_by=const.SPRINT_SORTBY_ENDDATE, descending=True, limit=None):
        """
        This returns detailed information about each sprint associated with a team.  The team must have an
        agile board associated it.
        :param team_id: The ID of the team to retrieve sprints for.
        :return: Returns an array of sprint objects.
        """
        ua_sprints = augur.api.get_abridged_sprint_list_for_team(team_id, limit)
        sprintdict_list = []

        for s in ua_sprints:
            # get_detailed... will handle caching
            sprint_ob = self.get_detailed_sprint_info_for_team(team, s['id'])

            if sprint_ob: sprintdict_list.append(sprint_ob)

        def sort_by_end_date(cmp1, cmp2):
            return -1 if cmp1['team_sprint_data']['sprint']['endDate'] < cmp2['team_sprint_data']['sprint'][
                'endDate'] else 1

        SORTKEYS = {
            SPRINT_SORTBY_ENDDATE: sort_by_end_date
        }

        if sort_by in SORTKEYS:
            return sorted(sprintdict_list, SORTKEYS[sort_by], reverse=descending)
        else:
            return sprintdict_list

    def get_sprints_by_board(self, board_id, sort_by=const.SPRINT_SORTBY_ENDDATE, descending=True, limit=None):

        ua_sprints = augur.api.get_abridged_sprint_list_for_team(team_id, limit)
        sprintdict_list = []

        for s in ua_sprints:
            # get_detailed... will handle caching
            sprint_ob = self.get_detailed_sprint_info_for_team(team, s['id'])

            if sprint_ob: sprintdict_list.append(sprint_ob)

        def sort_by_end_date(cmp1, cmp2):
            return -1 if cmp1['team_sprint_data']['sprint']['endDate'] < cmp2['team_sprint_data']['sprint'][
                'endDate'] else 1

        SORTKEYS = {
            SPRINT_SORTBY_ENDDATE: sort_by_end_date
        }

        if sort_by in SORTKEYS:
            return sorted(sprintdict_list, SORTKEYS[sort_by], reverse=descending)
        else:
            return sprintdict_list

    def get_sprint_simple_by_id(self, sprint_id, team_id):
        """
        Retrieves the sprint object identified by the given ID.  If the given object
        is a sprint object already it will be returned.  Otherwise, the sprint ID will be looked up in JIRA
        :param sprint_id: Either one of the SPRINT_XXX consts, an ID, or a sprint object.
        :param team_id: (optional) The ID of the team only required if the sprint ID given is one of the SPRINT_
                                    constants
        :return: Returns a sprint object or throws a TeamSprintNotFoundException
        """

        def get_key(item):
            return item['sequence']

        sprints = self.get_team_sprints_simple(team_id)
        sprints = sorted(sprints, key=get_key, reverse=True)

        sprint = None

        if sprint_id == const.SPRINT_LAST_COMPLETED:
            # Note: get_issue_sprints returns results that are sorted in descending order by end date
            for s in sprints:
                if s['state'] == 'FUTURE':
                    continue
                if s['state'] == 'ACTIVE' and not 'overdue' in s:
                    # this is an active sprint that is not completed yet.
                    continue
                elif s['state'] == 'ACTIVE' and 'overdue' in s:
                    # this is a sprint that should have been marked complete but hasn't been yet
                    sprint = s
                elif s['state'] == 'CLOSED':
                    # this is the first sprint that is not marked as active so we can assume that it's the last
                    # completed sprint.
                    sprint = s
                    break

        elif sprint_id == const.SPRINT_BEFORE_LAST_COMPLETED:
            # Note: get_issue_sprints returns results that are sorted in descending order by end date
            sprint_last = None
            sprint_before_last = None
            for s in sprints:
                if s['state'] == 'CLOSED':
                    # this is the first sprint that is not marked as active so we can assume that it's the last
                    # completed sprint.
                    if not sprint_last:
                        # so we've gotten to the most recently closed one but we're looking for the one before that.
                        sprint_last = s
                    else:
                        # this is the one before the last one.
                        sprint_before_last = s
                        break

            sprint = sprint_before_last

        elif sprint_id == const.SPRINT_CURRENT:
            # Note: get_issue_sprints returns results that are sorted in descending order by end date
            for s in sprints:
                if s['state'] == 'ACTIVE':
                    # this is an active sprint that is not completed yet.
                    sprint = s
                    break
                else:
                    continue

        elif isinstance(sprint_id, dict):
            # a sprint object was given instead of just an id
            sprint = sprint_id
        else:
            # Note: get_issue_sprints returns results that are sorted in descending order by end date
            for s in sprints:
                if s['id'] == sprint_id:
                    sprint = s
                    break
                else:
                    continue

        return sprint

    def get_sprint_by_id(self, sprint_id, context, team_id=None):
        """
        This will get sprint data for the the given sprint.  You can specify you want the current or the
        most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
        of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
        sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
        :param sprint_id: The ID, const, or sprint object.
        :param team_id: The ID of the team (required if the sprint ID is one of the SPRINT_ constants.
        :return: Returns a sprint object
        """

        # We either don't have anything cached or we decided not to use it.  So start from scratch by retrieving
        # the detailed sprint data from Jira
        sprint_abridged = self.get_sprint_simple_by_id(sprint_id, team_id)

        if not sprint_abridged:
            return None

        team_object = api.get_team_by_id(team_id)
        sprint_ob = self.sprint_info(team_object.get_agile_board_jira_id(), sprint_abridged['id'])

        if not sprint_ob:
            return None

        # convert date strings to actual dates.
        clean_detailed_sprint_info(sprint_ob)

        now = datetime.datetime.now().replace(tzinfo=None)

        if sprint_ob['sprint']['state'] == 'ACTIVE':
            sprint_ob['actual_length'] = now - sprint_ob['sprint']['startDate']
            sprint_ob['overdue'] = sprint_ob['actual_length'] > datetime.timedelta(days=16)
        else:
            sprint_ob['actual_length'] = sprint_ob['sprint']['completeDate'] - sprint_ob['sprint']['startDate']

            # not applicable if the sprint is complete or happens in the future.
            sprint_ob['overdue'] = False

        # Get point completion standard deviation
        standard_dev_map = defaultdict(int)
        total_completed_points = 0
        projects = context.workflow.get_projects(key_only=True)
        for issue in sprint_ob['contents']['completedIssues']:

            # ignore any issues that are not part of the context.
            if project_key_from_issue_key(issue['key']).upper() not in projects:
                continue

            points = issue.get('currentEstimateStatistic', {}).get('statFieldValue', {'value': 0}).get('value', 0)
            total_completed_points += points
            if 'assignee' in issue:
                standard_dev_map[issue['assignee']] += points
            else:
                print "Found a completed issue without an assignee - %s" % issue['key']

        std_dev = common.standard_deviation(standard_dev_map.values())

        # Replace "null" with 0
        for val in ('completedIssuesEstimateSum', 'issuesNotCompletedEstimateSum', 'puntedIssuesEstimateSum'):
            if val in sprint_ob['contents'] and isinstance(sprint_ob['contents'][val], dict) and \
                    sprint_ob['contents'][val]['text'] == 'null':
                sprint_ob['contents'][val]['text'] = "0"

        if sprint_ob['contents']['issueKeysAddedDuringSprint']:

            # get issues that were added during the sprint that are part of this context.
            results = self.augurjira.execute_jql("(%s) and key in ('%s')" %
                                                 (projects_to_jql(self.context.workflow),
                                                  "','".join(sprint_ob['contents']['issueKeysAddedDuringSprint'].keys())))

            sprint_ob['contents']['issueKeysAddedDuringSprint'] = results

        if sprint_ob['contents']['issuesNotCompletedInCurrentSprint']:
            incomplete_keys = [x['key'] for x in sprint_ob['contents']['issuesNotCompletedInCurrentSprint']]

            # get all the incomplete tickets that are part of this context
            jql = "(%s) and key in ('%s')" % \
                  (projects_to_jql(self.context.workflow), "','".join(incomplete_keys))
            results = self.augurjira.execute_jql_with_analysis(jql, total_only=False, context=self.context)

            sprint_ob['contents']['issuesNotCompletedInCurrentSprint'] = results['issues'].values()
            sprint_ob['contents']['incompleteIssuesFullDetail'] = results['issues'].values()

        team_stats = {
            "team_name": team_object.name,
            "team_id": team_id,
            "sprint_id": sprint_id,
            "board_id": team_object.agile_board.jira_id,
            "std_dev": std_dev,
            "contributing_devs": standard_dev_map.keys(),
            "team_sprint_data": sprint_ob,
            "total_completed_points": total_completed_points
        }

        return team_stats

    def get_board_backlog_metrics(self, board_id, context):

        board = JiraBoard(self, board_id=board_id)
        if board.load():
            metrics = BoardMetrics(context,board)
            return metrics.backlog_analysis()
        else:
            return None

