from augur import common
from augur.common import cache_store
from augur.integrations.uajira.data.uajiradata import UaJiraDataFetcher


class UaJiraOrgStatsFetcher(UaJiraDataFetcher):
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
        # in this case we try to update the data in the data store since there are more possibilities
        # and we don't have a cron job that updates the data in the background.  So it has to be updated by
        # visits to the page with the same user and the same look back days

        data = self.uajira.get_all_developer_info()

        for username, info in data['devs'].iteritems():
            jql = "category = 'Ecommerce Workflows' and assignee = '%s' and " \
                  "status = 'resolved' and resolution in (%s) order by assignee desc, updated desc" \
                  % (username, ",".join(common.POSITIVE_RESOLUTIONS))

            issues = self.uajira.execute_jql(jql)
            info['total_points'] = reduce(lambda total, dev: total + (dev.fields.customfield_10002 if
                                                                      dev.fields.customfield_10002 else 0.0), issues,
                                          0.0)

        return self.cache_data(data)
