from augur.common import cache_store
from augur.fetchers.fetcher import UaDataFetcher


class UaJiraIssueDataFetcher(UaDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraIssueData(self.uajira.mongo)

    def cache_data(self,data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        # if self.issue_key:
        #     self.recent_data = self.cache.load_issue(self.issue_key)
        #     return self.recent_data
        # else:
        #   return None

        # disable caching
        return None

    def validate_input(self,**args):
        if 'issue_key' not in args and 'issue_keys' not in args:
            raise LookupError("You must specify issue_key or issue_keys to retrieve that data")

        self.issue_key = args['issue_key'] if 'issue_key' in args else None
        self.issue_keys = args['issue_keys'] if 'issue_keys' in args else None

    def _fetch(self):

        if self.issue_key:
            issues = self.uajira.execute_jql("issue={key}".format(key=self.issue_key), expand='changelog')
            if len(issues) > 0:
                self.cache_data(issues[0].raw)
                return issues[0].raw
            return None

        elif self.issue_keys:
            issues = self.uajira.execute_jql("issue in ({keys})".format(keys=",".join(self.issue_keys)))
            if len(issues) > 0:
                return filter(lambda x: x.raw, issues)
            return None

