import datetime
from collections import defaultdict

from dateutil.parser import parse

import augur
from augur import common
from augur.common import const, cache_store
from augur.common.timer import Timer
from augur.fetchers.fetcher import AugurDataFetcher
from augur.integrations.augurjira import projects_to_jql, project_key_from_issue_key

SPRINT_SORTBY_ENDDATE = 'enddate'


class AugurSprintDataFetcher(AugurDataFetcher):
    """
    Retrieves data associated with one or more sprints.  This class can fetch data associated with both a team and
    a sprint.  You can also specify no team in which case it returns all team data for either the current sprint or
    the last completed sprint

    Input:
        team_id: (optional) The short name (e.g. hb) for a team
        sprint_id: (optional) The ID of a sprint, a sprint object or a one of [SPRINT_LAST_COMPLETED,SPRINT_CURRENT].
                    Defaults to SPRINT_LAST_COMPLETED if none given.
        get_history: (optional) If set to true and a team_id is given then this will return all sprints for that team.
                    By default, this is false which means that it returns whatever sprint is specified in sprint_id
    """

    def __init__(self, *args, **kwargs):
        self.cache_sprints = None
        self.team_id = None
        self.get_history = None
        self.sprint_id = None
        super(AugurSprintDataFetcher, self).__init__(*args, **kwargs)

    def init_cache(self):
        self.cache = cache_store.AugurTeamSprintData(self.augurjira.mongo)
        self.cache_sprints = cache_store.AugurJiraSprintsData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        return None

    def validate_input(self, **args):
        # team id is not a required param.  If not given, then we should get sprint data for all teams
        self.team_id = args['team_id'] if 'team_id' in args else None

        # sprint id is not a required param.  If not given then we should get the last sprint completed
        self.sprint_id = args['sprint_id'] if 'sprint_id' in args else const.SPRINT_LAST_COMPLETED

        # get_history is not a required param. If not given then it defaults to False.
        self.get_history = args['get_history'] if 'get_history' in args else False

        if not self.team_id and self.sprint_id not in (const.SPRINT_LAST_COMPLETED, const.SPRINT_CURRENT):
            raise LookupError("You cannot request a specific sprint ID if you do not specify a team ID.")

        if self.get_history and 'sprint_id' in args:
            raise LookupError(
                "You specified that you want sprint history but also specified a specific sprint to retrieve.")

        if self.get_history and not self.team_id:
            raise LookupError(
                "You specified that you want sprint history but didn't specify a team to retrieve the history for.")

        return True

    @staticmethod
    def should_use_cache(sprint):
        """
        Indicates whether or not the given sprint should be refreshed from JIRA or a cached copy can be used.
        :param sprint: The sprint object
        :return:  Returns True if you can use a cached version of this sprint.
        """
        if isinstance(sprint, dict):
            closed_for_a_while = sprint['state'] == 'CLOSED' and \
                                 (sprint['completeDate'] < datetime.datetime.now() - datetime.timedelta(days=6))

            return closed_for_a_while
        else:
            return True

    def _fetch(self):
        if not self.team_id:
            # get current or last sprint for all teams
            results = []
            for team in augur.api.get_teams():
                stats = augur.api.get_abridged_team_sprint(team.id, self.sprint_id)
                results.append({
                    'team_id': team.id,
                    'success': stats is not None
                })

        elif self.get_history:
            # get the sprint history for a specific team
            sprints = self.get_detailed_sprint_list_for_team(self.team_id, limit=5)
            to_calculate = []
            separated_sprint_data = []
            for s in sprints:
                separated_sprint_data.append(s)
                to_calculate.append(s['team_sprint_data'])

            aggregate_data = self._aggregate_sprint_history_data(to_calculate)

            results = {
                'sprint_data': separated_sprint_data,
                'aggregate_data': aggregate_data
            }

        else:
            # get a single team's stats for a given sprint
            results = self.get_detailed_sprint_info_for_team(self.team_id, self.sprint_id)

        self.recent_data = results
        return results

    @staticmethod
    def _clean_detailed_sprint_info(sprint_data):
        # convert date strings to dates
        for key, value in sprint_data['sprint'].iteritems():
            if key in ['startDate', 'endDate', 'completeDate']:
                try:
                    sprint_data['sprint'][key] = parse(value)
                except ValueError:
                    sprint_data['sprint'][key] = None

    def get_detailed_sprint_info_for_team(self, team_id, sprint_id):
        """
        This will get sprint data for the the given team and sprint.  You can specify you want the current or the
        most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
        of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
        sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
        :param team_id: The ID of the team
        :param sprint_id: The ID, const, or sprint object.
        :return: Returns a sprint object
        """

        with Timer("Detailed Sprint Data") as t:

            # We either don't have anything cached or we decided not to use it.  So start from scratch by retrieving
            # the detailed sprint data from Jira
            sprint_abridged = augur.api.get_abridged_team_sprint(team_id, sprint_id)
            t.split("Retrieve abridged sprint data")

            if not sprint_abridged:
                return None

            # see if it's in the cache.  If it is, then check if it's cached in the active state.  If it is,
            #   then throw away the cached version and reload from JIRA
            team_stats = self.cache.load_sprint(sprint_abridged['id'])

            if team_stats and team_stats['team_sprint_data']['sprint']['state'] == 'CLOSED':
                return team_stats

            team_object = augur.api.get_team_by_id(team_id)
            sprint_ob = self.augurjira.sprint_info(team_object.get_agile_board_jira_id(), sprint_abridged['id'])
            t.split("Retrieve full sprint data")

            if not sprint_ob:
                return None

            # convert date strings to actual dates.
            self._clean_detailed_sprint_info(sprint_ob)
            t.split("Cleaned sprint data")

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
            projects = self.context.workflow.get_projects(key_only=True)
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
            t.split("Calculated standard deviation and point sums")

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
                t.split("Got issue data for issues added during sprint")

            if sprint_ob['contents']['issuesNotCompletedInCurrentSprint']:
                incomplete_keys = [x['key'] for x in sprint_ob['contents']['issuesNotCompletedInCurrentSprint']]

                # get all the incomplete tickets that are part of this context
                jql = "(%s) and key in ('%s')" % \
                      (projects_to_jql(self.context.workflow), "','".join(incomplete_keys))
                results = self.augurjira.execute_jql_with_analysis(jql, total_only=False, context=self.context)

                sprint_ob['contents']['issuesNotCompletedInCurrentSprint'] = results['issues'].values()
                sprint_ob['contents']['incompleteIssuesFullDetail'] = results['issues'].values()

                t.split("Got issue data for issues not completed during sprint")

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

            self.cache.update(team_stats)

        return team_stats

    @staticmethod
    def _aggregate_sprint_history_data(sprint_data):
        """
        Given a set of sprint data returned from Jira, it will augment the data with rolling averages, running
         totals, etc for all critical data.
        :param sprint_data: A list of sprint data objects
        :return: Nothing is returned.  The given data is updated.
        """

        with Timer("Sprint History Data Aggregation") as t:
            # we assume that the sprints came in descending chrono order so we reverse to be in ascending order
            asc_sprint_data = list(reversed(sprint_data))
            t.split("Reversed sprint data list")

            # so first iterate over the list in ascending order

            aggregate_sprint_data = {
                "asc_order": []
            }

            _id = 0

            for idx, one_sprint in enumerate(asc_sprint_data):

                last_sprint_id = _id

                _id = one_sprint['sprint']['id']

                # maintain sprint order but still use a dict
                aggregate_sprint_data['asc_order'].append(_id)

                # create the storage location for aggregate data (keyed on sprint id)
                if _id not in aggregate_sprint_data:
                    aggregate_sprint_data[_id] = {
                        "info": one_sprint['sprint']
                    }

                # for some reason, there is no count of the # of *points* added during a sprint.  So we calculate
                #   manually here.

                added_during_sprint_points = 0.0
                for issue_key in one_sprint['contents']['issueKeysAddedDuringSprint']:
                    added_during_sprint_points += float(common.deep_get(issue_key,
                                                                        'fields', 'customfield_10002') or 0.0)
                one_sprint['contents']['pointsAddedDuringSprintSum'] = {
                    "text": str(added_during_sprint_points),
                    "value": added_during_sprint_points
                }

                # aggregate point value fields
                point_keys = ['completedIssuesEstimateSum',
                              'issuesNotCompletedEstimateSum',
                              'puntedIssuesEstimateSum',
                              'pointsAddedDuringSprintSum']

                for key in point_keys:

                    # get the actual value (raw)
                    orig_current = one_sprint['contents'][key]['text']

                    # convert the raw value to a number
                    current = float(orig_current if orig_current != 'null' else 0)

                    if idx == 0:
                        # if the index is zero then there's nothing to compare to so the running average would
                        #   be the same as the value.
                        average = current
                        running_sum = current
                    else:
                        # Now that we have more than one, we can calculate the running average.
                        running_sum = aggregate_sprint_data[last_sprint_id][key]['running_sum'] + current
                        count = idx + 1
                        average = running_sum / count

                    aggregate_sprint_data[_id][key] = {
                        'actual': current,
                        'running_avg': average,
                        'running_sum': running_sum
                    }

                # aggregate issue counts
                issue_keys = ['completedIssues', 'issuesNotCompletedInCurrentSprint', 'puntedIssues',
                              'issueKeysAddedDuringSprint']

                for key in issue_keys:
                    current = float(len(one_sprint['contents'][key]))
                    if idx == 0:
                        average = current
                        running_sum = current
                    else:
                        count = idx + 1
                        running_sum = aggregate_sprint_data[last_sprint_id][key]['running_sum'] + current
                        average = running_sum / count

                    aggregate_sprint_data[_id][key] = {
                        'actual': current,
                        'running_avg': average,
                        'running_sum': running_sum
                    }

                t.split("Finished aggregation for sprint index %d" % idx)

        return aggregate_sprint_data

    def get_detailed_sprint_list_for_team(self, team, sort_by=SPRINT_SORTBY_ENDDATE, descending=True, limit=None):
        """
        Gets a list of sprints for the given team.  This will load from cache in some cases and get the most recent
         when it makes to do so.
        :param team: The ID of the team to retrieve sprints for.
        :return: Returns an array of sprint objects.
        """
        ua_sprints = augur.api.get_abridged_sprint_list_for_team(team, limit)
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
