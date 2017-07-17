import base64

import exceptions

import augur
from augur.common import const, transform_status_string, cache_store
from augur.fetchers.fetcher import AugurDataFetcher
from augur.api import get_jira


class Milestone(object):
    def __init__(self):
        self.type = None # can be one of [epic, filter, adhoc]
        self.id = None
        self.ob = None # object type based on milestone type
        self.jql = None # all types must have jql associated with them.

    def get_id(self):
        return self.id

    def set_filter(self, filter_id):
        self.type = 'filter'
        self.id = filter_id
        f = get_jira().jira.filter(filter_id)
        if not f:
            raise LookupError("Unable to find a filter with ID %s"%str('filter_id'))
        self.ob = f.raw
        self.jql = f.jql

    def set_epic(self, epic_key):
        self.type = 'epic'
        self.id = epic_key
        self.ob = augur.api.get_issue_details(epic_key)
        if not self.ob:
            raise LookupError("Unable to find an epic with the key %s"%epic_key)
        self.jql  = '"Epic Link"="%s"' % epic_key

    def set_adhoc(self, jql):
        self.type = 'adhoc'
        self.id = base64.b64encode(jql)
        self.ob = None
        self.jql = jql


class UaMilestoneDataFetcher(AugurDataFetcher):
    """
    Retrieves data is helpful to analyze the state of a milestones.  Milestones can be tracked
    in one of three ways:
        * A filter ID (filter_id)
        * An epic key (epic_key)
        * An ad-hoc jql query (jql)

    """
    def __init__(self,*args, **kwargs):
        self.milestone = Milestone()
        super(UaMilestoneDataFetcher, self).__init__(*args, **kwargs)

    def init_cache(self):
        self.cache = cache_store.AugurJiraMilestoneData(self.augurjira.mongo)

    def cache_data(self,data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_milestone(self.milestone.get_id())
        return self.recent_data

    def validate_input(self,**args):

        if 'epic_key' not in args:
            if 'filter_id' not in args:
                if 'jql' not in args:
                    self.milestone = None
                    raise LookupError("The milestone data input requires a either a "
                                      "filter ID, an epic key or a JQL string as input")
                else:
                    self.milestone.set_adhoc(args['jql'])
            else:
                self.milestone.set_filter(args['filter_id'])
        else:
            self.milestone.set_epic(args['epic_key'])

        return True

    def _fetch(self):
        assert(self.context is not None)
        if self.milestone:

            stats = self.augurjira.execute_jql_with_analysis(self.milestone.jql)

            in_progress_items = []
            group_by_components = {}
            group_by_developers = {}
            group_by_status = {transform_status_string(s): [] for s in self.context.workflow.statuses}

            points_by_components = {}
            points_by_developers = {}
            points_by_status = {transform_status_string(s): 0 for s in self.context.workflow.statuses}

            points_field_name = augur.api.get_issue_field_from_custom_name('Story Points')
            for key,issue in stats['issues'].iteritems():

                story_points = 0
                if points_field_name in issue['fields']:
                    story_points = issue['fields'][points_field_name]

                # get a list of all the issues in progress
                if self.context.workflow.is_in_progress(issue['status']):
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
            stats['milestone'] = self.milestone.ob

            return self.cache_data(stats)
        else:
            raise Exception("An invalid (or no) milestone was given")