import settings

DISTRIBUTION_LISTS = dict()

DISTRIBUTION_LISTS["DEV_ONLY"] = [
        "kshehadeh@underarmour.com",
        "kshehadeh@ua.com",
    ]

if settings.main.project.debug:
    DISTRIBUTION_LISTS["ENG_REPORT"] = DISTRIBUTION_LISTS['DEV_ONLY']
else:
    DISTRIBUTION_LISTS["ENG_REPORT"] = [
            "kshehadeh@underarmour.com",
            "bfinnigan@underarmour.com",
            "kchung3@underarmour.com",
            "rwilson1@underarmour.com",
            "lwilson1@underarmour.com",
            "mfruhling@underarmour.com",
            "kvalencik@underarmour.com",
            "ptyng@underarmour.com",
            "jz@underarmour.com",
            "swalker1@underarmour.com",
            "ecomm-pdm@underarmour.com"
        ]

if settings.main.project.debug:
    DISTRIBUTION_LISTS["RELEASE_REPORT"] = DISTRIBUTION_LISTS['DEV_ONLY']
else:
    DISTRIBUTION_LISTS["RELEASE_REPORT"] = [
        "ecomm-engineering@underarmour.com",
        "ecomm-pdm@underarmour.com",
    ]


DISTRIBUTION_LISTS["ALDERSON_LOOP_TIMESHEET"] = [
        "lauren.asghari@aldersonloop.com",
        "kshehadeh@ua.com",
]

DISTRIBUTION_LISTS["CATALYST_TIMESHEET"] = [
    "tolonisakin@catalystdevworks.com",
    "jfreeman@catalystdevworks.com",
    "kshehadeh@ua.com",
]

DISTRIBUTION_LISTS["TWIN_TIMESHEET"] = [
    "pat.norton@twintechs.com",
    "kshehadeh@ua.com",
]

DISTRIBUTION_LISTS["TEK_TIMESHEET"] = [
    "dducharme@underarmour.com",
    "kshehadeh@ua.com",
]
