import augur.api
from augur import common
from augur.common import cache_store
from augur.fetchers.fetcher import UaDataFetcher


class UaJiraOrgStatsFetcher(UaDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraOrgData(self.uajira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load()
        if isinstance(self.recent_data, list) and len(self.recent_data) > 0:
            self.recent_data = self.recent_data[0]

        return self.recent_data

    def validate_input(self, **args):
        return True

    def _fetch(self):

        # We compose a single query to retrieve all resolved tickets by all assignees and iterate
        #   over them in memory to reduce the number of calls to jira

        data = augur.api.get_all_developer_info()

        jql = "category = 'Ecommerce Workflows' and status changed to 'resolved' after startOfDay(-2M) and " \
              "status = 'resolved' and resolution in (%s) order by assignee desc, updated desc" \
              % (",".join(common.POSITIVE_RESOLUTIONS))

        issues = self.uajira.execute_jql(jql, max_results=1000)
        for issue in issues:

            # needs to have a point value and an assignee to proceed
            if issue.fields.customfield_10002 and issue.fields.assignee and issue.fields.assignee.name:
                if issue.fields.assignee.name in data['devs']:
                    uname = issue.fields.assignee.name
                    # the username is in our list of developers so we can update with info
                    if 'total_points' not in data['devs'][uname]:
                        data['devs'][uname]['total_points'] = 0.0
                    data['devs'][uname]['total_points'] += issue.fields.customfield_10002

        return self.cache_data(data)
