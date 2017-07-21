
from augur.models import AugurModel, staff


class Team(AugurModel):
    """
    The team represents a scrum team and is made up of staff objects, a board id and a product.  One team can be
    assigned one product but a product could be on multiple teams.
    """
    def __init__(self):
        # must come before
        super(Team, self).__init__()
        import augur
        self.__dict__['_members'] = {}
        self.__dict__['_staff'] = augur.api.get_all_staff_as_dictionary()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("name", "", unicode)
        self.add_prop("member_ids", [], list)
        self.add_prop("board_id", 0, int)
        self.add_prop("product_id", "", unicode)

    def handle_field_import(self, key, value):
        if key == "member_ids":
            # This is expected to be a space delimited list of usernames
            value = map(lambda x: x.strip(), value.split(" "))

        super(Team, self).handle_field_import(key, value)

    def as_dict(self):
        d = super(Team, self).as_dict()
        d['members'] = self.get_members()
        return d

    def get_members(self):
        return {username: s.as_dict() for username,s in self.__dict__['_members'].iteritems()}

    def handle_post_import(self):

        # Load all information
        self.__dict__['_members'] = {}
        for username in self.member_ids:
            if username in self.__dict__['_staff']:
                self.__dict__['_members'][username] = self._staff[username]

        super(Team, self).handle_post_import()

if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/teams.csv"
        , Team)

    print models
