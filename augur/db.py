from pony import orm
from pony.orm import sql_debug, Json
import datetime

NOTIFY_TYPES = ["none", "email", "slack"]
TOOL_ISSUE_STATUS_TYPES = ["open", "in progress", "done"]
STATUS = ["Unknown", "Active", "Inactive", "Pending"]
ROLES = ["Unknown", "Developer", "SDET", "Technical Manager", "Product Manager", "Director", "Lead Developer",
         "Engagement Manager", "Project Manager",
         "Business Analyst", "QA", "Technical Manager", "Product Owner", "Vice President"]
TOOL_ISSUE_RESOLUTION_TYPES = ["positive", "negative"]
TOOL_ISSUE_TYPE_TYPES = ["story", "task", "bug", "question"]
BUILD_TYPES = ['all', 'upstream', 'myteam', 'otherteams']
STAFF_TYPES = ["FTE", "Consultant"]

db = orm.Database()
__is_bound = False


class ToolIssueResolution(db.Entity):
    """
    Represents an issue type within a workflow tool.  For example, Jira.
    """
    id = orm.PrimaryKey(int, auto=True)
    tool_issue_resolution_name = orm.Required(unicode)
    tool_issue_resolution_type = orm.Required(unicode, py_check=lambda v: v in TOOL_ISSUE_RESOLUTION_TYPES)
    workflows = orm.Set('Workflow', reverse="resolutions")


class ToolIssueStatus(db.Entity):
    """
    Represents an issue type within a workflow tool.  For example, Jira.
    """
    id = orm.PrimaryKey(int, auto=True)
    tool_issue_status_name = orm.Required(unicode)
    tool_issue_status_type = orm.Required(unicode, py_check=lambda v: v in TOOL_ISSUE_STATUS_TYPES)
    workflows = orm.Set('Workflow', reverse="statuses")


class ToolIssueType(db.Entity):
    """
    Represents an issue type within a workflow tool.  For example, Jira.
    """
    id = orm.PrimaryKey(int, auto=True)
    tool_issue_type_name = orm.Required(unicode)
    tool_issue_type_type = orm.Required(unicode, py_check=lambda v: v in TOOL_ISSUE_TYPE_TYPES)
    workflow_defect_project_filters = orm.Set('WorkflowDefectProjectFilter', reverse="issue_types")
    workflows = orm.Set('Workflow', reverse="issue_types")


class EventLog(db.Entity):
    """
    Represents an event log entry
    """
    id = orm.PrimaryKey(int, auto=True)
    event_time = orm.Required(datetime.datetime)
    event_type = orm.Required(unicode)
    event_data = orm.Optional(Json)


class Vendor(db.Entity):
    """
    Represents a third-party vendor who is either providing services or products to the group
    """
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    engagement_contact_first_name = orm.Optional(unicode)
    engagement_contact_last_name = orm.Optional(unicode)
    engagement_contact_email = orm.Optional(unicode)
    billing_contact_first_name = orm.Optional(unicode)
    billing_contact_last_name = orm.Optional(unicode)
    billing_contact_email = orm.Optional(unicode)
    tempo_id = orm.Optional(int)
    consultants = orm.Set('Staff', reverse='vendor')

    def get_engagement_contact_full_name(self):
        if self.engagement_contact_first_name and self.engagement_contact_last_name:
            return "%s %s" % (self.engagement_contact_first_name, self.engagement_contact_last_name)
        elif self.engagement_contact_last_name:
            return self.engagement_contact_last_name
        elif self.engagement_contact_first_name:
            return self.engagement_contact_first_name
        else:
            return "None Given"

    def get_billing_contact_full_name(self):
        if self.billing_contact_first_name and self.billing_contact_last_name:
            return "%s %s" % (self.billing_contact_first_name, self.billing_contact_last_name)
        elif self.billing_contact_last_name:
            return self.engagement_contact_last_name
        elif self.billing_contact_first_name:
            return self.engagement_contact_first_name
        else:
            return "None Given"


class Product(db.Entity):
    """
    Represents a single member of a team.  A team member can be on multiple teams and a team can have multiple
     team members.  The staff object is used to store information like hourly rate (when a consultant), usernames
     in various integrations along with start date.
    """
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    key = orm.Required(unicode, unique=True)
    teams = orm.Set('Team', reverse='product')
    groups = orm.Set('Group', reverse='products')


class ToolProject(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    tool_project_key = orm.Required(unicode)
    workflows = orm.Set('Workflow', reverse="projects")


class ToolProjectCategory(db.Entity):
    """
    Represents the category of a project as represented by the associated tools.  Not all tools organize projects
    into categories
    """
    id = orm.PrimaryKey(int, auto=True)
    tool_category_name = orm.Required(unicode)
    workflows = orm.Set('Workflow', reverse="categories")


class Staff(db.Entity):
    """
    Represents a single member of a team.  A team member can be on multiple teams and a team can have multiple
     team members.  The staff object is used to store information like hourly rate (when a consultant), usernames
     in various integrations along with start date.
    """
    first_name = orm.Required(unicode)
    last_name = orm.Required(unicode)
    company = orm.Optional(unicode)
    avatar_url = orm.Optional(unicode)
    role = orm.Required(unicode, py_check=lambda v: v in ROLES)
    email = orm.Required(unicode)
    rate = orm.Required(float)
    start_date = orm.Required(datetime.date)
    type = orm.Required(str, py_check=lambda v: v in STAFF_TYPES, default="FTE")
    jira_username = orm.Required(unicode)
    slack_id = orm.Optional(unicode)
    github_username = orm.Optional(unicode)
    status = orm.Required(unicode, py_check=lambda v: v in STATUS)
    teams = orm.Set('Team', reverse="members")
    base_daily_cost = orm.Optional(float)
    base_weekly_cost = orm.Optional(float)
    base_annual_cost = orm.Optional(float)
    vendor = orm.Optional(Vendor, reverse='consultants')
    notification = orm.Optional("Notifications", reverse="staff")

    def get_company(self):
        if self.vendor:
            return self.vendor.name
        else:
            return "None Given"

    def is_in_team(self, team_name):
        for t in self.teams:
            if team_name.lower() in t.name.lower():
                return True
        return False

    def get_fullname(self):
        if self.first_name and self.last_name:
            return "%s %s" % (self.first_name, self.last_name)
        else:
            return self.first_name if self.first_name else self.last_name or "None Given"

    def before_insert(self):
        self.calculate_costs()

    def before_update(self):
        self.calculate_costs()

    def calculate_costs(self):

        # Calculate the cost of the employee post import
        if self.status.lower() == "active":
            self.base_daily_cost = self.rate * 8
            self.base_weekly_cost = self.base_daily_cost * 5
            self.base_annual_cost = self.base_weekly_cost * 50  # assume two weeks of vacation
        else:
            self.base_daily_cost = 0.0
            self.base_weekly_cost = 0.0
            self.base_annual_cost = 0.0


class AgileBoard(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    jira_id = orm.Optional(int)
    team = orm.Optional('Team', reverse='agile_board')


class Team(db.Entity):
    """
    Represents a team in the organization.  Teams contain staff members and are associated with agile boards
    and products most of the time.
    """
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    members = orm.Set(Staff, reverse='teams')
    agile_board = orm.Optional(AgileBoard, reverse='team', sql_default=0)
    product = orm.Optional(Product, reverse='teams', sql_default=0)
    groups = orm.Set('Group', reverse="teams")
    notification = orm.Optional("Notifications", reverse="team")

    def get_agile_board_jira_id(self):
        return self.agile_board.jira_id if self.agile_board else 0

    def get_groups_as_string(self):
        names = []
        for g in self.groups:
            names.append(g.name)
        return ', '.join(names) if len(names) > 0 else "None"


class Notifications(db.Entity):
    """
    Represents a set of notification preferences that can be associated with a staff member or team
    """
    id = orm.PrimaryKey(int, auto=True)
    build = orm.Required(unicode, default="email,slack")
    deploy = orm.Required(unicode, default="email,slack")
    staff = orm.Optional(Staff)
    team = orm.Optional(Team)
    build_types = orm.Required(unicode, default="all")

    def should_send_build_x(self, ntype):
        ntypes = str(self.build).split(",")
        return ntype in ntypes

    def should_send_deploy_x(self, ntype):
        ntypes = str(self.deploy).split(",")
        return ntype in ntypes

    def should_send_build_email(self):
        return self.should_send_build_x("email")

    def should_send_build_slack(self):
        return self.should_send_build_x("slack")

    def should_send_deploy_email(self):
        return self.should_send_deploy_x("email")

    def should_send_deploy_slack(self):
        return self.should_send_deploy_x("slack")


class WorkflowDefectProjectFilter(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    project_key = orm.Required(str)
    issue_types = orm.Set(ToolIssueType, reverse='workflow_defect_project_filters')
    workflows = orm.Set('Workflow', reverse="defect_projects")

    def get_issue_types_as_string_list(self):
        types = []
        for it in self.issue_types:
            types.append(it.tool_issue_type_name)

        return types


class Workflow(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    statuses = orm.Set(ToolIssueStatus, reverse="workflows")
    resolutions = orm.Set(ToolIssueResolution, reverse="workflows")
    projects = orm.Set(ToolProject, reverse="workflows")
    categories = orm.Set(ToolProjectCategory, reverse="workflows")
    issue_types = orm.Set(ToolIssueType, reverse="workflows")
    defect_projects = orm.Set(WorkflowDefectProjectFilter, reverse="workflows")
    groups = orm.Set('Group', reverse="workflow")

    def get_defect_projects(self):
        """
        Gets all the projects that are considered defect projects for this workflow
        :return: Returns a list of dicts that look like this:
            {
                [
                    key: <string>,
                    issue_types: [<string>, <string>, ...]
                ]
            }
        """
        defect_projects = [p for p in self.defect_projects]

        if defect_projects:
            # if this workflow specifies projects with keys and the caller
            #   just wants keys returned then we can just return this list.
            return [dict({"key": df.project_key,
                          "issue_types": df.get_issue_types_as_string_list()})
                    for df in defect_projects]
        else:
            return []

    def is_defect_ticket(self, project_key, issue_type):
        if not project_key or not issue_type:
            return False

        for df in self.defect_projects:
            if project_key.lower() == df.project_key.lower():
                for df_type in df.issue_types:
                    if df_type.tool_issue_type_name.lower() == issue_type.lower():
                        return True
        return False

    def status_ob_from_string(self, status_name):
        try:
            return filter(lambda x: x.tool_issue_status_name.lower() == status_name.lower(),
                          self.statuses).pop()
        except IndexError:
            return None

    def resolution_ob_from_string(self, res_name):
        try:
            return filter(lambda x: x.tool_issue_resolution_name.lower() == res_name.lower(),
                          self.resolutions).pop()
        except IndexError:
            return None

    def is_resolved(self, status, resolution):
        """
        Determines if the given status and resolution indicates a completed ticket
        :param status:
        :type status: ToolIssueStatus
        :param resolution:
        :type resolution: ToolIssueResolution
        :return: Returns False if status or resolution could not be found in this workflow
        """
        status_ob = self.status_ob_from_string(status)
        res_ob = self.resolution_ob_from_string(resolution)
        if not status_ob:
            return False

        if status_ob.tool_issue_status_type.lower() == "done":
            if res_ob:
                if res_ob.tool_issue_resolution_type.lower() == "positive":
                    return True
            else:
                # if the resolution isn't set then we will assume
                return True

        return False

    def is_abandoned(self, status, resolution):
        """
        Determines if the given status and resolution indicates an abandoned ticket. An abandoned
        ticket is a "done" ticket that has a "negative" resolution.
        :param status:
        :type status: ToolIssueStatus
        :param resolution:
        :type resolution: ToolIssueResolution
        :return:
        """
        status_ob = self.status_ob_from_string(status)
        res_ob = self.resolution_ob_from_string(resolution)
        if not status_ob:
            return False

        if status_ob.tool_issue_status_type.lower() == "done":
            if res_ob:
                if res_ob.tool_issue_resolution_type.lower() == "negative":
                    return True

        return False

    def positive_resolutions(self):
        return filter(lambda x: x.tool_issue_resolution_type.lower() == "positive", self.resolutions)

    def negative_resolutions(self):
        return filter(lambda x: x.tool_issue_resolution_type.lower() == "negative", self.resolutions)

    def open_statuses(self):
        """
        Returns a list of all the statuses that are considered to be "open".
        :return: A list of ToolIssueStatus objects.
        """
        return filter(lambda x: x.tool_issue_status_type.lower() == "open", self.statuses)

    def done_statuses(self):
        """
        Returns a list of all the statuses that are considered to be "done".
        :return: A list of ToolIssueStatus objects.
        """
        return filter(lambda x: x.tool_issue_status_type.lower() == "done", self.statuses)

    def in_progress_statuses(self):
        """
        Returns all statuses that are considered "in progress" according to this workflow
        :return: A list of ToolIssueStatus objects
        """
        return filter(lambda x: x.tool_issue_status_type.lower() == "in progress", self.statuses)

    def dev_issue_types(self):
        """
        Returns all issue types that are considered development tickets as opposed to bug related tickets.
        :return: A list of ToolIssueType objects
        """
        return filter(lambda x: x.tool_issue_type_type.lower() in ["story", "task"], self.issue_types)

    def is_in_progress(self, status):
        """
        Returns True if the given status string is considered an "in progress" status.
        :param status: The status string
        :type status: str
        :return: Returns boolean
        :rtype: bool
        """
        for s in self.statuses:
            if s.tool_issue_status_name.lower() == status.lower():
                return s.tool_issue_status_type == "in progress"
        return False

    def get_project_keys(self):
        return self.get_projects(key_only=True)

    def get_projects_by_category(self, category):
        """
        Gets all projects with the given category
        :param category:
        :return:
        """
        from augur import api
        cache_key = "projects_%s" % category
        projects = api.get_memory_cached_data(cache_key)
        if not projects:
            projects = api.get_jira().jira.get_projects_with_category(category)
            api.memory_cache_data({'data': projects}, cache_key)
        else:
            projects = projects[0]['data']

        return projects

    def get_projects(self, key_only=False):
        from augur.api import get_jira
        project_keys = [p.tool_project_key for p in self.projects]
        projects = []

        if project_keys:
            if key_only:
                # if this workflow specifies projects with keys and the caller
                #   just wants keys returned then we can just return this list.
                return project_keys
            else:
                # Call into jira to get the list of projects with these keys
                projects = get_jira().jira.get_projects_with_key(project_keys)
        elif self.categories:
            # Call into jira to get the list of projects with the given categories.
            for c in self.categories:
                projects.extend(self.get_projects_by_category(c.tool_category_name))

        if key_only:
            return [p['key'].upper() for p in projects]
        else:
            return projects

    def get_projects_jql(self):
        """
        Generates the JQL for the portion of the expression that limits the projects to this workspace only.
        :return: Returns a string with the projects JQL
        """
        keys = []
        for p in self.projects:
            keys.append(p.tool_project_key)

        categories = []
        for c in self.categories:
            categories.append(c.tool_category_name)

        jql_projects = ""
        jql_categories = ""
        if len(keys) > 0:
            jql_projects = "project in (%s)" % ",".join(keys)

        if len(categories) > 0:
            jql_categories = "category in ('%s')" % "','".join(categories)

        if jql_projects and jql_categories:
            return "((%s) OR (%s))" % (jql_projects, jql_categories)
        else:
            return jql_projects if jql_projects else jql_categories

    def get_positive_resolution_jql(self):
        """
        Generates the JQL for the portion of the expression that limits the issues to those that have positive
        resolutions (which is defined by the statuses and resolutions defined in this workflow)
        :return: Returns a JQL string
        """
        done_statuses = [d.tool_issue_status_name for d in self.done_statuses()]
        done_resolutions = [d.tool_issue_resolution_name for d in self.positive_resolutions()]

        return "(status in (\"%s\") and resolution in (\"%s\"))" % \
               ('","'.join(done_statuses), '","'.join(done_resolutions))

    def as_json(self):
        return {
            "statuses": {
                "open": [s.tool_issue_status_name for s in self.open_statuses()],
                "in progress": [s.tool_issue_status_name for s in self.in_progress_statuses()],
                "done": [s.tool_issue_status_name for s in self.done_statuses()]
            },
            "projects": self.get_project_keys(),
            "resolutions": {
                "positive": [pr.tool_issue_resolution_name for pr in self.positive_resolutions()],
                "negative": [pr.tool_issue_resolution_name for pr in self.negative_resolutions()],
            }
        }


class Group(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    workflow = orm.Optional(Workflow, reverse="groups")
    products = orm.Set(Product, reverse="groups")
    teams = orm.Set(Team, reverse="groups")


def init_db():
    global __is_bound

    if not __is_bound:

        from augur import settings

        if settings.main.project.debug:
            sql_debug(True)

        if settings.main.datastores.main.type == "sqlite":
            dbtype = settings.main.datastores.main.type
            dbtarget = settings.main.datastores.main.sqlite.path
            db.bind('sqlite', filename=dbtarget, create_db=True)
            __is_bound = True
        elif settings.main.datastores.main.type == "postgres":
            pg_settings = settings.main.datastores.main.postgres
            dbtype = settings.main.datastores.main.type
            dbtarget = pg_settings.host + "/" + pg_settings.dbname + ":" + pg_settings.port
            db.bind('postgres', user=pg_settings.username, password=pg_settings.password,
                    host=pg_settings.host, database=pg_settings.dbname, port=pg_settings.port)
            __is_bound = True
        else:
            raise ValueError("Invalid database type configured: %s" % augur.settings.main.datastores.main.type)

        if __is_bound:
            print "Database Configuration:"
            print "Type: %s" % dbtype
            print "Target: %s" % dbtarget

            db.generate_mapping(create_tables=True)
        else:
            print "No valid database configuration found"
