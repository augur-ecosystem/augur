"""
The purpose of this file is to prepare the tests with the secrets that should be used in order to login to the
integrated tools like Github and Jira.  Copy this file and rename it to env.py and fill in with the correct
values before running the tests.
"""
import os


def init():
    os.environ['GITHUB_CLIENT_ID']=""
    os.environ['GITHUB_CLIENT_SECRET']=""

    os.environ['JIRA_USERNAME']=""
    os.environ['JIRA_PASSWORD']=""
    os.environ["JIRA_INSTANCE"] = "" # Example: https://underarmour.atlassian.net"
    os.environ["JIRA_API_REL"] = "" # Example: rest/api/2