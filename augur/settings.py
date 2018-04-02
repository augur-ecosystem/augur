import os
import sys

import logging

from munch import munchify

main = {}
db_instance = None


def load_settings(env=None):
    """
    (Re)Initialize global augur settings
    :return:
    """
    global main
    global db_instance

    if not env:
        env = os.environ

    main = munchify(
        {
            "project": {
                "debug": bool(int(env.get("DEBUG", True))),
                "augur_base_dir": os.path.dirname(os.path.abspath(__file__)),
                "base_dir": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            },
            "integrations": {
                "jira": {
                    "instance": env.get("JIRA_INSTANCE",""),
                    "username": env.get("JIRA_USERNAME",""),
                    "password": env.get("JIRA_PASSWORD",""),
                    "api_path": env.get("JIRA_API_PATH", "rest/api/2"),
                },
                "confluence": {
                    "url": "%s/wiki" % env.get("CONFLUENCE_INSTANCE", env.get("JIRA_INSTANCE","")),
                    "rest_url": "%s/wiki/rest/api/content" % env.get("CONFLUENCE_INSTANCE", ""),
                    "username": env.get("CONFLUENCE_USERNAME", env.get("JIRA_USERNAME","")),
                    "password": env.get("CONFLUENCE_PASSWORD", env.get("JIRA_PASSWORD","")),
                },
                "github": {
                    "base_url": env.get("GITHUB_BASE_URL", ""),
                    "login_token": env.get("GITHUB_LOGIN_TOKEN", ""),
                    "client_id": env.get("GITHUB_CLIENT_ID", ""),
                    "client_secret": env.get("GITHUB_CLIENT_SECRET", ""),
                },
                "tempo": {
                    "api_token": env.get("TEMPO_API_TOKEN")
                }
            },
            "datastores": {
                "main": {
                    "type": env.get("DB_TYPE"),
                    "postgres": {
                        "host": env.get("POSTGRES_DB_HOST"),
                        "dbname": env.get("POSTGRES_DB_NAME"),
                        "username": env.get("POSTGRES_DB_USERNAME",""),
                        "password": env.get("POSTGRES_DB_PASSWORD", ""),
                        "port": env.get("POSTGRES_DB_PORT", ""),
                    },
                    "sqlite": {
                        "path": env.get("SQLITE_PATH"),
                    }
                },
                "cache": {
                    "mongo": {
                        "host": env.get("MONGO_HOST","localhost"),
                        "port": int(env.get("MONGO_PORT", 27017)),
                    }
                }
            }
        }
    )

    if main.project.debug:
        # set root logger to show INFO and above
        logging.getLogger().setLevel(10)

        # add handlers for loggers if they don't already have one
        if len(logging.getLogger("timer").handlers) == 0:
            logging.getLogger("timer").addHandler(logging.StreamHandler(sys.stdout))

        if len(logging.getLogger("augurjira").handlers) == 0:
            logging.getLogger("augurjira").addHandler(logging.StreamHandler(sys.stdout))

    else:
        logging.getLogger().setLevel(40)


load_settings()

