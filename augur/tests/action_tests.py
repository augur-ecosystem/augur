import datetime
import unittest
from augur.actions import component_report,engineering_report
from augur.actions import release_report
from augur.actions import stale_doc_report
from augur.actions import team_report
from augur.common import const, Struct
from augur import settings
import env

class ActionTests(unittest.TestCase):

    def setUp(self):
        """Call before every test case."""
        env.init()
        settings.load_settings()

    def tearDown(self):
        """Call after every test case."""
        pass

    def testComponentReport(self):

        args = Struct(**{
            "output_format": const.OUTPUT_FORMAT_HTML,
            "output_type": const.OUTPUT_TYPE_NONE,
            "org": "apps"
        })
        action = component_report.ComponentReportAction(args)
        action.run()

        self.assertIsNotNone(action.report_data_json)
        self.assertIsInstance(action.report_data_json,dict)
        self.assertIn('org',action.report_data_json)
        self.assertIn('repos',action.report_data_json)
        self.assertIsInstance(action.report_data_json['org'],(unicode,str))
        self.assertIsInstance(action.report_data_json['repos'],list)

    def testEngineeringReport(self):

        args = Struct(**{
            "output_format": const.OUTPUT_FORMAT_HTML,
            "output_type": const.OUTPUT_TYPE_NONE,
            "week_number": int(datetime.datetime.now().strftime("%V"))
        })
        action = engineering_report.EngineeringReportAction(args)
        action.run()

        self.assertIsNotNone(action.report_data_json)
        self.assertIsInstance(action.report_data_json,dict)

        for key in ['epics','staff','sprint','defects','week_number','start','end']:
            self.assertIn(key,action.report_data_json)
            self.assertIsNotNone(key,action.report_data_json)

    def testReleaseReport(self):
        args = Struct(**{
            "output_format": const.OUTPUT_FORMAT_HTML,
            "output_type": const.OUTPUT_TYPE_NONE,
        })

        action = release_report.ReleaseReportAction(args)
        action.run()

        self.assertIsNotNone(action.report_data_json)
        self.assertIsInstance(action.report_data_json,dict)

        for key in ['release_date','issues']:
            self.assertIn(key,action.report_data_json)
            self.assertIsNotNone(key,action.report_data_json)

        self.assertIsInstance(action.report_data_json['issues'],list)
        self.assertIsInstance(action.report_data_json['release_date'],(str,unicode))

    def testStaleDocReport(self):
        args = Struct(**{
            "output_format": const.OUTPUT_FORMAT_HTML,
            "output_type": const.OUTPUT_TYPE_NONE,
            "space": "ENG",
            "email_authors": False,
            "stale_in_weeks": 12
        })

        action = stale_doc_report.StaleDocReportAction(args)
        action.run()

        self.assertIsNotNone(action.report_data_json)
        self.assertIsInstance(action.report_data_json,dict)

        for key in ['pages_by_user']:
            self.assertIn(key,action.report_data_json)
            self.assertIsNotNone(key,action.report_data_json)

        self.assertIsInstance(action.report_data_json['pages_by_user'],dict)

    def testTeamReport(self):
        args = Struct(**{
            "output_format": const.OUTPUT_FORMAT_HTML,
            "output_type": const.OUTPUT_TYPE_NONE,
        })

        action = team_report.TeamReportAction(args)
        action.run()

        self.assertIsNotNone(action.report_data_json)
        self.assertIsInstance(action.report_data_json,dict)

        for key in ['teams']:
            self.assertIn(key,action.report_data_json)
            self.assertIsNotNone(key,action.report_data_json)

        self.assertIsInstance(action.report_data_json['teams'],dict)
