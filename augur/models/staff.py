import datetime

from augur.models import AugurModel


class StaffStatus(object):
    Unknown = "Unknown"
    Active = "Active"
    Deactivated = "Deactivated"


class StaffRole(object):
    Unknown = "Unknown"
    Developer = "Developer"
    QE = "QE"
    Manager = "Manager"
    Directory = "Director"


class Staff(AugurModel):
    def __init__(self):
        # must come before
        super(Staff, self).__init__()

    def __repr__(self):
        return self.last_name

    def _add_properties(self):
        self.add_prop("first_name", "", (str,unicode))
        self.add_prop("last_name", "",(str,unicode))
        self.add_prop("company", "",(str,unicode))
        self.add_prop("avatar_url", "",(str,unicode))
        self.add_prop("role", "",(str,unicode))
        self.add_prop("email", "",(str,unicode))
        self.add_prop("rate", 0.0,float)
        self.add_prop("start_date", None, datetime.datetime)
        self.add_prop("jira_username", "", (str,unicode))
        self.add_prop("ua_username", "", (str,unicode))
        self.add_prop("github_username", "", (str,unicode))
        self.add_prop("status", "", (str,unicode))
        self.add_prop("base_daily_cost", 0.0, float)
        self.add_prop("base_weekly_cost", 0.0, float)
        self.add_prop("base_annual_cost", 0.0, float)

    def handle_field_import(self, key, value):

        if key == "rate":
            self.rate = float(value)
            return

        if key == "status":
            if value not in (StaffStatus.Active, StaffStatus.Deactivated):
                value = StaffStatus.Unknown

        super(Staff, self).handle_field_import(key, value)

    def handle_post_import(self):

        # Calculate the cost of the employee post import
        if self.status == StaffStatus.Active:
            self.base_daily_cost = self.rate * 8
            self.base_weekly_cost = self.base_daily_cost * 5
            self.base_annual_cost = self.base_weekly_cost * 50  # assume two weeks of vacation
        else:
            self.base_daily_cost = 0.0
            self.base_weekly_cost = 0.0
            self.base_annual_cost = 0.0

        super(Staff, self).handle_post_import()

    def get_jira_username(self):
        if 'jira' in self.usernames:
            return self.usernames['jira']
        else:
            return ''


if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/staff/engineering_ftes.csv"
        , Staff)

    print models
