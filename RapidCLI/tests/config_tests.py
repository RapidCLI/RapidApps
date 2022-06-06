import os
import pathlib
import unittest

from rapidcli.app_loader import (
    create_cli_config_from_cli_from_data,
)
from rapidcli.config_registrar import (
    CLIConfig,
    InputMenuConfig,
    SearchConfig,
)
from rapidcli.extension import Extension
from rapidcli.tests.cli_test_configs import (
    NestedObjInExtensionConfig,
    NestedObjInListConfig,
    TableConfig,
    TestExtensionConfig,
)
from rapidcli.utils import load_yaml


class TestUtils(unittest.TestCase):
    def setUp(self) -> None:
        cli_config_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'cli_config.yml')
        apps_path = pathlib.Path(__file__).parent.resolve().parent.resolve()
        self.cli_config_yaml_data = load_yaml(cli_config_path)
        self.cli_config = create_cli_config_from_cli_from_data(self.cli_config_yaml_data, apps_path)
        self.test_extension = Extension()
        self.test_extension.cli_config = self.cli_config
        self.test_extension.config = self.cli_config.test_extension

    def test_create_cli_config_from_cli_from_data(self):
        self.assertEqual(type(self.cli_config), CLIConfig)

    def test_extension_config_create(self):
        self.assertEqual(
            TestExtensionConfig,
            type(self.cli_config.test_extension),
        )

    def test_get_extension_config(self):
        self.assertEqual(
            self.cli_config.get_extension_config('test_extension'),
            self.cli_config.test_extension,
        )

    def test_input_map_created(self):
        self.assertEqual(type(self.cli_config.test_extension.input_menu), InputMenuConfig)

    def test_static_var_available(self):
        # Retrieve the value from extension's config from the extension
        self.assertEqual(self.test_extension.config.static_var, 'static_var_test')

        # Retrieve the value from the root config
        self.assertEqual(self.cli_config.test_extension.static_var, 'static_var_test')

        # Retrieve the value from config dynamically retrieved.
        self.assertEqual(
            self.cli_config.get_extension_config('test_extension').static_var,
            'static_var_test',
        )

    def test_nested_obj_in_extension_created(self):
        self.assertEqual(
            type(self.cli_config.test_extension.nested_obj_in_extension),
            NestedObjInExtensionConfig,
        )

    def test_nested_tables_objects_instantiated(self):
        self.assertEqual(
            type(self.cli_config.test_extension.nested_obj_in_extension.tables[0]),
            TableConfig,
        )

    def test_search_config_instantiation(self):
        self.assertEqual(
            type(self.cli_config.test_extension.searches[0]),
            SearchConfig,
        )

    def test_nested_table_object_value_populated(self):
        self.assertEqual(
            self.cli_config.test_extension.nested_obj_in_extension.tables[0].name,
            'test_table_name',
        )

    def test_nested_obj_in_list_created(self):
        self.assertEqual(
            type(
                self.cli_config.test_extension.nested_obj_in_extension.tables[0].nested_obj_in_list
            ),
            NestedObjInListConfig,
        )


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
