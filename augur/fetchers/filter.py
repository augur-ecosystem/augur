from augur.common import const, transform_status_string, cache_store
from augur.fetchers.fetcher import UaDataFetcher


class UaFilterDataFetcher(UaDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraFilterData(self.uajira.mongo)

    def cache_data(self,data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_filter(self.filter_id)
        return self.recent_data

    def validate_input(self,**args):
        if 'filter_id' not in args:
            raise LookupError("The filter data input requires a filter ID as input")
        else:
            self.filter_id = args['filter_id']

        return True

    def _fetch(self):

        filter_ob = self.uajira.jira.filter(self.filter_id)
        if filter_ob:
            stats = self.uajira.execute_jql_with_analysis(filter_ob.jql)

            in_progress_items = []
            group_by_components = {}
            group_by_developers = {}
            group_by_status = {
                transform_status_string(const.STATUS_OPEN):[],
                transform_status_string(const.STATUS_INPROGRESS):[],
                transform_status_string(const.STATUS_QUALITYREVIEW):[],
                transform_status_string(const.STATUS_INTEGRATION):[],
                transform_status_string(const.STATUS_STAGING):[],
                transform_status_string(const.STATUS_PRODUCTION):[],
                transform_status_string(const.STATUS_RESOLVED):[]
            }

            points_by_components = {}
            points_by_developers = {}
            points_by_status = {
                transform_status_string(const.STATUS_OPEN):0,
                transform_status_string(const.STATUS_INPROGRESS):0,
                transform_status_string(const.STATUS_QUALITYREVIEW):0,
                transform_status_string(const.STATUS_INTEGRATION):0,
                transform_status_string(const.STATUS_STAGING):0,
                transform_status_string(const.STATUS_PRODUCTION):0,
                transform_status_string(const.STATUS_RESOLVED):0
            }

            for key,issue in stats['issues'].iteritems():

                story_points = 0
                if 'customfield_10002' in issue['fields']:
                    story_points = issue['fields']['customfield_10002']

                # get a list of all the issues in progress
                if self.uajira._analytics_is_inprogress(issue['status']):
                    in_progress_items.append(issue)

                # get a list of all unfinished issues by component
                if 'components' in issue['fields']:
                    for cmp in issue['fields']['components']:
                        if cmp['name'] not in group_by_components:
                            group_by_components[cmp['name']] = []
                            points_by_components[cmp['name']] = 0

                        points_by_components[cmp['name']] = story_points
                        group_by_components[cmp['name']].append(issue)

                if 'assignee' in issue['fields'] and 'name' in issue['fields']['assignee']:
                    username = issue['fields']['assignee']['name']
                    username_key = username.replace(".","_")
                    if username_key not in group_by_developers:
                        group_by_developers[username_key] = []
                        points_by_developers[username_key] = 0

                    group_by_developers[username_key].append(issue)
                    points_by_developers[username_key] += story_points

                status = transform_status_string(issue['fields']['status']['name'])
                if status in group_by_status:
                    group_by_status[status].append(issue)
                    points_by_status[status] += story_points

            stats['in_progress_items'] = in_progress_items
            stats['group_by_components'] = group_by_components
            stats['group_by_status'] = group_by_status
            stats['group_by_assignee'] = group_by_developers
            stats['points_by_components'] = points_by_components
            stats['points_by_status'] = points_by_status
            stats['points_by_assignee'] = points_by_developers
            stats['filter'] = filter_ob.raw

            return self.cache_data(stats)
        else:
            raise Exception("The specified filter %d could not be found"%self.filter_id)