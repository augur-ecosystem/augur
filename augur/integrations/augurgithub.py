import datetime
import exceptions
import json
import logging
import re

import dateutil
import github
import pytz
import yaml
from github import Github
from github.GithubObject import GithubObject

from augur import settings
from augur.api import get_jira
import augur.api

DEFAULT_LOOKBACK_DAYS = 90


class GitFileNotFoundError(exceptions.Exception):
    """Used for reporting a problem when scanning a repo for a file"""
    pass


class AugurGithubDevStats(object):
    def __init__(self, username):
        self.user = username
        self.prs = []
        self.avg_changed_files_per_pr = 0
        self.avg_comments_per_pr = 0
        self.highest_changes_in_pr = 0
        self.highest_comments_in_pr = 0
        self.avg_length_of_time_pr_was_open = datetime.timedelta()
        self.dirty = False

    def reset(self):
        self.__init__(self.user)

    def add_pr(self, pr):

        if pr['user']['login'] == self.user:
            self.dirty = True

            # we need a version of this attribute that doesn't have the underscore so that we can
            #   display its values in a django template.
            pr['links'] = pr['pull_request']
            self.prs.append(pr)

            comment_count = pr['comments']
            self.avg_comments_per_pr += comment_count
            if comment_count > self.highest_comments_in_pr:
                self.highest_comments_in_pr = comment_count

            closed_at = pr['closed_at']
            created_at = pr['created_at']

            if not isinstance(pr['closed_at'], datetime.datetime):
                closed_at = dateutil.parser.parse(pr['closed_at'])
            closed_at = closed_at.replace(tzinfo=None)

            if not isinstance(pr['created_at'], datetime.datetime):
                created_at = dateutil.parser.parse(
                    pr['created_at']).replace(tzinfo=pytz.UTC)
            created_at = created_at.replace(tzinfo=None)

            if pr['state'] in ['merged', 'closed']:
                self.avg_length_of_time_pr_was_open += (closed_at - created_at)

    def as_dict(self):

        if self.dirty:
            self.avg_changed_files_per_pr /= len(self.prs)
            self.avg_comments_per_pr /= len(self.prs)

            avg_secs = self.avg_length_of_time_pr_was_open.total_seconds() / len(self.prs)
            self.avg_length_of_time_pr_was_open = datetime.timedelta(
                seconds=avg_secs)
            self.dirty = False

        return {
            'prs': self.prs,
            'avg_changed_files_per_pr': self.avg_changed_files_per_pr,
            'avg_comments_per_pr': self.avg_comments_per_pr,
            'highest_changes_in_pr': self.highest_changes_in_pr,
            'highest_comments_in_pr': self.highest_comments_in_pr,
            'avg_length_of_time_pr_was_open': self.avg_length_of_time_pr_was_open,
        }


class AugurGithub(object):
    def __init__(self):
        self.github = Github(login_or_token=settings.main.integrations.github.login_token,
                             password="x-oauth-basic",
                             base_url=settings.main.integrations.github.base_url,
                             per_page=200)

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

    def get_commit_info(self, commit_hash, org_repo=None):
        """
        Gets details about a single commit based on the given commit hash.  If there is more than one returned
        from github, the first is returned from this function
        :param commit_hash: The sha1 hash of the commit (shortened or full length)
        :param org_repo: The name of the org/repo combo (<org>/<repo>) to search. When you specify the repo, it
                            gives you better results.
        :return: Return github.Commit.Commit
        """

        if not org_repo:
            commits = self.github.search_commits(query="hash:%s" % commit_hash)
            if commits.totalCount > 0:
                return commits[0]
            else:
                logging.warning(
                    "Unable to find the following commit: %s" % commit_hash)
                return None
        else:
            try:
                org, repo = org_repo.split("/")
            except ValueError:
                logging.error(
                    "Got an invalid org_repo parameter in get_commit_info")
                return None

            org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)
            if repo_ob:
                commit = repo_ob.get_commit(commit_hash)
                if not commit:
                    logging.warning(
                        "Unable to find the following commit (with repo): %s" % commit_hash)
                    return None
                else:
                    return commit
            else:
                logging.error(
                    "Unable to find the given repo (%s) or org (%s)" % (repo, org))
                return None

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
                cached_repos = augur.api.get_memory_cached_data(
                    "repos_for_%s" % o)
                if not cached_repos:
                    repos = [r.raw_data for r in self.get_repos_in_org(o)]
                    augur.api.memory_cache_data(
                        {'data': repos}, "repos_for_%s" % o)
                else:
                    repos = cached_repos[0]['data']

                local_repo_obs += repos

            # build a list of all the repos to search (no way to filter by org apparently)
            query += " " + \
                     " ".join(["repo:%s/%s" % (r['organization']['login'], r['name'])
                               for r in local_repo_obs])

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
        dev_stats_ob = AugurGithubDevStats(user)
        since = datetime.datetime.now() - datetime.timedelta(days=int(lookback_days))
        merged_prs = self.fetch_author_merged_prs(user, since)
        for pr in merged_prs:
            dev_stats_ob.add_pr(pr)

        return dev_stats_ob.as_dict()

    def fetch_author_merged_prs(self, username, since, sort="created", order="desc"):
        """
        This will retrieve one or more authors prs in the given state
        :param username: A string or list of usernames
        :param state: Can be one of open, closed, merged
        :param sort: The sort order can be one of comments, created or updated
        :param order: Can be one of asc or desc
        :return: Returns a list of search results as a list of dictionaries
        """
        query = self._prepare_pr_search(
            orgs=None, state="merged", since=since, sort=sort, order=order)
        query += " author:%s" % username
        results = self.github.search_issues(
            query=query, sort=sort, order=order)
        return [r.raw_data for r in results]

    def fetch_organization_members(self, organization):
        """
        Gets a list of all organization members as a lits of dictionaries
        :param organization: The name of the organization
        :return: Returns a list of organization Member objects
        """
        org_ob = self.get_organization(organization)
        return [m.raw_data for m in org_ob.get_members()] if org_ob else []

    def get_pr(self, org, repo, number):
        """
        Gets the PR object from the given org/repo and PR number.
        :param org: The org string or Organization object
        :param repo: The repo string or Repo object
        :param number: The PR number
        :return: The PullRequest object.
        """
        try:
            org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)
            return repo_ob.get_pull(number)
        except TypeError:
            logging.error("Could not get org and repo objects from given data")
            return None

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
            self.logger.error(
                "Encountered an error while iterating over commits: %s" % e.message)

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

        if org and isinstance(org, (str, unicode)):
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
        repos = self.get_repos_in_org(org) or []
        data = {
            'org': None,
            'repos': []
        }

        for repo in repos:

            further_review = self.get_repo_further_review(repo)
            readme_summary_list = self.get_repo_readme_summary(repo)

            repo.raw_data["further_review"] = further_review or {}
            repo.raw_data['readme_summary'] = readme_summary_list[0] if len(
                readme_summary_list) else ""
            repo.raw_data["ua_stats"] = self.get_repo_commit_stats(repo)

            data['repos'].append(repo.raw_data)
            if not data['org']:
                data['org'] = repo.owner.login

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
                        result = re.findall(
                            '#.*\n([^#]*)', readme_str, re.MULTILINE)
                        return result
                    except Exception as e:
                        self.logger.info(
                            "Parse error during processing of README.md: %s" % e.message)
                else:
                    self.logger.warning("Unable to retrieve README.md")
            else:
                self.logger.warning("Unable to find README.md file")
        except github.UnknownObjectException, e:
            self.logger.error("Error occurred during README analysis: %s (%s)" % (
                e.message, str(e.__class__)))
        except github.GithubException, e:
            self.logger.error("Error occurred during further review analysis: %s (%s)" % (
                e.message, str(e.__class__)))
        return result

    def get_repo_further_review(self, repo, org=None):
        """
        Gets the further review information from the given repo
        :param repo: The repo object or name
        :param org: The org object or name.  Note that the org must be given if the repo is just a string
        :return: Returns a dictionary containing information about the maintainers and owners
        """
        fr = augur.api.get_memory_cached_data('FR_OPR_' + repo.full_name)
        if fr:
            return fr

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
                            self.logger.warning(
                                "Unable to find reviews section in further-review file")
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
                        self.logger.info(
                            "YAML error during processing of .further-review.yaml: %s" % e.message)
                else:
                    self.logger.warning(
                        "Unable to retrieve .further-review.yaml")
            else:
                self.logger.warning("Unable to find further-review.yaml file")
        except github.UnknownObjectException, e:
            self.logger.error(
                "Got a github error indicating that we were unable to find a file in the repo: %s (%s)" % (
                    e.message, str(e.__class__)))
        except github.GithubException, e:
            self.logger.error("Error occurred during further review analysis: %s (%s)" % (
                e.message, str(e.__class__)))

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
