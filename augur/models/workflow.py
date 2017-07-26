import augur
from augur.models import AugurModel


class WorkflowDefect(AugurModel):
    """
    An object representing the definition of a defect
    """
    def _add_properties(self):
        self.add_prop("key", "", unicode)
        self.add_prop("issuetypes", [], list)

    def handle_dict_import(self, item):
        if 'issuetypes' in item:
            self.issuetypes = item['issuetypes']
        if 'key' in item:
            self.key = item['key']

    def get_jql(self, include_issue_types=True):
        if include_issue_types:
            return "(project = %s and issuetype in ('%s'))" % (self.key, "','".join(self.issuetypes))
        else:
            return "(project = %s)" % self.key


class WorkflowProjects(AugurModel):
    def _add_properties(self):
        self.add_prop("keys", [], list)
        self.add_prop("categories", [], list)

    def get_projects(self, key_only):
        """
        Gets all projects that are part of this workflow
        from Jira.  This can return either the full project metadata or just the key
        :param key_only: If true, only return the project keys and not the full project object
        :return:
        """
        from augur.api import get_jira
        projects = []
        if self.keys:
            if key_only:
                # if this workflow specifies projects with keys and the caller
                #   just wants keys returned then we can just return this list.
                return self.keys
            else:
                # Call into jira to get the list of projects with these keys
                projects = get_jira().get_projects_with_key(self.keys)
        elif self.categories:
            # Call into jira to get the list of projects with the given categories.
            projects = []
            for c in self.categories:
                projects.extend(augur.api.get_projects_by_category(c))

        if key_only:
            return [p['key'] for p in projects]
        else:
            return projects

    def handle_dict_import(self, item):
        if 'keys' in item:
            self.keys = item['keys']
        if 'categories' in item:
            self.categories = item['categories']


class Workflow(AugurModel):
    def __init__(self):
        # must come before
        super(Workflow, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("name", "", unicode)
        self.add_prop("statuses", [], list)
        self.add_prop("in_progress_statuses", [], list)
        self.add_prop("completed_statuses", [], list)
        self.add_prop("positive_resolutions", [], list)
        self.add_prop("issuetypes", [], list)
        self.add_prop("projects", {}, WorkflowProjects)
        self.add_prop("defects", [], list)

    def handle_dict_import(self, item):
        """
        Handles import of a dictionary object that is meant to represent a single instance of the model
        :param item: dict: The item being imported
        :return:
        """
        if 'id' in item:
            self.id = item['id']
        if 'name' in item:
            self.name = item['name']
        if 'statuses' in item and isinstance(item['statuses'], list):
            self.statuses = item['statuses']
        if 'in_progress_statuses' in item and isinstance(item['in_progress_statuses'], list):
            self.in_progress_statuses = item['in_progress_statuses']
        if 'positive_resolutions' in item and isinstance(item['positive_resolutions'], list):
            self.positive_resolutions = item['positive_resolutions']
        if 'completed_statuses' in item and isinstance(item['completed_statuses'], list):
            self.completed_statuses = item['completed_statuses']
        if 'issuetypes' in item and isinstance(item['issuetypes'], list):
            self.issuetypes = item['issuetypes']
        if 'projects' in item and isinstance(item['projects'], dict):
            self.projects = WorkflowProjects()
            self.projects.handle_dict_import(item['projects'])
        if 'defects' in item and isinstance(item['defects'], list):
            for d in item['defects']:
                defect = WorkflowDefect()
                defect.handle_dict_import(d)
                self.defects.append(defect)

        super(Workflow, self).handle_dict_import(item)

        return self

    def is_in_progress(self, status):
        """Returns True if the given status is considered an in progress status, False otherwise"""
        return status.lower() in [s.lower() for s in self.in_progress_statuses]

    def is_resolved(self, status, resolution=None, check_positive=False):
        """
        Determines if the given status is "complete".  If check_positive is given, then the resolution value is
        used to determine if it's a postive resolution as in it was "fixed" or "completed" as opposed to "abandoned"
        :param status: The status to check
        :param resolution: The resolution to check
        :param check_positive: True to use the resolution to determine if it's truly completed.
        :return: Returns True if resolved, false otherwise.
        """
        complete = status.lower() in self.completed_statuses

        # if it's a complete status, a request for positive resolution check is made and
        # the resolution is not positive, then do not consider this complete.
        if complete and check_positive and resolution:
            if resolution.lower() not in [x.lower() for x in self.positive_resolutions]:
                complete = False

        return complete

    def is_abandoned(self, status, resolution):
        """
        Determines if the given status is "abandoned".  This means it has a complete status but an incomplete
        resolution (such as abandoned or duplicate)
        :param status: The status to check
        :param resolution: The resolution to check
        :return: Returns True if abandoned, false otherwise.
        """
        complete = status.lower() in self.completed_statuses

        # if it's a complete status, a request for positive resolution check is made and
        # the resolution is not positive, then do not consider this complete.
        if complete and resolution:
            if resolution.lower() not in [x.lower() for x in self.positive_resolutions]:
                return True

        return False

    def get_defect_projects(self, include_issue_types=True):
        """
        Gets the defect projects in jql fragment form.  If include_issue_types is True then it will further refine
        the query to only include the issue types specified in the workflow for these defect projects.
        :param include_issue_types: True to include the issuetype refinement, False otherwise.
        :return: Returns a string containing the jql fragment.
        """
        jql_list = []
        for d in self.defects:
            jql_list.append(d.get_jql(include_issue_types))

        return "((%s))" % ") OR (".join(jql_list)

    def get_resolved_statuses_jql(self):
        """
        Gets the resolved statuses in JQL form to be used with the IN or NOT IN operator
        :return: Returns a jql fragment string
        """
        return "('%s')" % "','".join(self.completed_statuses)

    def get_projects(self, key_only=False):
        """
        Gets the project objects from JIRA
        :param key_only:
        :return:
        """
        return self.projects.get_projects(key_only)

    def get_projects_jql(self):
        """
        Gets the projects information and returns a jql string that can be embedded directly into a larger jql
        :return: Returns a string containing the jql
        """
        if len(self.projects.keys) > 0:
            return "project in (%s)"%",".join(self.projects.keys)
        elif len(self.projects.categories) > 0:
            return "category in ('%s')" % "','".join(self.projects.categories)

    def handle_post_import(self):
        super(Workflow, self).handle_post_import()


if __name__ == '__main__':
    models = AugurModel.import_from_yaml(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/workflows.yaml"
        , Workflow)

    print models
