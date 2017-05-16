import datetime
import exceptions
import json
import logging
import re

import github
import yaml
from github import Github
from github.GithubObject import GithubObject

from augur import common
from augur import settings
from augur.common import cache_store
from augur.common.timer import Timer
from augur.integrations.uajira.uajira import get_jira

LOGIN_TOKEN = "1a764970a4a22d220bf416cbd5266d497f3d55a0"
DEFAULT_LOOKBACK_DAYS = 90

# These are the github orgs that we will monitor for prs/commits
GITHUB_ORGS = ['ua', 'v6', 'harbour', 'b2b', 'ui', 'lib', 'apps']


class GitFileNotFoundError(exceptions.Exception):
    """Used for reporting a problem when scanning a repo for a file"""
    pass


class UaGithub(object):
    def __init__(self):
        self.github = Github(login_or_token=settings.main.integrations.github.login_token,
                         password="x-oauth-basic",
                         base_url=settings.main.integrations.github.base_url)

        self.mongo = cache_store.UaStatsDb()
        self.prs_data_store = cache_store.UaTeamPullRequestsData(self.mongo)
        self.open_prs_data_store = cache_store.UaTeamOpenPullRequestsData(
            self.mongo)
        self.permissions_data_store = cache_store.UaPermissionsOrgData(
            self.mongo)
        self.jira = get_jira()
        self.logger = logging.getLogger("uagithub")

    def _cache_merged_prs_for_repo(self, repos, since):
        """
        Retrieves all PRs that have been merged since the "since" date and stores them in mongo.

        :param repos:
        :param since:
        :return:
        """
        results = dict()
        for repo in repos:
            results[repo.full_name] = {
                "added_prs": 0,
            }
            filtered_prs = []
            prs = repo.get_pulls(
                state="closed", sort="created", direction="desc")
            try:
                for p in prs:
                    if p.created_at > since:
                        if p.merged:
                            filtered_prs.append(p.raw_data)
                            results[repo.full_name]['added_prs'] += 1
                    else:
                        break

                # add this repo to the cache
                if len(filtered_prs) > 0:
                    self.logger.info(repo.name + ": Found %d PRs" % len(filtered_prs))
                    self.prs_data_store.save_prs(filtered_prs)
                else:
                    self.logger.info(repo.name + ": No PRs since %s" % str(since))

                results[repo.full_name]['added_prs'] = len(filtered_prs)
                results[repo.full_name]['since'] = str(since)

            except Exception as e:
                self.logger.error("Errur during _cache_merged_prs_for_repo: %s"%e.message)

        return results

    def _cache_open_prs_for_repo(self, repos):
        """
        Retrieves all PRs that have been opened against upstream repos
        :param repos:
        :return:
        """
        results = dict()
        for repo in repos:
            results[repo.full_name] = {
                "added_prs": 0,
            }
            filtered_prs = []
            prs = repo.get_pulls(state="open", sort="created", direction="asc")
            try:
                for p in prs:
                    fr = common.get_cache('FR_OPR', repo.full_name)
                    if not fr:
                        fr = self.get_repo_further_review(repo)
                        common.set_cache('FR_OPR', repo.full_name, fr)

                    fpr = p.raw_data
                    fpr['further_review'] = fr
                    filtered_prs.append(fpr)
                    results[repo.full_name]['added_prs'] += 1

                # add this repo to the cache
                if len(filtered_prs) > 0:
                    self.open_prs_data_store.save_prs(filtered_prs)

                results[repo.full_name]['added_prs'] = len(filtered_prs)

            except Exception as e:
                self.logger.error("Error during caching of open PRs: %s" % e.message)

        return results

    def refresh_open_pr_cache(self):
        results = {}

        # clear out all stored open prs.
        self.open_prs_data_store.empty()

        try:
            # for each org, retrieve and store the open prs (they are both
            # returned and stored in mongo
            for org in GITHUB_ORGS:
                results.update(self._cache_open_prs_for_repo(
                    self.github.get_organization(org).get_repos()))
        except Exception, e:
            logging.error(
                "Encountered an error during github cache refresh: %s" % e.message)

    def get_maintainer_prs(self, username=None):
        open_prs = self.open_prs_data_store.load_open_prs()
        responsible_prs = []
        for pr in open_prs:
            maintainer_usernames = map(lambda x: x.get('username', ''),
                                       pr['further_review'].get('maintainers', []))

            if not username or (username in maintainer_usernames):
                responsible_prs.append(pr)

        return responsible_prs

    def get_user_prs(self, username):
        return self.open_prs_data_store.load_open_prs(username)

    def get_all_prs(self, since=None):
        return self.prs_data_store.load_prs_since(since=since)

    def refresh_pr_cache(self):
        """
        Updates the PRs for all repos that have been merged and returns a result list that shows the number of PRs
        that were added for each repo.
        :return: A list of all the repos with the number of PRs that were added for each.
        """
        since = self.get_cache_update_since_date()
        results = {}

        # get all the prs for all repos in each organization
        for org in GITHUB_ORGS:
            results.update(self._cache_merged_prs_for_repo(
                self.github.get_organization(org).get_repos(), since))

        return results

    def get_cache_update_since_date(self):
        """
        Looks for the most recent pr and gets when it was created then returns the
        :return:
        """
        pr = self.prs_data_store.get_most_recent_pr()
        if pr:
            return pr['created_at'] - datetime.timedelta(days=14)

        else:
            return datetime.datetime.now() - datetime.timedelta(days=60)

    def get_all_user_stats(self, since=None):
        stats = {}
        most_recent_pr = None

        with Timer("get_all_user_stats") as t:
            teams = self.jira.get_all_developer_info()
            t.split("Finished getting developer info")

            if teams:
                # holds the UaGithubDevStats objects keyed on username
                dev_stats_obs = {}

                # this will either pull straight from Github or grab whatever was recently
                #   stored in mongo.
                all_prs = self.get_all_prs(since)
                t.split("Finished getting all PRs")

                try:
                    # iterate over all prs and add to our collection of github dev objects that will
                    #   gather statistics across all PRs as they're added.
                    for pr in all_prs:

                        # check when one of the PRs was stored and use that as the storage time
                        #   since they are refreshed entirely with each update.
                        if not most_recent_pr or pr['created_at'] > most_recent_pr:
                            most_recent_pr = pr['created_at']

                        if 'user' in pr and pr['user']:
                            username = pr['user']['login']
                        else:
                            username = 'undefined'
                            pr['user'] = {'login': username}

                        if username not in dev_stats_obs:
                            dev_stats_obs[username] = cache_store.UaGithubDevStats(
                                username)
                        dev_stats_obs[username].add_pr(pr)

                    t.split("Finished iterating over %d PRs" % len(all_prs))

                    # create the final dictionary of stats keyed by username with basic dev info
                    #   plus anything gathered from the dev_stats_obs
                    for team, info in teams['teams'].iteritems():
                        for user, user_info in info['members'].iteritems():
                            stats[user] = user_info
                            if user in dev_stats_obs:
                                github_stats_ob = dev_stats_obs[user].as_dict()
                            else:
                                github_stats_ob = cache_store.UaGithubDevStats(
                                    user).as_dict()

                            stats[user].update(github_stats_ob)
                    t.split("Finished creating the stats object")

                except Exception as e:
                    self.logger.error("Error during get_all_user_stats: %s" % e.message)
                    return None

        return {
            'developers': stats,
            'most_recent_pr_time': most_recent_pr
        }

    def get_user_stats(self, user, all_prs=None, since=None):
        """
        Get github status for a single user.  This will retrieve the most recent data if not already
        stored in the database.  So at this point, this call could take 20 minutes to complete
        :param user:
        :param all_prs:
        :param since: How far back to look.
        :return: Returns a dict with github stats info in it
        """
        if not all_prs:
            all_prs = self.get_all_prs(since)

        user_prs = []

        dev_stats_ob = cache_store.UaGithubDevStats(user)
        for pr in all_prs:
            dev_stats_ob.add_pr(pr)
            if pr['user']['login'] == user and pr['merged']:
                if 'links' not in pr:
                    pr['links'] = pr['_links']

                user_prs.append(pr)

        return dev_stats_ob

    def get_repos_in_org(self, org):

        try:
            # try an actual org.
            org_ob = self.github.get_organization(org)
        except github.UnknownObjectException:

            # try a user org
            try:
                org_ob = self.github.get_user(org)
            except github.UnknownObjectException, e:
                return None

        if org_ob:
            return org_ob.get_repos()

        return None

    def get_permissions_data(self, username):

        # if there is no data in the db then load it now.
        if not self.permissions_data_store.has_data():
            org_ob = self.github.get_organization("UaPermissions")
            if org_ob:
                members = org_ob.get_members()
                members_data = [m.raw_data for m in members]
                self.permissions_data_store.save(members_data)

        return self.permissions_data_store.get_user(username)

    def get_repo_commit_stats(self, repo, org=None):

        org_ob, repo_ob = self.get_org_and_repo_from_params(repo, org)

        since = datetime.datetime.now() - datetime.timedelta(days=90)
        commits = repo_ob.get_commits(since=since)
        by_author = dict()
        avg_comments = 0
        total_comments = 0

        commit_objects = []
        for c in commits:
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
        if not org and not isinstance(repo, GithubObject):
            raise Exception(
                "If repo given is not a github object then organization must be specified")

        repo_ob = None
        org_ob = None

        if repo and isinstance(repo, GithubObject):
            repo_ob = repo

        if org and isinstance(repo, GithubObject):
            raise Exception(
                "If org is given then repo should be a string otherwise there's no reason to pass the org")

        if org and isinstance(org, str):
            org_ob = self.github.get_organization(org)

        elif org and isinstance(org, GithubObject):
            org_ob = org

        elif org:
            raise Exception("Org must be a github object or a string")

        if not repo_ob:
            repo_ob = org_ob.get_repo(repo)

        if not org_ob and repo_ob:
            org_ob = repo_ob.organization

        return org_ob, repo_ob

    def get_org_component_data(self, org):
        ds = cache_store.UaComponentOwnership(self.mongo)
        data = ds.load_org(org)
        if not data:
            repos = self.get_repos_in_org(org) or []
            data = {
                'org': None,
                'repos': []
            }

            for repo in repos:

                try:
                    further_review = self.get_repo_further_review(repo)
                    repo.raw_data["further_review"] = further_review or {}
                    repo.raw_data["ua_stats"] = self.get_repo_commit_stats(
                        repo)

                except Exception, e:
                    repo.raw_data["further_review"] = {}

                data['repos'].append(repo.raw_data)
                if not data['org']:
                    data['org'] = repo.owner.login

            # cache in case anything else wants to use this info
            ds.save(data)

        return data

    def get_repo_further_review(self, repo, org=None):

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

                            return result

                    except yaml.YAMLError, e:
                        self.logger.info("YAML error during processing of .further-review.yaml: %s" % e.message)
                else:
                    self.logger.warning("Unable to retrieve .further-review.yaml")
            else:
                self.logger.warning("Unable to find further-review.yaml file")
        except github.UnknownObjectException, e:
            self.logger.error("Error occurred during further review analysis: %s (%s)" % (e.message, str(e.__class__)))

        result['owner'] = {
            "name": "Karim Shehadeh",
            "email": "kshehadeh@underarmour.com"
        }

        return result

    def get_repo_package_json(self, repo, org=None):

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
    gh = UaGithub()
    gh.refresh_open_pr_cache()
