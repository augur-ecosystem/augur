# Augur Developer Metrics

Help team leads, managers and developers track progress, improvement, 
gaps by combing data from multiple tools into an easy to use dashboard
using the Augur Development Method.

This is a library that can be easily included into any client that wants to
collect data using ADM.  

# Augur Installation

Augur is hosted in the UA Artifactory PyPI index because it contains some UA-specific
 information (currently).  Access to only the pypi index on the artifactory host is given
 to the following artifactory user: `pypi-reader`

To install, you can do one of the following:

## Install on command line

    pip install augur -i https://pypi-reader:ThOgrAVultiA@artifacts.ua-ecm.com/artifactory/api/pypi/ua-pypi/simple

Without changing your global index, this will install augur using the custom index this once.

## Install in requirements.txt

Modify you requirements.txt file by including this at the top of the file:

    --extra-index-url https://pypi-reader:ThOgrAVultiA@artifacts.ua-ecm.com/artifactory/api/pypi/ua-pypi/simple

Then include augur as you would any other package:

    augur==<version>
    or
    augur

# Augur Development

To upload a new version of augur, you can modify your .pypirc file with the following:

    [dist-utils]
    .... # whatever indexes you already had in there
    local

    ...

    [local]
    repository: https://artifacts.ua-ecm.com/artifactory/api/pypi/ua-pypi
    username: <username> # must have publish rights
    password: <password>


Then build and upload the new version from within the augur root directory:

    python setup.py sdist upload -r local


# Augur Integration

## Settings

In order to use Augur there are some settings that it expects to be accessible
via environment variables.  In some cases, there are defaults that are applied,
in other cases, the initialization will fail if not specified.


| Environment Variable |  Purpose                                 |   Default   | Example                        |
| -------------------- |:-----------------------------------------|:----------: |--------------------------------|
| JIRA_INSTANCE        | The full url to the JIRA instance to use | Required    | http://voltron.atlassian.net/   |
| JIRA_USERNAME        | The full url to the JIRA instance to use | Required    | A username   |
| JIRA_PASSWORD        | The full url to the JIRA instance to use | Required    | It's a password   |
| JIRA_API_PATH        | The relative path to the root of the rest endpoints | rest/api/2 | rest/api/2  |
| CONFLUENCE_INSTANCE  | The full url to the Confluence instance  | JIRA_INSTANCE    | http://voltron.atlassian.net/wiki   |
| CONFLUENCE_USERNAME  | The full url to the Confluence instance  | JIRA_USERNAME    | A username   |
| CONFLUENCE_PASSWORD  | The full url to the Confluence instance  | JIRA_PASSWORD    | Another password   |
| GITHUB_BASE_URL  | The full url to the Github instance  | Required    | http://github.com/ |
| GITHUB_LOGIN_TOKEN  | The token of the user that should be used to access the API for the instance of github specificed in GITHUB_BASE_URL | Required    | cbab75c171843afef555d9dcbc212e0b54681b32 |
| GITHUB_CLIENT_ID | The client ID that has been registered for the client that is using this instance of the Augur library | Required    | e3d808650b4f45f9ac03 |
| GITHUB_CLIENT_SECRET | The client secret that has been registered for the client that is using this instance of the Augur library | Required    | f3d80e650b4d45f9ad15 |


# Integration with External Tools

## Github

There is no explicit requirements for Github setup other than this: Augur was developed from the enterprise edition 
 which means it's more acceptable for Github Organizations to be part of the hierarchy of the codebase.
 
     Note:
     Augur uses PyGithub for interacting with the github server.  Unfortunately, at the time of this writing,
     the library did not support a search endpoint needed for hash searches.  So the code
     to do that was added to the library and a PR created:
     https://github.com/PyGithub/PyGithub/pull/648
     
     While waiting for that PR to be merged and a new release cut, a custom PyGithub build 1.36
     was created and pushed to the UA artifact repo.  

## Jira 

### Groups, Workflows and Teams
Augur now supports creation of custom workflows.  To do this, a taxonomy of 
was created to organize them.  

* Groups
    * Workflow
        * Projects
    * Teams
        * Staff
* Vendors

#### Groups
A group in Augur is a group of people within an organization that share a common 
workflow.  For example, developers might use a workflow that is different than 
that used by the marketing team.  Groups are described by a single workflow and 
a set of teams. 

#### Workflows
While Augur workflows are closely tied to Jira workflows there's not a 1:1 comparison. 

A workflow is made up of:
* Statuses - The various statuses that this workflow includes
* Resolutions - fixed, completed, etc.
* Projects - the Jira projects that are considered part of the workflow
* Project Categories - A jira project category that should be included in this project
* Issue Types - The types of issues that should be considered identified selected when making queries
* Defect Projects - Which projects within the list of projects above are used for storing defects


##### Statuses
Within a workflow, statuses can be of three types (open, in progress, resolved).  This helps 
us understand what tickets are actively being worked on for metrics purposes.


##### Resolutions
When a ticket status is set to a resolved state, we look at the resolution types to understand
the success or failure of that issue.  So each resolution type supported has a type
as well: postive or negative.  So a positived resolution would be "fixed" and a negative one 
would be "won't fix"


##### Projects
We can indicate which projects to include by either specifying the project keys individually
or using JIRA's project categories which is a more easy to manage because you simply have
to set the category of a project in JIRA and it will automatically be included in this workflow.

##### Issue Types
We can also indicate which issue types we should pay attention to.  This is helpful when 
projects have issue types that are used for tracking information that has nothing
to do with the workflow - like individual todo items, etc.

##### Defect Projewcts
Finally, defect projects are projects that we specifically call out for consisting
entirely of bugs found in production.  We can use this information to collect defect
metrics over time.  A defect project is not necessarily just all tickets in the project
but can also be further filtered by the issue type.

#### Teams
Teams are made up of staff who have a long list of attributes associated with each.  
We keep information about the staff such as who they work for, email, usernames
for different tools, etc.

##### Sprints
Sprints are not stored in the augur db explicitly but the agile board ID is used
to retrieve sprint information.  To ensure that the correct sprints are being read, 
sprint names must follow a certain format: 

    <sprint_num> - Team <team_name>
    
    Example:
    001 - Team Voltron
    
This is to ensure that only sprints that are associated with the team are
included in the metrics.  Due to the way Jira works, it is possible for a 
sprint that is part of a different agile board to be included in the metrics
if this formatting restriction is not used.

