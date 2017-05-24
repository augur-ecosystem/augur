MAX_HISTORY = 2

COLOR_GOOD = '#e4f9d6'
COLOR_OK = '#fff4cc'
COLOR_BAD = '#ffd6d6'
COLOR_QUESTIONABLE = '#e5c6f4'

STATUS_INPROGRESS = "In Progress"
STATUS_OPEN = "Open"
STATUS_QUALITYREVIEW = "Quality Review"
STATUS_INTEGRATION = "Integration"
STATUS_STAGING = "Staging"
STATUS_PRODUCTION = "Production"
STATUS_RESOLVED = "Resolved"

PROJECTS = [
    "ENG",
    "TOP",
    "POST",
    "PDC",
    "DEF",
    "ARMBOX",
    "ICON",
    "EFMS",
    "CNR",
    "TEAM",
    "B2BDEF"
]

JIRA_TEAMS_BY_SHORT_NAME = {
    "rc": "Team Sagamore",
    "b": "Team Charm",
    "cm": "Team Constellation",
    "sg": "Team McCormick",
    "vd": "Team Camden",
    "by": "Team Bayside",
    "lc": "Team Hon",
    "bh": "Team Boh",
    "at": "Team ATX",
    "mc": "Team McHenry",
    "p": "Team Poe"
}

CONSULTING_TEAM_IDS = {
    "catalyst": 25,
    "twin": 12,
    "tek": 22,
    "all": 27
}

JIRA_TEAMS_RAPID_BOARD = {
    "rc": 426,
    "b": 422,
    "cm": 444,
    "sg": 640,
    "vd": 661,
    "by": 700,
    "lc": 543,
    "mc": 789,
    "bh": 741,
    "at": 819,
    "p": 832
}

FUNNELS = {
    'top': {
        "title": "Top of Funnel",
        "pdm": "Mary Lawyer",
        "teams": ['by', 'lc']
    },
    'bottom': {
        "title": "Bottom of Funnel",
        "pdm": "Brendan Kelleher",
        "teams": ['rc', 'vd', 'sg', 'cm', 'mc']
    },
    'b2b': {
        "title": "B2B",
        "pdm": "Dave Hartzell",
        "teams": ['b','p']
    },
    'plat': {
        "title": "Platform",
        "pdm": "Ken Valencik",
        "teams": ['bh']
    },
    'apps': {
        "title": "Apps",
        "pdm": "Jeremy Zedell",
        "teams": ['at']
    }
}

JIRA_TEAM_BY_FULL_NAME = dict(zip(JIRA_TEAMS_BY_SHORT_NAME.values(), JIRA_TEAMS_BY_SHORT_NAME.keys()))

JIRA_TEAM_EXCLUSIONS = ["Team Leads", "Team Sherlock", "Team Opstimus Prime", "Team Negasonic"]

SPRINT_BEFORE_LAST_COMPLETED = "__BEFORELAST__"
SPRINT_LAST_COMPLETED = "__LAST__"
SPRINT_CURRENT = "__CURRENT__"
