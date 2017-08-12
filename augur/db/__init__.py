import json

from pony import orm
from pony.orm import db_session, commit, sql_debug

import augur
from augur.models import staff, product, workflow, group
from augur.models import team

import datetime

TOOL_ISSUE_STATUS_TYPES = ["open", "in progress", "done"]
STATUS = ["Unknown", "Active", "Deactivate"]
ROLES = ["Unknown", "Developer", "QE", "Manager", "Director", "DevTeamLead", "Engagement Manager", "PM",
         "Business Analyst", "QA", "Technical Manager"]
TOOL_ISSUE_RESOLUTION_TYPES = ["positive", "negative"]
TOOL_ISSUE_TYPE_TYPES = ["story", "task", "bug", "question"]
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
    company = orm.Required(unicode)
    avatar_url = orm.Optional(unicode)
    role = orm.Required(unicode, py_check=lambda v: v in ROLES)
    email = orm.Required(unicode)
    rate = orm.Required(float)
    start_date = orm.Required(datetime.date)
    type = orm.Required(str, py_check=lambda v: v in STAFF_TYPES, default="FTE")
    jira_username = orm.Required(unicode)
    github_username = orm.Optional(unicode)
    status = orm.Required(unicode, py_check=lambda v: v in STATUS)
    teams = orm.Set('Team', reverse="members")
    base_daily_cost = orm.Optional(float)
    base_weekly_cost = orm.Optional(float)
    base_annual_cost = orm.Optional(float)

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

    def get_agile_board_jira_id(self):
        return self.agile_board.jira_id


class WorkflowDefectProjectFilter(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    project_key = orm.Required(str)
    issue_types = orm.Set(ToolIssueType, reverse='workflow_defect_project_filters')
    workflows = orm.Set('Workflow', reverse="defect_projects")

    def get_issue_types_as_string_list(self, include_issue_types=True):
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

    def get_defect_project_filters(self):
        return self.defect_projects

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
        if not (status_ob or res_ob):
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
        if not (status_ob or res_ob):
            return False

        if status_ob.tool_issue_status_type.lower() == "done":
            if res_ob.tool_issue_resolution_type.lower() == "negative":
                return True

        return False

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


class Group(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    workflow = orm.Optional(Workflow, reverse="groups")
    products = orm.Set(Product, reverse="groups")
    teams = orm.Set(Team, reverse="groups")


def init_db():

    global __is_bound

    if not __is_bound:

        if augur.settings.main.project.debug == True:
            sql_debug(True)

        if augur.settings.main.datastores.main.type == "sqlite":
            filename = augur.settings.main.datastores.main.sqlite.path
            print "Opening sqlite database with filename %s"%filename
            db.bind('sqlite', filename=filename, create_db=True)
            __is_bound = True
        elif augur.settings.main.datastores.main.type == "postgres":
            # TODO: Suport Postgres
            pass

        db.generate_mapping(create_tables=True)
