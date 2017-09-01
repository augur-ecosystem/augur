import unittest

import datetime
from jira import JIRA, Issue

from augurjira import AugurJira
from augur.api import get_jira


class TestAugurJira(unittest.TestCase):
    def setUp(self):
        # Must set this in environment before running
        # os.environ['GITHUB_CLIENT_ID']=""
        # os.environ['JIRA_USERNAME']=""
        # os.environ['JIRA_PASSWORD']=""
        # os.environ['GITHUB_CLIENT_SECRET']=""
        # os.environ["JIRA_INSTANCE"] = ""
        # os.environ["JIRA_API_REL"] = "rest/api/2"
        pass

    def test_get_jira(self):
        j = get_jira()
        self.assertIsNotNone(j)
        self.assertTrue(hasattr(j, 'execute_jql'))

    def test_get_jira_proxy(self):
        j = get_jira()
        jp = j.get_jira_proxy()
        self.assertIsNotNone(jp)
        self.assertIsInstance(jp, JIRA)

    def test_get_projects_with_category(self):
        j = get_jira()
        p = j.get_projects_with_category("AugurTestCategory")
        self.assertIsInstance(p, list)
        self.assertTrue(len(p) == 1)
        self.assertIsInstance(p[0], dict)

    def test_get_projects_with_key(self):
        j = get_jira()
        p = j.get_projects_with_key("AGTEST")
        self.assertIsInstance(p, list)
        self.assertTrue(len(p) == 1)
        self.assertIsInstance(p[0], dict)

        p = j.get_projects_with_key("AGTEST____")
        self.assertIsInstance(p, list)
        self.assertTrue(len(p) == 0)

    def test_get_project_components(self):
        j = get_jira()
        c = j.get_project_components("AGTEST")
        self.assertIsInstance(c, list)
        self.assertTrue(len(c) == 2)
        self.assertTrue(c[0].name in ['Component1', 'Component2'])

    def test_get_group_data(self):
        j = get_jira()
        g = j.get_group_data("AGTEST_")
        self.assertIsInstance(g, list)
        self.assertTrue(len(g) == 1)

    def test_group_members(self):
        j = get_jira()
        g = j.get_group_members(j.get_group_data("AGTEST_"))
        self.assertIsInstance(g, dict)
        self.assertTrue(len(g) >= 1)

    def test_execute_jql(self):
        j = get_jira()
        issues = j.execute_jql("project=AGTEST")
        self.assertIsInstance(issues, list)
        self.assertTrue(len(issues) >= 1)
        self.assertIsInstance(issues[0], dict)

    def test_execute_jql_with_analysis(self):
        j = get_jira()
        issues = j.execute_jql_with_analysis("project=AGTEST")
        self.assertIsInstance(issues, dict)
        self.assertTrue(len(issues) >= 1)
        self.assertTrue('complete' in issues)
        self.assertTrue('incomplete' in issues)
        self.assertTrue('total_points' in issues)
        self.assertTrue('abandoned' in issues)
        self.assertTrue('percent_complete' in issues)
        self.assertTrue('open' in issues)
        self.assertTrue('unpointed' in issues)
        self.assertTrue('ticket_count' in issues)
        self.assertTrue('remaining_ticket_count' in issues)
        self.assertTrue('developer_stats' in issues)
        self.assertTrue('issues' in issues)
        self.assertIsInstance(issues['issues'], dict)

    def test_get_associated_epic(self):
        j = get_jira()
        issue = j.execute_jql("key=AGTEST-3")
        self.assertTrue(len(issue) > 0)

        epic = j.get_associated_epic(issue[0])
        self.assertIsNotNone(epic)
        self.assertEqual(epic['key'], 'AGTEST-1')

    def test_get_worklog_raw(self):
        j = get_jira()
        logs = j.get_worklog_raw("2017-07-01", "2017-07-10", 19, "kshehadeh")
        self.assertIsInstance(logs, dict)
        self.assertIn('logs', logs)
        self.assertIn('consultants', logs)
        self.assertIn('kshehadeh', logs['consultants'])
        self.assertIn('tempo_team_info', logs)

    def test_get_total_time_for_user(self):
        j = get_jira()
        issue = j.execute_jql("key=AGTEST-3")
        self.assertTrue(len(issue) > 0)
        t = AugurJira.get_total_time_for_user(issue[0], 'kshehadeh')
        self.assertIsInstance(t, datetime.timedelta)

    def test_link_issues(self):
        j = get_jira()
        issues = j.execute_jql("key in ('AGTEST-3','AGTEST-4')")
        self.assertTrue(len(issues) > 0)
        j.link_issues('is blocking', issues[0], issues[1])

    def test_create_and_delete_ticket(self):

        import augur
        j = get_jira()
        field_name = augur.api.get_issue_field_from_custom_name("Epic Link")

        create_fields = {
            field_name: "AGTEST-1",
            "project": 'AGTEST',
            "summary": 'TestTicket',
            "description":'Description',
            "issuetype": {'name': 'Task'},
        }

        i = j.create_ticket(create_fields,)

        self.assertIsInstance(i, Issue)
        self.assertEqual(i.fields.summary, 'TestTicket')
        self.assertEqual(i.fields.description, 'Description')

        result = j.delete_ticket(i.key)
        self.assertTrue(result)

    def test_sprint_retrieval(self):
        j = get_jira()
        sprints = j.get_sprints_from_board(863)

        self.assertIsInstance(sprints, list)
        self.assertTrue(len(sprints) > 0)

        sprint = sprints[0]
        self.assertIn('id', sprint)
        sprint_details = j.sprint_info(862,sprint['id'])
        self.assertIsInstance(sprint_details, dict)

    def test_clean_username(self):
        result = AugurJira._clean_username("this.has.periods")
        self.assertEquals(result, "this_has_periods")

    def test_time_in_status(self):
        j = get_jira()
        issues = j.execute_jql("key=AGTEST-3")
        result = j.get_time_in_status(issues[0],"In Progress")
        self.assertIsInstance(result,datetime.timedelta)
        self.assertTrue(result.total_seconds() > 1)
