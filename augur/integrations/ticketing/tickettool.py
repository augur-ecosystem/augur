
import logging


class TeamSprintNotFoundException(Exception):
    pass


class DeveloperNotFoundException(Exception):
    pass


class TicketTool(object):

    def __init__(self, server=None, username=None, password=None):
        self.logger = logging.getLogger("tickettool")

    def search(self, query, expand=None, max_results=500):
        pass

    def worklogs(self, start, end, team_id, username, project_key=None):
        pass

    def link_tickets(self, link_type, inward, outward, comment=None):
        pass

    def create_ticket(self, project_key, summary, description, issuetype, reporter, **kwargs):
        pass

    def get_sprints(self, team):
        pass
