from marshmallow import Schema, fields, ValidationError, pprint, post_load
import augur


def validate_resolution_types(s):
    if s not in augur.db.TOOL_ISSUE_RESOLUTION_TYPES:
        raise ValidationError("{} is not a valid resolution type".format(s))


def validate_issue_status_type(s):
    if s not in augur.db.TOOL_ISSUE_STATUS_TYPES:
        raise ValidationError("{} is not a valid issue status type".format(s))


def validate_issue_type_types(s):
    if s not in augur.db.TOOL_ISSUE_TYPE_TYPES:
        raise ValidationError("{} is not a valid issue type type".format(s))


def validate_staff_roles(s):
    if s not in augur.db.ROLES:
        raise ValidationError("{} is not a valid staff role".format(s))


def validate_staff_types(s):
    if s not in augur.db.STAFF_TYPES:
        raise ValidationError("{} is not a valid staff type".format(s))


def validate_staff_status(s):
    if s not in augur.db.STATUS:
        raise ValidationError("{} is not a valid staff status".format(s))


def validate_notification_targets(s):
    if s:
        targets = s.split(",")
    else:
        return

    for t in targets:
        if t.trim() not in augur.db.NOTIFY_TYPES:
            raise ValidationError("{} is not a valid notification target".format(t))


def validate_build_types(s):
    if s:
        types = s.split(",")
    else:
        return

    for t in types:
        if t.trim() not in augur.db.BUILD_TYPES:
            raise ValidationError("{} is not a valid build type".format(t))


class ToolIssueResolutionSchema (Schema):
    id = fields.Integer()
    tool_issue_resolution_name = fields.String()
    tool_issue_resolution_type = fields.String(validate=validate_resolution_types)


class ToolIssueStatusSchema (Schema):
    id = fields.Integer()
    tool_issue_status_name = fields.String()
    tool_issue_status_type = fields.String(validate=validate_issue_status_type)


class ToolIssueTypeSchema (Schema):
    id = fields.Integer()
    tool_issue_type_name = fields.String()
    tool_issue_type_type = fields.String(validate=validate_issue_type_types)


class VendorSchema (Schema):
    id = fields.Integer()
    name = fields.String()
    engagement_contact_first_name = fields.String()
    engagement_contact_last_name = fields.String()
    engagement_contact_email = fields.Email()
    billing_contact_first_name = fields.String()
    billing_contact_last_name = fields.String()
    billing_contact_email = fields.Email()
    tempo_id = fields.Integer()
    consultants = fields.Nested('StaffSchema', many=True)


class ProductSchema (Schema):
    id = fields.Integer()
    name = fields.String()
    key = fields.String()
    teams = fields.Nested('TeamSchema', many=True)


class ToolProjectSchema (Schema):
    id = fields.Integer()
    tool_project_key = fields.String()


class ToolProjectCategorySchema (Schema):
    id = fields.Integer()
    tool_category_name = fields.String()


class StaffSchema (Schema):
    id = fields.Integer()
    first_name = fields.String()
    last_name = fields.String()
    company = fields.String()
    avatar_url = fields.Url()
    role = fields.String(validate=validate_staff_roles)
    email = fields.Email()
    rate = fields.Float()
    start_date = fields.DateTime()
    type = fields.String(validate=validate_staff_types)
    jira_username = fields.String()
    slack_id = fields.String()
    github_username = fields.String()
    status = fields.String(validate=validate_staff_status)
    teams = fields.Nested('TeamSchema', many=True, only=('id','name'))
    base_daily_cost = fields.Float()
    base_weekly_cost = fields.Float()
    base_annual_cost = fields.Float()
    vendor = fields.Nested('VendorSchema', only=('id', 'name'))
    notification = fields.Nested('NotificationSchema')

    @post_load
    def make_staff_entity(self, data):
        from augur.db import Staff
        if 'id' in data:
            # load an existing object and update with the given data.
            s = Staff[data['id']]
            data.pop('id')

            # If there is no data to update then we can skip the update.
            if data:
                s.set(**data)

            return s
        else:
            # create a new staff object
            return Staff(**data)


class AgileBoardSchema (Schema):
    id = fields.Integer()
    jira_id = fields.Integer()


class TeamSchema (Schema):
    id = fields.Integer()
    name = fields.String()
    members = fields.Nested('StaffSchema', only=('id', 'email', 'first_name', 'last_name', 'jira_username', 'github_username'), many=True)
    agile_board = fields.Nested('AgileBoardSchema')
    product = fields.Nested('ProductSchema', only=('id', 'name', 'key'))
    groups = fields.Nested('GroupSchema', only=('id', 'name', 'workflow.name', 'workflow.id'), many=True)
    notification = fields.Nested('NotificationSchema')


class NotificationSchema (Schema):
    id = fields.Integer()
    build = fields.String(validate=validate_notification_targets)
    deploy = fields.String(validate=validate_notification_targets)
    build_types = fields.String(validate=validate_build_types)


class WorkflowDefectProjectFilterSchema (Schema):
    id = fields.Integer()
    project_key = fields.String()
    issue_types = fields.Nested('ToolIssueTypeSchema', many=True)


class GroupSchema (Schema):

    id = fields.Integer()
    name = fields.String()
    workflow = fields.Nested('WorkflowSchema', only=['id','name','statuses','resolutions','projects','categories',
                                                     'issue_types','defect_projects'], many=False)
    products = fields.Nested(ProductSchema, only=['id','name', 'key', 'teams.id','teams.name'], many=True)
    teams = fields.Nested(TeamSchema, only=['id', 'name', 'members.id', 'members.first_name',
                                            'members.last_name', 'members.email'], many=True)


class WorkflowSchema (Schema):
    id = fields.Integer()
    name = fields.String()
    statuses = fields.Nested(ToolIssueStatusSchema, many=True)
    resolutions = fields.Nested(ToolIssueResolutionSchema, many=True)
    projects = fields.Nested(ToolProjectSchema, many=True)
    categories = fields.Nested(ToolProjectCategorySchema, many=True)
    issue_types = fields.Nested(ToolIssueTypeSchema, many=True)
    defect_projects = fields.Nested(WorkflowDefectProjectFilterSchema, many=True)
    groups = fields.Nested(GroupSchema, many=True)
