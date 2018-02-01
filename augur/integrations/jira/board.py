from munch import Munch

from augur import db, common
from pony import orm

from augur.integrations.jira.base import JiraObject
from augur.integrations.jira.issue import JiraIssueCollection


class InvalidId(Exception):
    pass


class InvalidData(Exception):
    pass


class JiraSprint(JiraObject):
    """
    JiraSprint objects can be loaded using a sprint ID for basic information or for more of a report on a sprint,
    it will require both the sprint ID and the board ID.

    Options:
        sprint_id - The ID of the sprint in Jira
        board_id (optional) - The agile board (rapid board) ID in Jira
    """

    def __init__(self, source, **kwargs):
        self._sprint_report = None
        self._sprint = None
        super(JiraSprint, self).__init__(source, **kwargs)

    def start_date(self):
        if not self._sprint:
            raise InvalidData("No sprint has been loaded yet.")

        if isinstance(self._sprint.start_date, (str,unicode)):
            # convert if necessary
            start_date = self._convert_date_string_to_date_time(self._sprint.start_date)
            if start_date:
                self._sprint.start_date = start_date
            else:
                return None

        return self._sprint.start_date

    def end_date(self):
        if not self._sprint:
            raise InvalidData("No sprint has been loaded yet.")

        if isinstance(self._sprint.end_date, (str,unicode)):
            # convert if necessary
            end_date = self._convert_date_string_to_date_time(self._sprint.end_date)
            if end_date:
                self._sprint.end_date = end_date
            else:
                return None

        return self._sprint.end_date

    def completed_date(self):
        if not self._sprint:
            raise InvalidData("No sprint has been loaded yet.")

        if isinstance(self._sprint.completed_date, (str,unicode)):
            # convert if necessary
            completed_date = self._convert_date_string_to_date_time(self._sprint.completed_date)
            if completed_date:
                self._sprint.completed_date = completed_date
            else:
                return None

        return self._sprint.end_date

    def name(self):
        if not self._sprint:
            raise InvalidData("No sprint has been loaded yet")

        return self._sprint.name

    def _load(self):

        if not self.option("sprint_id"):
            raise InvalidId("Sprint ID must be given")

        if self.option('include_report'):
            if self.option('board_id'):
                if not self._sprint_report:
                    self._load_sprint_report()
            else:
                raise InvalidId("To get a full sprint report you need to provide the board_id option")
        else:
            if not self._sprint:
                self._load_sprint()

    def _load_sprint_report(self):
        sprint_id = self.option("sprint_id")
        board_id = self.option("board_id")

        sprint_report = Munch(self.source.jira.sprint_report(board_id,sprint_id))

        if sprint_report:

            # only grab the contents area which contains the meatiest bits.
            self._sprint_report = sprint_report.contents

            # the sprint report is a superset of the sprint object.  The sprint key in the sprint report object
            #   contains the same keys plus a few more so we can reuse it for the sprint object so that both
            #   can be used without having to do a load twice.
            self._sprint = self._sprint_report.sprint

        else:
            raise InvalidId("JiraSprint: Unable to load sprint report data from Jira")

    def _load_sprint(self):

        sprint_id = self.option("sprint_id")
        s = self.source.jira.sprint(sprint_id)
        if s:
            self._sprint = Munch(s)
        else:
            self._sprint = None
            raise InvalidId

    def prepopulate(self,data):
        if 'contents' in data:
            self._sprint_report = data
        elif 'completeDate' in data and 'startDate' in data:
            self._sprint = data
        else:
            raise InvalidData("Could not prepopulate because the given data does not match expected values")

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
        - team_name - If given, this will restrict the sprints to those which have the given team name in the title.
    """
    def __init__(self, source, **kwargs):
        self._sprints = None
        super(JiraSprintCollection, self).__init__(source, **kwargs)

    def _load(self):
        if not self.option('sprints') and not self.option('board'):
            raise InvalidData("JiraSprintCollection: No sprint data source provided")

        if not self._sprints:

            if self.option('board'):
                board = self.option('board')
                if isinstance(board, JiraBoard):
                    board_id = board.id
                else:
                    board_id = board
                sprints = self.source.jira.sprints(board_id)

            elif self.option('sprints'):
                sprints = self.option('sprints')

            self._sprints = []
            for jira_sprint_json in sprints:
                sprint_ob = JiraSprint(sprint_id=jira_sprint_json['id'], board_id=self.option('board_id'))
                sprint_ob.prepopulate(jira_sprint_json)

                continue_adding = True

                # filter on sprints with names that match the team (if given)
                if self.option('team_name'):
                    continue_adding = common.find_team_name_in_string(self.option('team_name'), sprint_ob.name)

                if continue_adding:
                    self._sprints.append(sprint_ob)

            # order them from most recent to oldest by default.
            self._sprints.reverse()

        return self._sprints


class JiraBoard(JiraObject):
    """
    Provides access to a Jira Agile Board.
    Options:
        - team_id OR board_id OR both- If team ID given then board id will be taken from the database (if it exists). If
                                board ID is given but not team id then
        - restrict_sprints_with_team_name (optional, default=False) - If a team is given and if this is set to
                                True then only sprints that match the team name will be used.
    """
    def __init__(self, source, **kwargs):
        self._team = None
        self._db_board = None
        self._jira_board = None
        self._sprints = None
        self._backlog_issues = None
        super(JiraBoard, self).__init__(source, **kwargs)

    @property
    def id(self):
        if self._jira_board:
            return self._jira_board.id
        else:
            raise InvalidData("JiraBoard: A board object has not yet been loaded")

    def get_backlog(self):
        """
        Returns a JiraIssueCollection of all the issues stored in the backlog.
        :return: Returns a JiraIssueCollection populated with backlog issues.
        """
        if not self._db_board:
            raise InvalidId("JiraBoard: There is no board ID specified for this yet")

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
        Gets the sprints on the agile board in order from newest to oldest>
        :return: Returns a JiraSprintCollection
        """
        if not self._sprints:
            self._sprints = JiraSprintCollection(self.source, board=self)
            self._sprints.load()

        return self._sprints

    def get_most_recent_active_sprint(self):
        sprints = self.get_sprints()
        for s in sprints:
            if s.active():
                return s

        return None

    def get_most_recent_closed_sprint(self):
        sprints = self.get_sprints()
        for s in sprints:
            # the first inactive one it finds it returns since we assume that they are orded from newest to oldest
            #   (see get_sprints)
            if not s.active():
                return s

        return None

    def _load(self):
        if not self.option('board_id') and not self.option('team_id'):
            raise InvalidId("Board ID or Team ID must be given")

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
                raise InvalidId("Unable to find team with ID %d"%team_id)
        else:
            board_id = self.option('board_id')
            board = orm.select(b for b in db.AgileBoard if b.jira_id == board_id).first()
            if board:
                team = board.team
            else:
                raise InvalidId("Unable to find board with ID %d"%board_id)

        self._team = team
        self._db_board = board

        return self._team is not None and self._db_board is not None

    def _load_jira_data(self):

        b = self.source.jira.board(self.option('board_id'))
        self._jira_board = Munch(b)

        if not b:
            raise InvalidId("Could not load the board information from Jira")


    @property
    def board(self):
        return self._db_board

    @property
    def team(self):
        return self._team
