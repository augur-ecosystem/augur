import unittest

import datetime

import augur
from augur.integrations.augurgithub import AugurGithub


class TestAugurGithub(unittest.TestCase):
    def setUp(self):
        # Must set this in environment before running
        # os.environ['GITHUB_CLIENT_ID']=""
        # os.environ['JIRA_USERNAME']=""
        # os.environ['JIRA_PASSWORD']=""
        # os.environ['GITHUB_CLIENT_SECRET']=""
        # os.environ["JIRA_INSTANCE"] = ""
        # os.environ["JIRA_API_REL"] = "rest/api/2"
        pass

    def test_get_github(self):
        gh = augur.api.get_github()
        self.assertIsInstance(gh, AugurGithub)

    def test_get_org_and_repo_from_params(self):
        gh = augur.api.get_github()
        org_ob, repo_ob = gh.get_org_and_repo_from_params("service-tax", "harbour")
        self.assertIsNotNone(org_ob)
        self.assertEqual(org_ob.login == 'harbour')

        self.assertIsNotNone(repo_ob)
        self.assertEqual(repo_ob.name == 'service-tax')

    def test_fetch_prs(self):
        gh = augur.api.get_github()
        since=datetime.datetime.now()-datetime.timedelta(days=30)
        prs = gh.fetch_prs(org="harbour",state="merged",since=since)
        self.assertTrue(len(prs) != 0)

