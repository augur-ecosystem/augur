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
        self.assertEqual(org_ob.login,'harbour')

        self.assertIsNotNone(repo_ob)
        self.assertEqual(repo_ob.name,'service-tax')

    def test_fetch_organization_members(self):
        gh = augur.api.get_github()
        members = gh.fetch_organization_members('apps')
        self.assertTrue(len(members) != 0)

    def test_get_organization(self):
        gh = augur.api.get_github()
        org1 = gh.get_organization("apps")
        self.assertIsNotNone(org1)

        org2 = gh.get_organization("kshehadeh")
        self.assertIsNotNone(org2)

    def test_get_org_component_data(self):
        gh = augur.api.get_github()
        cmpdata = gh.get_org_component_data("apps")
        self.assertIsInstance(cmpdata,dict)
        self.assertIn('repos',cmpdata)
