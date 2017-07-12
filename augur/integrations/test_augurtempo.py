import unittest
import datetime
import augur
from augur.integrations.augurtempo import AugurTempo

TEMPO_API_TOKEN="72c7fe70-eac9-4497-a3a1-e29ce4c47d41"


class TestAugurTempo(unittest.TestCase):

    def setUp(self):
        def setUp(self):
            # Must set this in environment before running
            # os.environ['GITHUB_CLIENT_ID']=""
            # os.environ['JIRA_USERNAME']=""
            # os.environ['JIRA_PASSWORD']=""
            # os.environ['GITHUB_CLIENT_SECRET']=""
            # os.environ["JIRA_INSTANCE"] = ""
            # os.environ["JIRA_API_REL"] = "rest/api/2"
            pass

    def test_get_worklogs(self):
        t = AugurTempo(augur.api.get_jira())

        now = datetime.datetime.now()
        then = now - datetime.timedelta(days=7)

        results = t.get_worklogs(then, now, 27)
        self.assertIsNotNone(results)
        self.assertIsNotNone(results)
        self.assertIsInstance(results,list)
        self.assertTrue(len(results) > 0, "The list of worklogs returned is empty")
        self.assertIn('comment', results[0], "Did not find an expected field in the first worklog returned")

    def get_team_details(self):

        t = AugurTempo(augur.api.get_jira())
        results = t.get_team_details(27)
        self.assertIsInstance(results,dict)
        self.assertIn('name',results)