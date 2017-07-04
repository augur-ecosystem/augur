
from augur.models import AugurModel


class Workflow(AugurModel):
    def __init__(self):
        # must come before
        super(Workflow, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("name", "", unicode)
        self.add_prop("statuses", [], list)
        self.add_prop("positive_resolutions", [], list)

    def handle_field_import(self, key, value):
        if key == "statuses":
            # This is expected to be a comma delimited list of statuses
            value = map(lambda x: x.strip(), value.split(","))
        elif key == "positive_resolutions":
            # This is expected to be a comma delimited list of statuses
            value = map(lambda x: x.strip(), value.split(","))

        super(Workflow, self).handle_field_import(key, value)

    def handle_post_import(self):
        super(Workflow, self).handle_post_import()


if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/workflows.csv"
        , Workflow)

    print models
