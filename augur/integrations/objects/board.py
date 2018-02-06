from munch import munchify

from augur import db, common
from pony import orm

from jira import Sprint

from augur.integrations.objects.base import JiraObject, InvalidId, InvalidData
from augur.integrations.objects.issue import JiraIssueCollection


class JiraSprint(JiraObject):
    """
    JiraSprint objects can be loaded using a sprint ID for basic information or for more of a report on a sprint,
    it will require both the sprint ID and the board ID.

    Options:
        sprint_id - The ID of the sprint in Jira
        board_id (optional) - The agile board (rapid board) ID in Jira
        include_reports (optional, Default=False) - If True then, when loading from Jira, there will be two calls.
                            One to load the sprint details and one to return the sprint report.
    """

    def __init__(self, source, **kwargs):
        super(JiraSprint, self).__init__(source, **kwargs)
        self._sprint_report = None
        self._sprint = None

    def __str__(self):
        if not self._sprint:
            return "<Unpopulated JiraSprint object>"
        else:
            return "%s (start: %s, end: %s)" % (self._sprint.name,
                                                self.start_date.isoformat() if self.start_date else "None",
                                                self.end_date.isoformat() if self.end_date else "None")

    @property
    def start_date(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet.")
            return False

        if isinstance(self._sprint.startDate, (str, unicode)):
            # convert if necessary
            start_date = self._convert_date_string_to_date_time(self._sprint.startDate)
            if start_date:
                self._sprint.startDate = start_date
            else:
                return None

        return self._sprint.startDate

    @property
    def completed_points(self):
        if not self._sprint_report:
            self.logger.error("You must provide the completed sprints")

        return self._sprint_report.completedIssuesEstimateSum.value if 'value' in self._sprint_report.completedIssuesEstimateSum else 0

    @property
    def incomplete_points(self):
        if not self._sprint_report:
            self.logger.error("You must provide the completed sprints")

        return self._sprint_report.issuesNotCompletedEstimateSum.value if 'value' in self._sprint_report.issuesNotCompletedEstimateSum else 0

    @property
    def end_date(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet.")
            return False

        if isinstance(self._sprint.endDate, (str, unicode)):
            # convert if necessary
            end_date = self._convert_date_string_to_date_time(self._sprint.endDate)
            if end_date:
                self._sprint.endDate = end_date
            else:
                return None

        return self._sprint.endDate

    @property
    def average_point_size(self):
        if not self._sprint_report:
            self.logger.error("JiraSprint: No sprint report has been loaded yet.")
            return None

        points = 0.0
        for issue in self._sprint_report.completedIssues:
            if 'estimateStatistic' in issue and 'statFieldValue' in issue.estimateStatistic and \
                    'value' in issue.estimateStatistic.statFieldValue:
                points += float(issue.estimateStatistic.statFieldValue.value)

        if len(self._sprint_report.completedIssues) > 0:
            return points / float(len(self._sprint_report.completedIssues))
        else:
            return 0

    @property
    def completed_date(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet.")
            return None

        if isinstance(self._sprint.completedDate, (str, unicode)):
            # convert if necessary
            completed_date = self._convert_date_string_to_date_time(self._sprint.completedDate)
            if completed_date:
                self._sprint.completedDate = completed_date
            else:
                return None

        return self._sprint.completedDate

    @property
    def name(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet")
            return None

        return self._sprint.name

    @property
    def state(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet")
            return None

        return self._sprint.state

    @property
    def future(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet")
            return None

        return self._sprint.state.lower() == "future"

    @property
    def active(self):
        if not self._sprint:
            self.logger.error("JiraSprint: No sprint has been loaded yet")
            return None

        return self._sprint.state.lower() == 'active'

    def _load(self):

        if not self.option("sprint_id"):
            self.logger.error("JiraSprint: Sprint ID must be given")
            return False

        if self.option('include_report'):
            if self.option('board_id'):
                if not self._sprint_report:
                    self._load_sprint_report()
            else:
                self.logger.error("JiraSprint: To get a full sprint report you need to provide the board_id option")
                return False
        else:
            if not self._sprint:
                self._load_sprint()

        return True

    def _load_sprint_report(self):
        sprint_id = self.option("sprint_id")
        board_id = self.option("board_id")

        sprint_report = munchify(self.source.jira.sprint_report(board_id, sprint_id))

        if sprint_report:

            # only grab the contents area which contains the meatiest bits.
            self._sprint_report = munchify(sprint_report.contents)

            # the sprint report is a superset of the sprint object.  The sprint key in the sprint report object
            #   contains the same keys plus a few more so we can reuse it for the sprint object so that both
            #   can be used without having to do a load twice.
            self._sprint = munchify(sprint_report.sprint)

            return True
        else:
            self.logger.error("JiraSprint: Unable to load sprint report data from Jira")
            return False

    def _load_sprint(self):

        sprint_id = self.option("sprint_id")
        s = self.source.jira.sprint(sprint_id)
        if s:
            self._sprint = munchify(s)
        else:
            self._sprint = None
            self.logger.error("JiraSprint: Unable to find the sprint with this id: %s" % str(sprint_id))
            return False

    def prepopulate(self, data):
        if 'contents' in data:
            self._sprint_report = munchify(data['contents'])
            self._sprint = munchify(data['sprint'])
            return True

        elif 'state' in data and 'name' in data:
            self._sprint = munchify(data)
            if self.option('include_reports'):
                if not self.option('board_id'):
                    self.logger.error("You cannot load reports within a JiraSprint object without a board ID given")
                    return False

                # do not return False if this fails.
                self._load_sprint_report()
            return True
        else:
            self.logger.error("JiraSprint: Could not prepopulate because the given data does not match expected values")
            return False

    @property
    def sprint_id(self):
        return self._sprint_id

    @sprint_id.setter
    def sprint_id(self, val):
        self._sprint_id = val

    @property
    def sprint(self):
        return self._sprint


class JiraSprintCollection(JiraObject):
    """
    Represents a collection of issues

    Options:
        - board (Optional) - This can either be a board ID or a JiraBoard object.
        - sprints (Optional) - The JIRA sprint objects as returned from the Jira REST API.
        - max_sprints (optional, default=None) - If given this is the maximum number of sprints to load keeping
                            in mind that they are loaded in reverse chronological order.
        - include_reports (optional, default=False) - If True, this will set make extra calls per
                            sprint to retrieve detailed sprint reports.
        - team_name - If given, this will restrict the sprints to those which have the given team name in the title.
        - states (optional, default="['closed','active']) - Which sprints to include based on state.  By default we
                            exclude future sprints.
    """

    def __init__(self, source, **kwargs):
        super(JiraSprintCollection, self).__init__(source, **kwargs)
        self._sprints = None
        if not self.option('states'):
            self._options.states = ['closed','active']

    def __iter__(self):
        return iter(self._sprints)

    def __str__(self):
        return "Sprint Collection:\n\t%s" % format("\n\t".join([str(s) for s in self._sprints]))

    @property
    def board_id(self):
        board = self.option('board')
        if board and isinstance(board, JiraBoard):
            return board.id
        elif board:
            return int(board)

        return None

    def _load(self):
        if not self.option('sprints') and not self.option('board'):
            self.logger.error("JiraSprintCollection: No sprint data source provided")
            return False

        if not self._sprints:

            if self.option('board'):
                board = self.option('board')
                if isinstance(board, JiraBoard):
                    board_id = board.id
                else:
                    board_id = board

                # we do it this way because this returns a paginated object that automatically
                #   makes additional calls when there are more than fit on a single page.
                sprints = self.source.jira.sprints(board_id, maxResults=0, state=','.join(self.option('state')))

            elif self.option('sprints'):
                sprints = self.option('sprints')
            else:
                # should never get here because initial check should validate
                #   required input.
                self.logger.error("You must provide a non empty set of sprints or a board to load a sprint collection")
                return False

            sprints.reverse()
            self._sprints = []
            for s in sprints:
                if self.option('max_sprints') and len(self._sprints) > int(self.option('max_sprints')):
                    # there's no need to look at any more sprints if we've
                    #   hit the maximum requested.
                    break

                if isinstance(s, Sprint):
                    jira_sprint_json = s.raw
                elif isinstance(s, dict):
                    jira_sprint_json = s
                else:
                    self.logger.error("Unrecognized sprint object found. Skipping...")
                    continue

                sprint_ob = JiraSprint(source=self.source, sprint_id=jira_sprint_json['id'],
                                       board_id=self.board_id,
                                       include_reports=self.option('include_reports'))

                continue_adding = True

                # filter on sprints with names that match the team (if given)
                if self.option('team_name'):
                    continue_adding = common.find_team_name_in_string(self.option('team_name'),
                                                                      jira_sprint_json['name'])

                if jira_sprint_json['state'].lower() not in self.option('states'):
                    continue_adding = False

                if continue_adding:
                    sprint_ob.prepopulate(jira_sprint_json)
                    self._sprints.append(sprint_ob)

            # order them from most recent to oldest by default.

        return self._sprints


class JiraBoard(JiraObject):
    """
    Provides access to a Jira Agile Board.
    Options:
        - team_id OR board_id OR both- If team ID given then board id will be taken from the database (if it exists). If
                                board ID is given but not team id then
        - max_sprints (optional, default=None) - If given this is the maximum number of sprints to load keeping
                            in mind that they are loaded in reverse chronological order.
        - restrict_sprints_with_team_name (optional, default=False) - If a team is given and if this is set to
                                True then only sprints that match the team name will be used.
        - include_sprint_reports (optional, default=False) - If this is specified loading the board will
                                take much longer as a separate call is made to retrieve the report
                                for each sprint.

    """

    def __init__(self, source, **kwargs):
        super(JiraBoard, self).__init__(source, **kwargs)
        self._team = None
        self._db_board = None
        self._jira_board = None
        self._sprints = None
        self._backlog_issues = None

    @property
    def id(self):
        if self._jira_board:
            return self._jira_board.id
        else:
            self.logger.error("JiraBoard: A board object has not yet been loaded")
            return None

    def get_backlog(self):
        """
        Returns a JiraIssueCollection of all the issues stored in the backlog.
        :return: Returns a JiraIssueCollection populated with backlog issues.
        """
        if not self._db_board:
            self.logger.error("JiraBoard: There is no board ID specified for this yet")
            return None

        if not self._backlog_issues:
            result = self.source.jira.get_backlog_issues(self._db_board.jira_id, json_result=True)
            if result:
                try:
                    self._backlog_issues = JiraIssueCollection(self.source, input_jira_issue_list=result['issues'])
                    self._backlog_issues.load()
                except InvalidData, e:
                    self.logger.warn("Unable to retrieve backlog.  %s" % e.message)
                    return None
            else:
                self._backlog_issues = None

        return self._backlog_issues

    def get_sprints(self):
        """
        Gets the sprints on the agile board in order from newest to oldest.  Note that this will not include
        future sprints.
        :return: Returns a JiraSprintCollection
        """
        if not self._sprints:

            if self.option('restrict_sprints_with_team_name'):
                team_name = self._team.name if self._team else ""
            else:
                team_name = None

            self._sprints = JiraSprintCollection(self.source, board=self,
                                                 include_reports=self.option('include_sprint_reports'),
                                                 max_sprints=self.option('max_sprints'),
                                                 team_name=team_name,
                                                 include_future=False)
            self._sprints.load()

        return self._sprints

    def get_most_recent_active_sprint(self):
        sprints = self.get_sprints()
        for s in sprints:
            if s.active:
                return s

        return None

    def get_most_recent_closed_sprint(self):
        sprints = self.get_sprints()
        for s in sprints:
            # the first inactive one it finds it returns since we assume that they are orded from newest to oldest
            #   (see get_sprints)
            if s.state.lower() == 'closed':
                return s

        return None

    def _load(self):
        if not self.option('board_id') and not self.option('team_id'):
            self.logger.error("Board ID or Team ID must be given")
            return None

        if self._load_db_data():
            return self._load_jira_data()

        return False

    def _load_db_data(self):
        team_id = self.option('team_id')
        if team_id:
            team = db.Team[team_id]
            if team:
                board = team.agile_board
            else:
                self.logger.error("Unable to find team with ID %d" % team_id)
                return False
        else:
            board_id = self.option('board_id')
            board = orm.select(b for b in db.AgileBoard if b.jira_id == board_id).first()
            if board:
                team = board.team
            else:
                self.logger.error("Unable to find board with ID %d" % board_id)
                return False

        self._team = team
        self._db_board = board

        return self._team is not None and self._db_board is not None

    def _load_jira_data(self):

        board_id = self.option('board_id')
        if not board_id:
            board_id = self._db_board.jira_id if self._db_board else None

        if board_id:
            b = self.source.jira.board(board_id)
            self._jira_board = munchify(b.raw)

            if not b:
                self.logger.error("Could not load the board information from Jira")
                return False
        else:
            self.logger.error("Could not get a board ID to load the board with")
            return False

        return True

    @property
    def board(self):
        return self._db_board

    @property
    def team(self):
        return self._team
