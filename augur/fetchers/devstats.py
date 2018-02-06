import augur.api
import augur.common
from augur.common import cache_store
from augur.integrations import augurjira
from augur.integrations.augurjira import DeveloperNotFoundException
from augur.fetchers.fetcher import AugurDataFetcher


class AugurDevStatsDataFetcher(AugurDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.AugurDeveloperData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_user(self.username, self.look_back_days, context=self.context)
        return self.recent_data

    def validate_input(self, **args):
        if 'username' not in args:
            raise LookupError("You must specify a username as input to this data fetcher")
        else:
            self.username = args['username']

        self.look_back_days = args['look_back_days'] if 'look_back_days' in args else 60

        return True

    def _fetch(self):
        # in this case we try to update the data in the data store since there are more possibilities
        # and we don't have a cron job that updates the data in the background.  So it has to be updated by
        # visits to the page with the same user and the same look back days

        devs = augur.api.get_all_developer_info()
        user_details = None
        team_details = None
        for team, team_info in devs['teams'].iteritems():
            for user, user_info in team_info['members'].iteritems():
                if user == self.username:
                    # no need to keep going if we found the user
                    team_details = team_info
                    user_details = user_info
                    break

            # no need to keep going if we found the team
            if user_details:
                break

        if not user_details:
            raise DeveloperNotFoundException()

        workflow = self.context.workflow

        project_jql = augur.common.projects_to_jql(workflow)
        resolved_status_jql = "('%s')"%"','".join([s.tool_issue_status_name for s in workflow.done_statuses()])
        results2 = self.augurjira.execute_jql_with_analysis(
            "%s and assignee='%s' and status not in %s" %
            (project_jql, self.username, resolved_status_jql), context=self.context)

        results1 = self.augurjira.execute_jql_with_analysis(
            "%s and assignee='%s' and status changed to \"Resolved\" after endOfDay(-%dd)"
            % (project_jql, self.username, self.look_back_days), context=self.context)

        results3 = self.augurjira.execute_jql_with_analysis(
            "%s and assignee='%s'" % (project_jql, self.username), total_only=True,context=self.context)

        for key, issue in results1['issues'].iteritems():
            issue['totalTimeSpentByUser'] = self.augurjira.get_total_time_for_user(issue, self.username)

        for key, issue in results2['issues'].iteritems():
            issue['totalTimeSpentByUser'] = self.augurjira.get_total_time_for_user(issue, self.username)

        dev_info = {
            'username': self.username,
            'user_details': user_details,
            'team_details': team_details,
            'recently_resolved': results1,
            'currently_unresolved': results2,
            'totals_over_all_time': results3,
            'num_days': self.look_back_days
        }

        return self.cache_data(dev_info)
