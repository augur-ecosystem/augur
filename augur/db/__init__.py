import json

from pony import orm
from pony.orm import db_session, commit

import augur
from augur.models import staff, product, workflow
from augur.models import team

import datetime

TOOL_ISSUE_STATUS_TYPES = ["open", "in progress", "done"]
STATUS = ["Unknown", "Active", "Deactivate"]
ROLES = ["Unknown", "Developer", "QE", "Manager", "Director", "DevTeamLead", "Engagement Manager", "PM",
         "Business Analyst", "QA", "Technical Manager"]
TOOL_ISSUE_RESOLUTION_TYPES = ["positive", "negative"]

db = orm.Database()


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
    workflow_defect_project_filters = orm.Set('WorkflowDefectProjectFilter', reverse="issue_types")


class Product(db.Entity):
    """
    Represents a single member of a team.  A team member can be on multiple teams and a team can have multiple
     team members.  The staff object is used to store information like hourly rate (when a consultant), usernames
     in various integrations along with start date.
    """
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    key = orm.Required(unicode,unique=True)
    teams = orm.Set('Team', reverse='product')


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
    jira_username = orm.Required(unicode)
    github_username = orm.Optional(unicode)
    status = orm.Required(unicode, py_check=lambda v: v in STATUS)
    team = orm.Optional('Team', reverse="members", nullable=True)
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
    members = orm.Set(Staff, reverse='team')
    agile_board = orm.Optional(AgileBoard, reverse='team',sql_default=0)
    product = orm.Optional(Product, reverse='teams',sql_default=0)


class WorkflowDefectProjectFilter(db.Entity):
    id = orm.PrimaryKey(int,auto=True)
    project_key = orm.Required(str)
    issue_types = orm.Set(ToolIssueType, reverse='workflow_defect_project_filters')
    workflows = orm.Set('Workflow', reverse="defect_projects")


class Workflow(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(unicode)
    statuses = orm.Set(ToolIssueStatus, reverse="workflows")
    resolutions = orm.Set(ToolIssueResolution, reverse="workflows")
    projects = orm.Set(ToolProject, reverse="workflows")
    categories = orm.Set(ToolProjectCategory, reverse="workflows")
    defect_projects = orm.Set(WorkflowDefectProjectFilter, reverse="workflows")


db.bind('sqlite', filename='../../../augur.sqlite', create_db=True)
db.generate_mapping(create_tables=True)


@db_session
def prepopulate():
    import os

    statuses = []
    resolutions = []
    issuetypes = []
    if orm.select(tir for tir in ToolIssueResolution).count() == 0:
        for tir in (("fixed","positive"),("done","positive"),("complete","positive"),
                    ("won't do","negative"),("duplicate","negative"), ("not an issue","negative")):
            resolutions.append(ToolIssueResolution(tool_issue_resolution_name=tir[0],tool_issue_resolution_type=tir[1]))

    if orm.select(tis for tis in ToolIssueStatus).count() == 0:
        for tis in (("open","open"),("blocked","in progress"),("quality review","in progress"),
                    ("staging","in progress"),("production","in progress"), ("resolved","done")):
            statuses.append(ToolIssueStatus(tool_issue_status_name=tis[0],tool_issue_status_type=tis[1]))

    if orm.select(tit for tit in ToolIssueType).count() == 0:
        for tit in ("story","bug","task","sub-task","defect"):
            issuetypes.append(ToolIssueType(tool_issue_type_name=tit))

    if orm.select(s for s in Staff).count() == 0:
        path_to_csv = os.path.join(augur.settings.main.project.augur_base_dir, 'data/engineering_consultants.csv')
        all_staff = augur.models.AugurModel.import_from_csv(path_to_csv, staff.Staff)
        for a in all_staff:
            Staff(
                first_name=a.first_name,
                last_name=a.last_name,
                company=a.company,
                avatar_url=a.avatar_url,
                role=a.role,
                email=a.email,
                rate=a.rate,
                start_date=a.start_date,
                jira_username=a.jira_username,
                github_username=a.github_username,
                status=a.status,
                base_daily_cost=a.base_daily_cost,
                base_weekly_cost=a.base_weekly_cost,
                base_annual_cost=a.base_annual_cost,
            )

    if orm.select(t for t in Product).count() == 0:
        path_to_csv = os.path.join(augur.settings.main.project.augur_base_dir, 'data/products.csv')
        items = augur.models.AugurModel.import_from_csv(path_to_csv, product.Product)
        for a in items:
            Product(
                name=a.name,
                key=a.id
            )

    if orm.select(t for t in Team).count() == 0:
        path_to_csv = os.path.join(augur.settings.main.project.augur_base_dir, 'data/teams.csv')
        items = augur.models.AugurModel.import_from_csv(path_to_csv, team.Team)
        for a in items:
            board_id = a.board_id
            b = orm.get(b for b in AgileBoard if b.jira_id == a.board_id)
            if not b:
                b = AgileBoard(
                    jira_id=board_id
                )

            p = orm.get(p for p in Product if p.key.lower() == a.product_id.lower())
            t = Team(
                name=a.name,
                product=p ,
                agile_board=b
            )

            members = orm.select(m for m in Staff if m.jira_username in a.member_ids)
            t.members = members

    if orm.select(w for w in Workflow).count() == 0:
        path_to_yaml = os.path.join(augur.settings.main.project.augur_base_dir, 'data/workflows.yaml')
        items = augur.models.AugurModel.import_from_yaml(path_to_yaml, workflow.Workflow)
        for a in items:
            projects = []
            project_categories = []
            defect_projects = []

            for k in a.projects.keys:
                tp = ToolProject(
                    tool_project_key=k
                )
                projects.append(tp)

            for c in a.projects.categories:
                tpc = ToolProjectCategory(
                    tool_category_name=c
                )
                project_categories.append(tpc)

            for d in a.defects:
                wdpf = WorkflowDefectProjectFilter(project_key=d.key)
                for it in d.issuetypes:
                    x = orm.get(it1 for it1 in ToolIssueType if it1.tool_issue_type_name.lower() == it.lower())
                    if x:
                        wdpf.issue_types.add(x)
                defect_projects.append(wdpf)

            wf = Workflow(name=a.name)
            wf.statuses.add(statuses)
            wf.resolutions.add(resolutions)
            wf.projects.add(projects)
            wf.categories.add(project_categories)
            wf.defect_projects.add(defect_projects)


    commit()
