import datetime

import arrow

import augur.api
from augur import common
from augur.common import const, teams, cache_store
from augur.fetchers.fetcher import UaDataFetcher
from augur.fetchers.release import UaJiraRelease


class UaJiraEngineeringReport(UaDataFetcher):
    def init_cache(self):
        self.cache = cache_store.UaEngineeringReportData(self.uajira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_data(self.week_number)
        return self.recent_data

    def validate_input(self, **args):
        if 'week_number' not in args:
            raise LookupError("You must specify a week_number as input to this data fetcher")
        else:
            self.week_number = args['week_number']

        return True

    def _get_most_recent_completed_sprints(self):

        sprints = {}
        for team_id in teams.get_all_teams().keys():
            sprints[team_id] = {
                "last": augur.api.get_sprint_info_for_team(team_id, const.SPRINT_LAST_COMPLETED),
                "before_last": augur.api.get_sprint_info_for_team(team_id, const.SPRINT_BEFORE_LAST_COMPLETED)
            }

        return sprints

    def _get_aggregate_metrics(self):

        open_defect_metrics = self._get_defect_metrics("project=DEF and status=\"open\"", self.staff)
        resolved_defect_metrics = self._get_defect_metrics("project=DEF and status=\"resolved\" and resolution in (%s)"
                                                           % ",".join(common.POSITIVE_RESOLUTIONS), self.staff, True)

        return {
            "open": open_defect_metrics,
            "resolved": resolved_defect_metrics
        }

    def _get_defect_metrics(self, jql, devs, count_only=False):
        defects = self.uajira.execute_jql(jql, max_results=("0" if count_only else 1000))
        results = {
            "total": defects.total,
            "priorities": {},
            "severities": {},
            "devs": devs,
            "dev_defect_ratio": defects.total / len(devs['devs'])
        }

        if not count_only:
            for defect in defects:
                if defect.fields.customfield_10300:
                    severity = defect.fields.customfield_10300.value
                else:
                    severity = "Not Given"

                if defect.fields.priority:
                    priority = defect.fields.priority.name
                else:
                    priority = "Not Given"

                if priority not in results['priorities']:
                    results['priorities'][priority] = []
                if severity not in results['severities']:
                    results['severities'][severity] = []

                results['priorities'][priority].append(common.simplify_issue(defect))
                results['severities'][severity].append(common.simplify_issue(defect))

        return results

    @staticmethod
    def _get_start_date_from_week_number(week_number):
        year = datetime.datetime.now().year
        conversion_str = "%d-W%d" % (year, int(week_number))
        return datetime.datetime.strptime(conversion_str + '-1', "%Y-W%W-%w")

    def _get_defect_data_by_week(self, week_count):
        start_date = self._get_start_date_from_week_number(self.week_number)
        weeks = []
        for w in range(week_count):
            start, end = common.get_week_range(start_date)
            start_str = arrow.get(start).floor('day').format("YYYY/MM/DD HH:mm")
            end_str = arrow.get(end).ceil('day').format("YYYY/MM/DD HH:mm")

            defects = self.uajira.execute_jql("project in (ENG, DEF) AND issuetype = Bug "
                                              "AND created >= '%s' AND created <= '%s' "
                                              "ORDER BY severity desc,created DESC" % (start_str, end_str))

            resolved_this_week = self.uajira.execute_jql("project = def and  resolution in "
                                                         "(fixed,done,deployed) and status changed "
                                                         "to resolved during ('%s','%s')" % (start_str, end_str))

            resolved_this_week_count = len(resolved_this_week)
            opened_this_week_count = len(defects)
            dev_defect_ratio = float(float(len(defects)) / float(len(self.staff['devs'])))

            weeks.append({
                "start": start_str,
                "end": end_str,
                "dev_defect_ratio": dev_defect_ratio,
                "opened_this_week_count": opened_this_week_count,
                "resolved_this_week_count": resolved_this_week_count,
                "defects": [d.raw for d in defects]
            })

            # move it back to the previous week.
            start_date = start - datetime.timedelta(days=1)

        return weeks

    def _get_active_epics_from_sprints(self, sprints):

        epics = {}

        def update_epic_data(epic_inner, issue_inner):

            if 'currentEstimateStatistic' not in issue_inner:
                # this is the full blow issue_inner dict
                points = issue_inner['fields']['customfield_10002'] if 'customfield_10002' in issue_inner[
                    'fields'] else 0.0
                status = issue_inner['fields']['status']['name']
                issue_type = issue_inner['fields']['issuetype']
                done = issue_inner[
                           'resolution'] in common.POSITIVE_RESOLUTIONS and status.lower() in common.COMPLETE_STATUSES
            else:
                # this is the abbreviated form of the issue_inner dict (returned by sprint endpoints)
                points = float(issue_inner['currentEstimateStatistic']['statFieldValue']['value']
                               if 'value' in issue_inner['currentEstimateStatistic']['statFieldValue'] else 0.0)
                status = issue_inner['status']['name']
                issue_type = issue_inner['typeName']
                done = issue_inner['done']

            epic_key = common.deep_get(issue_inner, 'epicField', 'epicKey') or "NONE"
            if epic_key not in epic_inner:
                epic_inner[epic_key] = {
                    "key": epic_key,
                    "text": issue_inner['epicField']['text'] if epic_key != "NONE" else "No epic assigned",
                    "completed_points": 0.0,
                    "incomplete_points": 0.0,
                    "total_points": 0.0,
                    "issues": [],
                    "devs": [],
                    "teams": []
                }

            assignee = issue_inner['assigneeKey'] if 'assigneeKey' in issue_inner else ""
            epic_inner[epic_key]['issues'].append({
                "key": issue_inner['key'],
                "summary": issue_inner['summary'],
                "assignee": assignee,
                "status": status,
                "issue_type": issue_type,
                "points": points
            })

            if assignee:
                if assignee not in epic_inner[epic_key]["devs"]:
                    epic_inner[epic_key]["devs"].append(assignee)

                if assignee in self.staff['devs']:
                    team = self.staff['devs'][assignee]["team_name"]
                    if team not in epic_inner[epic_key]["teams"]:
                        epic_inner[epic_key]["teams"].append(team)

            if done:
                epic_inner[epic_key]['completed_points'] += points
            else:
                epic_inner[epic_key]['incomplete_points'] += points

            epic_inner[epic_key]['total_points'] += points

        for team_id, info in sprints.iteritems():
            sprint_data = info['last']
            for issue in sprint_data['team_sprint_data']['contents']['completedIssues']:
                update_epic_data(epics, issue)

            for issue in sprint_data['team_sprint_data']['contents']['issuesNotCompletedInCurrentSprint']:
                update_epic_data(epics, issue)

        return epics

    def _fetch(self):

        # get developer and team data
        self.staff = augur.api.get_all_developer_info()

        # get data for the most recent sprint for all teams
        sprints = self._get_most_recent_completed_sprints()

        # get data about the epics that were worked on during the sprint
        active_epics = self._get_active_epics_from_sprints(sprints)

        for name, team in self.staff['teams'].iteritems():
            members = team['members'].values()
            team['total_consultants'] = reduce(lambda x, y: x + 1 if y['is_consultant'] else x, members, 0)
            team['total_fulltime'] = reduce(lambda x, y: x + 1 if not y['is_consultant'] else x, members, 0)
            team_id = team['id']
            if team_id in sprints and 'last' in sprints[team_id]:
                team['avg_pts_per_engineer'] = sprints[team_id]['last']['total_completed_points'] / len(team['members'])

        # get defect data for the given week
        defects = {
            "weekly_metrics": self._get_defect_data_by_week(2),
            "aggregate_metrics": self._get_aggregate_metrics()
        }

        start, end = common.get_week_range(self._get_start_date_from_week_number(self.week_number))
        fetcher = UaJiraRelease(self.uajira)
        releases = fetcher.fetch(start=start, end=end)

        results = {
            'epics': active_epics,
            'staff': self.staff,
            'sprint': sprints,
            'defects': defects,
            'week_number': self.week_number,
            'start': start,
            'end': end,
            'releases': releases
        }

        return self.cache_data(results)
