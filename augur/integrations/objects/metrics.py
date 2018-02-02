import datetime
from munch import Munch, munchify

from augur import common
from pony import orm


class Metrics(object):
    def __init__ (self, context):
        self.context = context


class IssueCollectionMetrics(Metrics):

    def __init__(self, context, collection):
        self.collection = collection
        super(IssueCollectionMetrics, self).__init__(context)

    def status_analysis(self, options=None):
        status_counts = {
            'remaining_ticket_count': 0
        }

        for issue in self.collection:
            status_as_key = common.status_to_dict_key(issue.status)
            if status_as_key not in status_counts:
                status_counts[status_as_key] = 0
            status_counts[status_as_key] += 1

            if not self.context.workflow.is_resolved(issue.status, issue.resolution):
                status_counts['remaining_ticket_count'] += 1

        return munchify(status_counts)

    def timing_analysis(self, options=None):
        """
        For each issue in the collection, this will create an item a dictionary keyed on the issue key
        for each issue with the value being a dictionary containing the start, end and total times for each
        status along with the full in progress time.
        :param options: ----no options----
        :return: dict
        """

        issues_with_timing = {}
        for issue in self.collection:
            # initialize all the keys for stats
            total_time_to_complete = 0
            timing = {}
            for s in self.context.workflow.in_progress_statuses():
                total_status_str_prepped = "time_%s" % common.status_to_dict_key(s)
                start_status_str_prepped = "start_time_%s" % common.status_to_dict_key(s)
                end_status_str_prepped = "end_time_%s" % common.status_to_dict_key(s)

                t = common.get_issue_status_timing_info(issue.issue, s)

                total_time_to_complete += t['total_time'].total_seconds()
                timing[total_status_str_prepped] = t['total_time']
                timing[start_status_str_prepped] = t['start_time']
                timing[end_status_str_prepped] = t['end_time']

            timing['total_time_to_complete'] = datetime.timedelta(seconds=total_time_to_complete)
            issues_with_timing[issue.key] = (munchify(timing))

        return munchify(issues_with_timing)

    def point_analysis(self, options=None):
        """
        Does a very general analysis of a collection of issues
        :param options:
                - total_only (Boolean): If True, then issue details will not be included in many of the results -
                        just the totals
        :return:
        """

        options = munchify(options)

        # Initialize the general analytics
        result = Munch({
            "ticket_count": self.collection.count(),
            "remaining_ticket_count": 0,
            "unpointed": 0.0,
            'developer_stats': {},
            'issues': {},
        })

        # Initialize the status counters
        result.update({common.status_to_dict_key(x): 0 for x in self.context.workflow.statuses})

        # Initialize point totals
        result.update({
            "complete": 0.0,
            "incomplete": 0.0,
            "total_points": 0.0,
            "percent_complete": 0,
            "abandoned": 0.0,
        })

        for issue in self.collection:
            assignee_cleaned = common.clean_username(issue.assignee)

            if issue.assignee not in result['developer_stats']:
                result['developer_stats'][assignee_cleaned] = Munch({
                    "info": issue.assignee,
                    "complete": 0,
                    "incomplete": 0,
                    "abandoned": 0,
                    "percent_complete": 0,
                    'issues': []
                })

            # Add this issue to the list of issues for the user
            result['developer_stats'][assignee_cleaned]['issues'].append(issue.key)

            if self.context.workflow.is_resolved(issue.status, issue.resolution):
                result['complete'] += issue.points
                result['developer_stats'][assignee_cleaned]['complete'] += issue.points

            elif self.context.workflow.is_abandoned(issue.status, issue.resolution):
                result["abandoned"] += issue.points
                result['developer_stats'][assignee_cleaned]['abandoned'] += issue.points

            else:
                result["incomplete"] += issue.points
                result['developer_stats'][assignee_cleaned ]['incomplete'] += issue.points

            if not issue.points and not self.context.workflow.is_abandoned(issue.status, issue.resolution):
                result['unpointed'] += 1

        total_points = result['complete'] + result['incomplete'] + result['abandoned']
        result["percent_complete"] = int(((result['complete'] / total_points) if total_points > 0 else 0) * 100.0)
        result['total_points'] = total_points

        # get dev specific stats
        for assignee, dev in result['developer_stats'].iteritems():
            total = dev['complete'] + dev['incomplete'] + dev['abandoned']
            dev['percent_complete'] = int((dev['complete'] / total if total > 0 else 0) * 100.0)
            dev['total_points'] = total

        return munchify(result)


class BoardMetrics(Metrics):

    def __init__(self, context, board):
        self._board = board
        super(BoardMetrics, self).__init__(context)

    def backlog_analysis(self, options):

        collection = self._board.get_backlog()

        simplified_issue_list = []

        metrics = {
            "issues": simplified_issue_list,
            "points":{
                "unpointed":[],
                # pointed stories will be grouped by number of points keyed on their point value converted to string
            },
            "grade":""
        }

        pointed = 0
        unpointed = 0

        for issue in collection.issues:

            if not issue.points:
                metrics['points']['unpointed'].append(issue.key)
                unpointed += 1
            else:
                pointed += 1
                key = str(issue.points)
                if key not in metrics['points']:
                    metrics['points'][key] = []

                metrics['points'][key].append(issue.key)

        total = pointed+unpointed
        if total > 0:
            percentage = (float(pointed)/float(total))*100.0
        else:
            percentage = 0.0

        metrics['total_unpointed_tickets'] = unpointed
        metrics['total_pointed_tickets'] = pointed
        metrics['pointed_percentage'] = percentage

        # now look at velocity for that board
        # sprints = self.get_sprints_from_boardby_team(team)

        if percentage >= 90.0:
            grade = "A"
        elif percentage >= 80.0:
            grade = "B"
        elif percentage >= 70.0:
            grade = "C"
        elif percentage >= 60.0:
            grade = "D"
        else:
            grade = "E"

        metrics['grade'] = grade

        return munchify(metrics)