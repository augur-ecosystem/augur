
from augur.models import AugurModel


class Product(AugurModel):
    def __init__(self):
        # must come before
        super(Product, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("name", "", unicode)

    def handle_field_import(self, key, value):
        super(Product, self).handle_field_import(key, value)

    def handle_post_import(self):
        super(Product, self).handle_post_import()


if __name__ == '__main__':
    models = AugurModel.import_from_csv(
        "/Users/karim/dev/tools/augur-tools/augur/augur/data/products.csv"
        , Product)

    print models
