import augur.api
from augur import common
from augur.common import cache_store, deep_get
from augur.fetchers.fetcher import AugurDataFetcher


class AugurOrgStatsFetcher(AugurDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.AugurJiraOrgData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load(context=self.context)
        if isinstance(self.recent_data, list) and len(self.recent_data) > 0:
            self.recent_data = self.recent_data[0]

        return self.recent_data

    def validate_input(self, **args):
        return True

    def _fetch(self):

        # We compose a single query to retrieve all resolved tickets by all assignees and iterate
        #   over them in memory to reduce the number of calls to jira

        data = augur.api.get_all_developer_info()

        jql = "%s and status changed to %s after startOfDay(-2M) and " \
              "status = 'resolved' and resolution in %s order by assignee desc, updated desc" \
              % (self.workflow.get_projects_jql(),
                 self.workflow.get_resolved_statuses_jql(),
                 self.workflow.get_positive_resolutions_jql())

        issues = self.augurjira.execute_jql(jql, max_results=1000)
        point_value_field = augur.api.get_issue_field_from_custom_name('Story Points')
        for issue in issues:

            # needs to have a point value and an assignee to proceed
            assignee_name = deep_get(issue,'fields','assignee','name')
            if issue['fields'][point_value_field] and assignee_name:
                if assignee_name in data['devs']:
                    # the username is in our list of developers so we can update with info
                    if 'total_points' not in data['devs'][assignee_name]:
                        data['devs'][assignee_name]['total_points'] = 0.0
                    data['devs'][assignee_name]['total_points'] += issue['fields'][point_value_field]

        return self.cache_data(data)
