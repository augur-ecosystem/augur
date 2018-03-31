import logging
import unittest
import json
import os
import pprint

import sys
from munch import munchify
from pony import orm

from augur import db
from augur.context import AugurContext
from augur.integrations.objects.board import JiraBoard, JiraSprint
from augur import settings
from augur.integrations.augurjira import AugurJira
from augur.integrations.objects.issue import JiraIssueCollection
from augur.integrations.objects.metrics import IssueCollectionMetrics, BoardMetrics

FIXTURE_DIR = os.path.join(os.path.dirname(__file__),"fixtures")


def translate_fixture(value):
    if value.startswith("@env:"):
        env_variable = value[5:]
        return os.getenv(env_variable,"")
    else:
        return value


class TestObject(unittest.TestCase):

    def __init__(self, *args, **kwargs):

        logging.basicConfig( stream=sys.stdout )
        self.log = logging.getLogger("TestObject")
        self.log.setLevel(logging.INFO)

        fixture_file = os.environ.get('FIXTURE_FILE_NAME', 'fixtures.json')

        with open(os.path.join(FIXTURE_DIR,fixture_file)) as f:
            self.fixture = munchify(json.load(f))

        self.jira = None
        self.pp = pprint.PrettyPrinter(indent=4)

        os.environ['DB_TYPE'] = self.fixture.connections.db.type
        os.environ["POSTGRES_DB_HOST"] = self.fixture.connections.db.postgres.host
        os.environ["POSTGRES_DB_NAME"] = self.fixture.connections.db.postgres.dbname
        os.environ["POSTGRES_DB_USERNAME"] = self.fixture.connections.db.postgres.username
        os.environ["POSTGRES_DB_PASSWORD"] = self.fixture.connections.db.postgres.password
        os.environ["POSTGRES_DB_PORT"] = str(self.fixture.connections.db.postgres.port)

        settings.load_settings()
        db.init_db()

        super(TestObject, self).__init__(*args, **kwargs)

    def setUp(self):

        self.jira = AugurJira(
            server=translate_fixture(self.fixture.connections.jira.server),
            username=translate_fixture(self.fixture.connections.jira.username),
            password=translate_fixture(self.fixture.connections.jira.password))

    def create_context(self):
        return AugurContext(group_id=self.fixture.context.group)

    def test_board(self):

        with orm.db_session:

            context = self.create_context()

            # board_from_id = JiraBoard(self.jira, board_id=self.fixture.jira_test_data.board)
            #
            board_from_team = JiraBoard(self.jira, team_id=self.fixture.jira_test_data.team,
                                        max_sprints=2, restrict_sprints_with_team_name=True,
                                        include_sprint_reports=True)

            self.log.info("Retrieving board from Team %d"%self.fixture.jira_test_data.team)
            self.assertTrue(board_from_team.load())
            sprints = board_from_team.get_sprints()
            print (str(sprints))

            self.log.info("Getting most recent active sprints...")
            sprint1 = board_from_team.get_most_recent_active_sprint()
            self.assertIsInstance(sprint1, JiraSprint)

            sprint2 = board_from_team.get_most_recent_active_sprint()
            self.assertIsInstance(sprint2, JiraSprint)

            self.log.info("Getting most recent closed sprints...")
            sprint3 = board_from_team.get_most_recent_closed_sprint()
            self.assertIsInstance(sprint3, JiraSprint)

            sprint4 = board_from_team.get_most_recent_closed_sprint()
            self.assertIsInstance(sprint4, JiraSprint)

            self.log.info("Getting backlog...")
            backlog = board_from_team.get_backlog()
            self.assertIsInstance(backlog, JiraIssueCollection)

            self.log.info("Getting backlog metrics...")
            board_metrics = BoardMetrics(context,board_from_team)
            backlog_metrics = board_metrics.backlog_analysis()
            self.assertIn('points', backlog_metrics)
            self.assertIn('grade', backlog_metrics)
            self.pp.pprint(backlog_metrics)

            self.log.info("Getting sprint metrics...")
            sprint_metrics = board_metrics.historic_sprint_analysis()
            self.assertIn('avg_velocity', sprint_metrics)
            self.pp.pprint(sprint_metrics)

    def test_issues(self):
        with orm.db_session:

            context = self.create_context()

            collection = JiraIssueCollection(self.jira,
                                             input_jql=self.fixture.jira_test_data.jql.created_last_three_days)
            result = collection.load()
            self.assertTrue(result, "Collection load failed")

            metrics = IssueCollectionMetrics(context, collection)
            status_analysis = metrics.status_analysis()
            self.assertIn('in_progress', status_analysis, "Missing key in status analysis")

            point_analysis = metrics.point_analysis()
            self.assertIn('developer_stats',point_analysis, "Invalid point analysis result")

            timing_analysis = metrics.timing_analysis()
            self.assertIn(collection.issues[0].key, timing_analysis.issues, "Missing key in timing analysis")

            df = metrics.get_data_frame(('points','timing','status'))
            print df.describe()


def suite():
    tests = ['test_issues']
    return unittest.TestSuite(map(TestObject, tests))


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
