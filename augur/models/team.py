
from augur.models import AugurModel


class Team(AugurModel):
    """
    The team represents a scrum team and is made up of staff objects, a board id and a product.  One team can be
    assigned one product but a product could be on multiple teams.
    """
    def __init__(self):
        # must come before
        super(Team, self).__init__()

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

    def handle_post_import(self):
        super(Team, self).handle_post_import()


if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/teams.csv"
        , Team)

    print models
