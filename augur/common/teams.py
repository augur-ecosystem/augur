import const

def team_to_funnel_map():
    FUNNELS_BY_TEAM = {}
    for funnel,info in const.FUNNELS.iteritems():
        for t in info['teams']:
            FUNNELS_BY_TEAM[t] = funnel

    return FUNNELS_BY_TEAM


def get_all_teams():
    """
    Gets all teams' data
    :return: A a dict of teams
    """
    return {short_name:get_team_from_short_name(short_name) for short_name in const.JIRA_TEAMS_BY_SHORT_NAME}


def get_team_from_short_name(short_name):
    """
    Returns simplified team data from a short name
    :param short_name: A small version of the team's info
    :return: Returns a dict
    """
    if short_name in const.JIRA_TEAMS_BY_SHORT_NAME:
        return {
            "team_name": const.JIRA_TEAMS_BY_SHORT_NAME[short_name],
            "short_name": short_name,
            "board_id": const.JIRA_TEAMS_RAPID_BOARD[short_name],
        }
    else:
        return None


def get_teams_in_group(group_name):
    return {}
