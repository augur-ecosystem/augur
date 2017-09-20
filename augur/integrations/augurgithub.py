import datetime
import exceptions
import json
import logging
import re

import github
import yaml
from github import Github, GithubException
from github.GithubObject import GithubObject

from augur import settings
from augur.common import cache_store
from augur.common.timer import Timer
from augur.api import get_jira
import augur.api

LOGIN_TOKEN = "1a764970a4a22d220bf416cbd5266d497f3d55a0"
DEFAULT_LOOKBACK_DAYS = 90

# These are the github orgs that we will monitor for prs/commits
GITHUB_ORGS = ['ua', 'v6', 'harbour', 'b2b', 'ui', 'lib', 'apps']


class GitFileNotFoundError(exceptions.Exception):
    """Used for reporting a problem when scanning a repo for a file"""
    pass


class AugurGithub(object):
    def __init__(self):
        self.github = Github(login_or_token=settings.main.integrations.github.login_token,
                             password="x-oauth-basic",
                             base_url=settings.main.integrations.github.base_url,
                             per_page=200)

        self.mongo = cache_store.AugurStatsDb()
        self.prs_data_store = cache_store.AugurTeamPullRequestsData(self.mongo)
        self.open_prs_data_store = cache_store.AugurTeamOpenPullRequestsData(
            self.mongo)
        self.permissions_data_store = cache_store.AugurPermissionsOrgData(
            self.mongo)
        self.jira = get_jira()
        self.logger = logging.getLogger("augurgithub")

    def fetch_further_reviews(self, org):
        """
        Gets all the further review information for each repo in the given org
        :param org: The name of the org to return further review info from
        :return: Returns a dictionary containing further review information
        """
        repos = self.get_repos_in_org(org)
        org_further_reviews = {}
        for r in repos:
            org_further_reviews[r.name] = self.get_repo_further_review(r)

        return org_further_reviews

    def _prepare_pr_search(self, orgs, state, since, sort, order):
        """
        Prepare the basic query for a PR search including state, beginning date, orgs/repos
        It returns a string containing the full query and caller can add to it to filter further
        :param order: The sort order can be asc or desc
        :param sort: The sort order.  Can be comments, created, or updated
        :param state: The state of the pr (open, closed, merged)
        :param org: The name of the organization (as a string)
        :param since: The earliest date when the PRs were first opened
        :return: Returns a query string (just the q parameter's value
        """
        # Convert to list if it's not already
        query = " type:pr"

        if orgs:
            orgs = orgs if isinstance(orgs, list) else [orgs]

            local_repo_obs = []
            for o in orgs:
                cached_repos = augur.api.get_cached_data("repos_for_%s" % o)
                if not cached_repos:
                    repos = [r.raw_data for r in self.get_repos_in_org(o)]
                    augur.api.cache_data({'data':repos}, "repos_for_%s" % o)
                else:
                    repos = cached_repos[0]['data']

                local_repo_obs += repos

            # build a list of all the repos to search (no way to filter by org apparently)
            query += " " + " ".join(["repo:%s/%s" % (r['organization']['login'], r['name']) for r in local_repo_obs])

        if state in ("open", "closed"):
            query += " is:%s" % state

        if since:
            if state == 'merged':
                query += ' merged:>%s' % since.date().isoformat()
            else:
                query += ' created:>%s' % since.date().isoformat()

        return query

    def fetch_user_data(self, user, lookback_days=60):
        """
        Get github status for a single user.  This will retrieve the most recent data if not already
        stored in the database.  So at this point, this call could take 20 minutes to complete
        :param user: The name of the user
        :param lookback_days: The number of days to look back in time for PRs and other data
        :return: Returns a dict with github stats info in it
        """
        dev_stats_ob = cache_store.AugurGithubDevStats(user)
        since = datetime.datetime.now() - datetime.timedelta(days=int(lookback_days))
        merged_prs = self.fetch_author_merged_prs(user,since)
        for pr in merged_prs:
            dev_stats_ob.add_pr(pr)

        return dev_stats_ob.as_dict()

    def fetch_prs(self, org, state, since=None, sort="created", order="desc"):
        """
        Gets the PRs for the given repo(s) of the given type.  You can specify PRs of certain types
        :param order: The sort order can be asc or desc
        :param sort: The sort order.  Can be comments, created, or updated
        :param state: The state of the pr (open, closed, merged)
        :param org: The name of the organization (as a string)
        :param since: The earliest date when the PRs were first opened
        :return: Returns a list of search results
        """

        try:
            query = self._prepare_pr_search(orgs=org, state=state, since=since, sort=sort, order=order)
            results = self.github.search_issues(query=query, sort=sort, order=order)
            return [r.raw_data for r in results]

        except GithubException as e:
            self.logger.error(
                "Error while retrieving %s PRs since %s from %s: %s" % (state, str(since), org, e.message))

        return []

    def fetch_prs_to_review(self, username=None, orgs=None, sort="created", order="desc"):
        """
        Searches for all PRs that the given user is responsible for reviewing or has already
        started reviewing and the PR is still open.
        :param username: The github username or None if all PRs to review should be searched.
        :param sort: Can be one of comments,created or updated
        :param order: Can be one of asc or desc
        :return:
        """
        if not username and not orgs:
            raise exceptions.ValueError("you must specific a username or orgs to restrict "
                                        "this to - result set will be too large without those constraints")

        query = self._prepare_pr_search(orgs=orgs, state="open", since=None, sort=sort, order=order)

        if username:
            query += " review-requested:%s" % username

        results = self.github.search_issues(query=query, sort=sort, order=order)
        return [r.raw_data for r in results]

    def fetch_author_merged_prs(self, username, since, sort="created", order="desc"):
        """
        This will retrieve one or more authors prs in the given state
        :param username: A string or list of usernames
        :param state: Can be one of open, closed, merged
        :param sort: The sort order can be one of comments, created or updated
        :param order: Can be one of asc or desc
        :return: Returns a list of search results as a list of dictionaries
        """
        query = self._prepare_pr_search(orgs=None, state="merged", since=since, sort=sort, order=order)
        query += " author:%s" % username
        results = self.github.search_issues(query=query, sort=sort, order=order)
        return [r.raw_data for r in results]

    def fetch_author_open_prs(self, username, sort="created", order="desc"):
        """
        This will retrieve one or more authors prs in the given state
        :param username: A string or list of usernames
        :param state: Can be one of open, closed, merged
        :param sort: The sort order can be one of comments, created or updated
        :param order: Can be one of asc or desc
        :return: Returns a list of search results as a list of dictionaries
        """
        query = self._prepare_pr_search(orgs=None, state="open", since=None, sort=sort, order=order)
        query += " author:%s" % username
        results = self.github.search_issues(query=query, sort=sort, order=order)
        return [r.raw_data for r in results]

    def fetch_organization_members(self, organization):
        """
        Gets a list of all organization members as a lits of dictionaries
        :param organization: The name of the organization
        :return: Returns a list of organization Member objects
        """
        org_ob = self.get_organization(organization)
        return [m.raw_data for m in org_ob.get_members()] if org_ob else []

    def get_organization(self, org):
        """
        Takes an organization name and returns an organization object
        :param org: The organization's name
        :return: The Organization object or None
        """
        try:
            # first we try getting a real organization
            org_ob = self.github.get_organization(org)
        except github.UnknownObjectException:
            # try a user org if there is not actual org
            org_ob = self.github.get_user(org)

        return org_ob

    def get_repos_in_org(self, org):
        """
        Gets a list of all the repositories in the form of Repository objects
        from the given organization name.
        :param org: The name of an organization
        :return: Returns a list of Repository objects
        """
        org_ob = self.get_organization(org)
        return [r for r in org_ob.get_repos()] if org_ob else []

    def get_repo_commit_stats(self, repo, org=None):
        """
        Gets commits information for the last 90 days.  This includes things like:
            * A flat list of commits
            * the commit object and counts organized by author
            * total commits
            * total comments
            * average comments per commit
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns a dictionary containing commit information
        """
        org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)

        since = datetime.datetime.now() - datetime.timedelta(days=90)
        commits = repo_ob.get_commits(since=since)
        by_author = dict()
        avg_comments = 0
        total_comments = 0

        commit_objects = []
        try:
            for c in commits:
                try:
                    if c.author.login not in by_author:
                        by_author[c.author.login] = {
                            "count": 0,
                            "commits": []
                        }
                    by_author[c.author.login]['count'] += 1
                    by_author[c.author.login]['commits'].append(c.raw_data)

                    comments = c.get_comments()
                    comment_objects = []
                    for cmt in comments:
                        comment_objects.append(cmt.raw_data)

                    total_comments += len(comment_objects)
                    commit_objects.append(c.raw_data)
                except Exception, e:
                    self.logger.error(
                        "Encountered error when reviewing commits for repo %s: %s" % (repo_ob.name, e.message))
                    continue
        except github.GithubException, e:
            self.logger.error("Encountered an error while iterating over commits: %s" % e.message)

        total_commits = len(commit_objects)

        if total_commits:
            avg_comments = float(total_comments) / float(total_commits)

        return {
            "commits": commit_objects,
            "by_author": by_author,
            "total_commits": total_commits,
            "total_comments": total_comments,
            "avg_comments_per_commit": avg_comments
        }

    def get_org_and_repo_from_params(self, repo, org=None):
        """
        Tries to get the org and repo objects based on the given params.  If the repo is an object
        then it will just return that and the org object contained within.  If the repo param
        is a string then the org param must be non-null so that the specific repo can be found.
        In that case, the org can either be an Organization object or a string.
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns two results: Repository object, Organization object.
        """
        if not org and not isinstance(repo, GithubObject):
            raise TypeError(
                "If repo given is not a github object then organization must be specified")

        repo_ob = None
        org_ob = None

        if repo and isinstance(repo, GithubObject):
            repo_ob = repo

        if org and isinstance(repo, GithubObject):
            raise TypeError(
                "If org is given then repo should be a string otherwise there's no reason to pass the org")

        if org and isinstance(org, str):
            org_ob = self.github.get_organization(org)

        elif org and isinstance(org, GithubObject):
            org_ob = org

        elif org:
            raise TypeError("Org must be a github object or a string")

        if not repo_ob:
            repo_ob = org_ob.get_repo(repo)

        if not org_ob and repo_ob:
            org_ob = repo_ob.organization

        return org_ob, repo_ob

    def get_org_component_data(self, org):
        """
        Gets all repos in an org and retrieves information about each that comes from github along with additional
        info including further review data, additional aggregate data and the readme summary.  Note that this
        will use cached data if available.

        :param org: The organization object or name
        :return: Returns a dict containing the data.
        """
        ds = cache_store.AugurComponentOwnership(self.mongo)
        data = ds.load_org(org,context=None)
        if not data:
            repos = self.get_repos_in_org(org) or []
            data = {
                'org': None,
                'repos': []
            }

            for repo in repos:

                further_review = self.get_repo_further_review(repo)
                readme_summary_list = self.get_repo_readme_summary(repo)

                repo.raw_data["further_review"] = further_review or {}
                repo.raw_data['readme_summary'] = readme_summary_list[0] if len(readme_summary_list) else ""
                repo.raw_data["ua_stats"] = self.get_repo_commit_stats(repo)

                data['repos'].append(repo.raw_data)
                if not data['org']:
                    data['org'] = repo.owner.login

            # cache in case anything else wants to use this info
            ds.save(data)

        return data

    def get_repo_readme_summary(self, repo, org=None):
        """
        Finds the text between the h1 and h2 in the readme file for a repo and returns it in the form of an array
        of strings (one for each line)
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns a list of strings.
        """
        org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)
        result = []
        try:
            content_ob = repo_ob.get_file_contents("README.md")
            if content_ob:
                readme_str = content_ob.decoded_content
                if readme_str:
                    try:
                        result = re.findall('#.*\n([^#]*)', readme_str, re.MULTILINE)
                        return result
                    except Exception as e:
                        self.logger.info("Parse error during processing of README.md: %s" % e.message)
                else:
                    self.logger.warning("Unable to retrieve README.md")
            else:
                self.logger.warning("Unable to find README.md file")
        except github.UnknownObjectException, e:
            self.logger.error("Error occurred during README analysis: %s (%s)" % (e.message, str(e.__class__)))
        except github.GithubException, e:
            self.logger.error("Error occurred during further review analysis: %s (%s)" % (e.message, str(e.__class__)))
        return result

    def get_repo_further_review(self, repo, org=None):
        """
        Gets the further review information from the given repo
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns a dictionary containing information about the maintainers and owners
        """
        fr = augur.api.get_memory_cached_data('FR_OPR_' + repo.full_name)
        if fr: return fr

        def parse_user(user_str):
            name_match = re.match(r"^([^\(<]+)", user_str)
            email_match = re.match(r".*<(.*)>.*", user_str)
            user_match = re.match(r".*\(@(.*)\).*", user_str)

            return {
                'name': name_match.group(1) if name_match else "",
                'email': email_match.group(1) if email_match else "",
                'username': user_match.group(1) if user_match else "",
            }

        org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)

        result = {
            "owner": None,
            "maintainers": [],
        }

        try:
            content_ob = repo_ob.get_file_contents(".further-review.yaml")
            if content_ob:
                yaml_str = content_ob.decoded_content
                if yaml_str:
                    try:
                        further_review = yaml.load(yaml_str)
                        if 'reviews' not in further_review or not isinstance(further_review['reviews'], list):
                            self.logger.warning("Unable to find reviews section in further-review file")
                        else:
                            for index, review in enumerate(further_review['reviews']):
                                if review['name'].lower() == 'general maintainers':
                                    reviewers = review['logins'] if review['logins'] else [
                                    ]
                                    for r in reviewers:
                                        user_ob = parse_user(r)
                                        result['maintainers'].append(user_ob)
                            if 'owner' in further_review and further_review['owner']:
                                result['owner'] = parse_user(
                                    further_review['owner'])

                    except yaml.YAMLError, e:
                        self.logger.info("YAML error during processing of .further-review.yaml: %s" % e.message)
                else:
                    self.logger.warning("Unable to retrieve .further-review.yaml")
            else:
                self.logger.warning("Unable to find further-review.yaml file")
        except github.UnknownObjectException, e:
            self.logger.error(
                "Got a github error indicating that we were unable to find a file in the repo: %s (%s)" % (
                    e.message, str(e.__class__)))
        except github.GithubException, e:
            self.logger.error("Error occurred during further review analysis: %s (%s)" % (e.message, str(e.__class__)))

        augur.api.memory_cache_data(result, 'FR_OPR_' + repo.full_name)

        return result

    def get_repo_package_json(self, repo, org=None):
        """
        Gets the package.json JSON from a given repo
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns a dictionary object containing all of the package.json contents
        """
        org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)

        try:
            content_ob = repo_ob.get_file_contents("package.json")
            if content_ob:
                json_str = content_ob.decoded_content
                if json_str:
                    try:
                        package_ob = json.loads(json_str)
                        if 'maintainers' in package_ob and isinstance(package_ob['maintainers'], list):
                            for index, maintain in enumerate(package_ob['maintainers']):
                                if isinstance(maintain, (str, unicode)):
                                    parts = re.match(
                                        r"(?:(.*))\s(?:<?(.+@[^>]+)>?)?", maintain)
                                    groups = parts.groups()
                                    package_ob['maintainers'][index] = {
                                        'name': groups[0] if len(groups) > 0 else "",
                                        'email': groups[1] if len(groups) > 1 else ""
                                    }
                        if 'owner' in package_ob:
                            owner = package_ob['owner']
                            if isinstance(owner, (str, unicode)):
                                parts = re.match(
                                    r"(?:(.*))\s(?:<?(.+@[^>]+)>?)?", owner)
                                groups = parts.groups()
                                package_ob['owner'] = {
                                    'name': groups[0] if len(groups) > 0 else "",
                                    'email': groups[1] if len(groups) > 1 else ""
                                }
                        return package_ob

                    except ValueError, e:
                        raise GitFileNotFoundError(
                            "Package found but had invalid JSON in it %s: %s" % (repo.name, e.message))
                else:
                    raise GitFileNotFoundError(
                        "Found package file but nothing in it for repo %s" % repo.name)
            else:
                raise GitFileNotFoundError(
                    "Cannot find package file in %s" % repo.name)
        except github.UnknownObjectException, e:
            raise GitFileNotFoundError(
                "Cannot find package file in %s: %s" % (repo.name, e.message))


if __name__ == "__main__":
    gh = AugurGithub()
    gh.refresh_open_pr_cache()
