import os
import shutil
import unittest
from unittest.mock import patch

from rapidcli import utils
from rapidcli.protos.channel.chat_channels_pb2 import ChannelGroup
from rapidcli.protos.itsm.itsm_systems_pb2 import ITSMSystem
from rapidcli.protos.security_factors.authn_system_enums_pb2 import AuthnSystemProviderEnum


class TestUtils(unittest.TestCase):
    def test_choice_from_proto(self):
        with patch('builtins.input', return_value='2'):
            choice = utils.select_choice_from_proto(ChannelGroup.ChannelType.DESCRIPTOR.values)
            self.assertEqual(choice, 'SLACK')

        with patch('builtins.input', return_value='8'):
            choice = utils.select_choice_from_proto(ITSMSystem.DESCRIPTOR.values)
            self.assertEqual(choice, 'NOT_IMPLEMENTED')

    def test_get_enums_from_proto(self):
        full_test_data = [
            ('UNKNOWN_PROVIDER', 'unknown provider'),
            ('OKTA', 'okta'),
            ('RSA', 'rsa'),
            ('SYMANTEC', 'symantec'),
            ('GOOGLE', 'google'),
            ('DUO', 'duo'),
            ('YUBICO', 'yubico'),
            ('FIDO', 'fido'),
            ('ONELOGIN', 'onelogin'),
            ('PING_ID', 'ping id'),
            ('CUSTOM', 'custom'),
            ('MICROSOFT_AUTHENTICATOR', 'microsoft authenticator'),
        ]
        exlusion_list = ['YUBICO', 'FIDO', 'ONELOGIN', 'PING_ID', 'CUSTOM']
        filtered_list_target = [
            ('UNKNOWN_PROVIDER', 'unknown provider'),
            ('OKTA', 'okta'),
            ('RSA', 'rsa'),
            ('SYMANTEC', 'symantec'),
            ('GOOGLE', 'google'),
            ('DUO', 'duo'),
            ('MICROSOFT_AUTHENTICATOR', 'microsoft authenticator'),
        ]
        full_choices = utils.get_enums_from_proto(
            AuthnSystemProviderEnum.Provider.DESCRIPTOR.values
        )
        filtered_choices = utils.get_enums_from_proto(
            AuthnSystemProviderEnum.Provider.DESCRIPTOR.values, exlusion_list
        )
        self.assertEqual(full_test_data, full_choices)
        self.assertEqual(filtered_list_target, filtered_choices)

    def test_get_export_path(self):
        # Should have actually been created don't forget to tear down
        export_path = utils.get_export_path('test_get_export_path')
        sub_dir_export = utils.get_export_path(
            'test_get_export_path', 'sub_file', 'would_be_file_name'
        )
        self.assertTrue(os.path.exists(export_path))
        self.assertTrue(os.path.exists(os.path.dirname(sub_dir_export)))

        # Tearing down
        shutil.rmtree(export_path)
        self.assertFalse(os.path.exists(export_path))

    def test_write_content(self):
        file_path = os.path.join('temp', 'file.tst')

        # Should have actually been created don't forget to tear down
        utils.write_content('test content', file_path)
        self.assertTrue(os.path.exists(file_path))

        # Tearing down
        shutil.rmtree(os.path.dirname(file_path))

    def test_is_snake_case(self):
        self.assertTrue(utils.is_snake_case('_is_snake_case'))
        self.assertFalse(utils.is_snake_case('NotSnakeCase'))
        self.assertTrue(utils.is_snake_case('is_snake_'))
        self.assertFalse(utils.is_snake_case('NOTSNAKE'))

    def test_change_to_snake_case(self):
        self.assertEqual(utils.change_to_snake_case('camelCase'), 'camel_case')
        self.assertEqual(utils.change_to_snake_case('PascalCase'), 'pascal_case')
        self.assertEqual(utils.change_to_snake_case('UPPERCASE'), 'uppercase')

    def test_iterate_down_to(self):
        test_data = {
            'yolo': 'test_value',
            'brolo': {
                'nested_key': 'nested_test_value',
                'nested_list': [{'key': 'value1'}, {'key': 'value2'}],
            },
        }

        self.assertEqual(utils.iterate_down_to(test_data, 'yolo'), 'test_value')
        self.assertEqual(
            utils.iterate_down_to(test_data, 'brolo', 'nested_key'), 'nested_test_value'
        )
        self.assertEqual(utils.iterate_down_to(test_data, 'brolo', 'nonexistent_key'), None)
        self.assertEqual(
            utils.iterate_down_to(test_data, 'brolo', 'nested_list', 'key'), ['value1', 'value2']
        )

    def test_is_plural(self):
        self.assertTrue(utils.is_plural('tables'))
        self.assertTrue(utils.is_plural('countries'))
        self.assertFalse(utils.is_plural('table'))

    def test_make_singular(self):
        self.assertEqual(utils.make_singular('tables'), 'table')
        self.assertEqual(utils.make_singular('countries'), 'country')


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
