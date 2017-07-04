import logging

import augur.api

from augur.common import projects, audit
from augur.events.filters.jirawebhookfilter import JiraWebhookFilter
from augur.events.listener import WebhookListener
from augur.integrations.uajira import get_jira

EXCLUSIONS = ["team", "b2bdef", "ueb2b", "tsc"]

DESCRIPTION_TEMPLATE = \
    "{panel:title=Artifact}\n" + \
    "<artifactory_path_goes_here> (e.g. docker-artifacts.ua-ecm.com/ua-b2c:apps-master-fda423a-6afd3a802496)\n" + \
    "{panel}\n" + \
    "{panel:title=Special Instructions}\n" + \
    "_[Anything that needs to be done beyond the deployment of the docker container]_\n" + \
    "{panel}"

# make sure and transition the associated ticket when this is transitioned
CM_TO_TS_TRANSITION_MAP = {
    "staging pending": {
        "transition": {
            "production": {
                "transition_name": "Return to staging",
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            },
            "blocked": {
                "transition_name": "unblock staging",
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            },
            "quality review": {
                "transition_name": "begin staging deploy",
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            },
            "staging": {
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            }

        },
        "target_status": "staging"
    },
    "staging deployed": {
        "transition": {
            "production": {
                "transition_name": "Return to staging",
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            },
            "blocked": {
                "transition_name": "unblock staging",
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            },
            "quality review": {
                "transition_name": "begin staging deploy",
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            },
            "staging": {
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            }
        },
        "target_status": "staging"

    },
    "staging validated": {
        "transition": {
            "staging": {
                "transition_name": "deploy to production",
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            },
        },
        "target_status": "production"

    },
    "production deployed": {
        "transition": {
            "staging": {
                "transition_name": "deploy to production",
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            },
            "production": {
                "custom_fields": {
                    "Deployment Status": {"value": "Deployed"}
                }
            },
        },
        "target_status": "production"

    },
    "production validated": {
        "transition": {
            "production": {
                "transition_name": "resolve",
                "builtin_fields": {
                    "resolution": {"name": "Done"},
                },
                "custom_fields": {
                    "Deployment Status": {"value": "Validated"}
                }
            },
        },
        "target_status": "Resolved"
    },
    "abandoned": {
        "transition": {
            "production": {
                "transition_name": "Return to staging",
                "custom_fields": {
                    "Deployment Status": {"value": "Pending"}
                }
            }
        },
        "target_status": "staging"
    },
}


class JiraCmIssueTransitionHandler(WebhookListener):
    """
    Handles the sync of CM tickets with their work tickets.  This will create a CM ticket upon transition from
     Quality Review to Staging
    """

    def __init__(self):

        super(JiraCmIssueTransitionHandler, self).__init__(
            JiraWebhookFilter(
                actions=["issue:transitioned"],
                projects=projects.get_all_jira_projects(),
                fields=["status"]
            )
        )

    def execute(self, action, event):
        success = False

        try:

            if event['issue']['fields']['project']['key'].lower() == "cm":
                success = self._handle_cm_transition(action, event)
            else:
                success = self._handle_non_cm_transition(action, event)

        except Exception, e:
            self.logger.error("Problem during execution: %s"%e.message)
            success = False

        finally:
            return success

    def _handle_cm_transition(self, action, event):

        from_string = event['changelog']['current']['fromString'].lower() if event['changelog']['current'][
            'fromString'] else ""
        to_string = event['changelog']['current']['toString'].lower() if event['changelog']['current'][
            'toString'] else ""

        if to_string not in CM_TO_TS_TRANSITION_MAP:
            # if the transition map doesn't care about this status then we skip this altogether.
            return False

        j = get_jira()

        tickets = self._get_linked_tickets(event, "Change Management", linked_project_key=None, direction="out")
        issue_ob = None

        # for each linked ticket, check to see what new state it should be in based on the map above.
        for t in tickets:
            current_status = t['fields']['status']['name'].lower()
            transition_success = False

            # if the ticket is not already in the target status then we need to try and transition
            if current_status != CM_TO_TS_TRANSITION_MAP[to_string]['target_status']:

                # first, let's try transitioning the ticket.  Does the map have information
                #   about the new transition.  If not, we'll skip transitioning entirely
                if current_status in CM_TO_TS_TRANSITION_MAP[to_string]['transition']:

                    # We need information about the jira transition then we need information about the fields
                    #   that must be changed along with the transition as well as any addition field changes that
                    #   should happen after the trnasition has taken place.
                    transition_name = CM_TO_TS_TRANSITION_MAP[to_string]['transition'][current_status].get(
                        'transition_name', None)
                    builtin_fields = CM_TO_TS_TRANSITION_MAP[to_string]['transition'][current_status].get(
                        'builtin_fields', {})
                    transition_success = False
                    try:
                        if transition_name:
                            j.jira.transition_issue(
                                t['key'],
                                transition_name,
                                fields=builtin_fields)
                        elif builtin_fields:
                            # if there's no transition to execute - just an update of some fields then execute that.
                            issue_ob = j.jira.issue(t['key']) if not issue_ob else issue_ob
                            issue_ob.update(fields=builtin_fields)

                        transition_success = True
                    except Exception, e:
                        logging.error("Unable to transition issue due to error: %s" % e.message)

            else:
                # already transitioned so we'll say the transition was successful.
                transition_success = True

            update_success = False
            if transition_success:
                # the ticket is now in the right status but it might have additional fields that need to
                # be set after the transition has taken place.
                if current_status in CM_TO_TS_TRANSITION_MAP[to_string]['transition']:
                    fields = {}
                    custom_fields = CM_TO_TS_TRANSITION_MAP[to_string]['transition'][current_status].get(
                        'custom_fields', {})

                    if len(custom_fields):
                        for name, value in custom_fields.iteritems():
                            actual_name = augur.api.get_issue_field_from_custom_name(name)
                            fields[actual_name] = value

                        try:
                            issue_ob = j.jira.issue(t['key']) if not issue_ob else issue_ob
                            issue_ob.update(fields=fields)
                            update_success = True
                        except Exception, e:
                            logging.error(
                                "Unable to update issue with field changes after transition due to error: %s" %
                                e.message)
                            update_success = False
                    else:
                        # nothing to update but still say it was successful
                        update_success = True
                else:
                    #
                    update_success = True

            return transition_success or update_success

    def _handle_non_cm_transition(self, action, event):

        # make sure we are not processing excluded project transitions.
        if event['issue']['fields']['project']['key'].lower() in EXCLUSIONS:
            return False

        from_string = event['changelog']['current']['fromString']
        to_string = event['changelog']['current']['toString']

        if (from_string.lower() == "quality review") and (to_string.lower() == "staging"):
            # in the case where we're moving to Staging from Quality Review, create a CM ticket and link
            # it to this ticket
            j = get_jira()

            # check to see if there is already a link to a CM ticket
            linked_tickets = self._get_linked_tickets(event, 'change management', 'cm', 'in')

            if not linked_tickets:
                ticket = j.create_ticket(project_key='CM',
                                         summary='Release %s - %s' % (
                                            event["issue"]["key"], event["issue"]["fields"]["summary"]),
                                         description=DESCRIPTION_TEMPLATE,
                                         issuetype={'name': 'V7 Harbour Release'},
                                         reporter=event['user'],
                                         watchers=[event['user']['name']]
                                         )

                if ticket:
                    # now establish a link between the two.
                    j.link_issues("Change Management", ticket.key, event["issue"]["key"])

                return True
            else:
                # there is already a CM linked to this ticket
                return False

        else:
            # The transition is not what we are looking for so there nothing to do.  We interpret that as a failure.
            return False

    @staticmethod
    def _get_linked_tickets(event, link_type, linked_project_key=None, direction=None):
        """

        :param event: The event dict
        :param link_type: The type of link this is (e.g. "Change Management")
        :param linked_project_key: Filter on only tickets with the given project key (optional)
        :param direction: Filter on only links that are either "in" OR "out".  If none given then
                accept either.(optional)
        :return: Return an array of tickets that are linked given the parameters given.
        """
        linked = event["issue"]['fields']["issuelinks"] or []
        tickets = []
        for l in linked:
            if l['type']['name'].lower() == link_type.lower():
                # this is the type of link we're looking for.
                if direction:
                    direction_arr = ['inwardIssue'] if direction == "in" else ['outwardIssue']
                else:
                    direction_arr = ['inwardIssue', 'outwardIssue']

                for d in direction_arr:
                    if d in l:
                        if linked_project_key:
                            pk = l[d]['key'].split("-")[0].lower()
                            if pk != linked_project_key.lower():
                                continue

                        # a link between a CM and this ticket is already there so don't create one.
                        tickets.append(augur.api.get_issue_details(l[d]['key']))

        return tickets
