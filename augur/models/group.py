
import augur
from augur.models import AugurModel


class Group(AugurModel):
    """
    A group represents an organization unit.  A group can be made up of teams and products.  There is a
    1/1 relationship between groups and workflows.
    """
    def __init__(self):
        # must come before
        super(Group, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("name", "", unicode)
        self.add_prop("teams", [], list)
        self.add_prop("products", [], list)
        self.add_prop("workflow_id", "", unicode)

    def get_workflow(self):

        if self.workflow_id:
            return augur.api.get_workflow(self.workflow_id)
        else:
            return None

    def handle_field_import(self, key, value):
        if key == "teams":
            # This is expected to be a space delimited list of string ids (e.g. "vd")
            value = map(lambda x: x.strip(), value.split(" "))
        elif key == "products":
            # This is expected to be a space delimited list of string ids (e.g. "top")
            value = map(lambda x: x.strip(), value.split(" "))

        super(Group, self).handle_field_import(key, value)

    def handle_post_import(self):
        super(Group, self).handle_post_import()


if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/teams.csv"
        , Group)

    print models
