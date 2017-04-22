from augur import cache_store
from augur.common import const, transform_status_string
from augur.integrations.uajira.data.uajiradata import UaJiraDataFetcher


class UaJiraEpicDataFetcher(UaJiraDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraEpicData(self.uajira.mongo)

    def cache_data(self,data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_epic(self.epic_key)
        return self.recent_data

    def validate_input(self,**args):
        if 'epic_key' not in args:
            raise LookupError("The epic data input requires an epic key as input")
        else:
            self.epic_key = args['epic_key']

        return True

    def _fetch(self):

        epic_ob = self.uajira.get_issue_details(self.epic_key)
        if epic_ob:
            jql = '"Epic Link"="%s"'%self.epic_key
            stats = self.uajira.execute_jql_with_analysis(jql)

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
                    if username not in group_by_developers:
                        group_by_developers[username] = []
                        points_by_developers[username] = 0

                    group_by_developers[username].append(issue)
                    points_by_developers[username] += story_points

                status = transform_status_string(issue['fields']['status']['name'])
                if status in group_by_status:
                    group_by_status[status].append(issue)
                    points_by_status[status] += story_points

            stats['in_progress_items'] = in_progress_items
            stats['group_by_components'] = group_by_components
            stats['group_by_status'] = group_by_status
            stats['group_by_assignee'] = group_by_developers
            stats['epic'] = epic_ob

            return self.cache_data(stats)
        else:
            raise Exception("The specified epic %d could not be found"%self.epic_key)
