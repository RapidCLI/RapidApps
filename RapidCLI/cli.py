import argparse
import inspect
import sys

from colorama import init

import moveworks.cse_tools.internal.scripts.extensible_cli_framework.settings as settings
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.app_loader import (
    create_cli_config_from_cli,
)
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.extension_registrar import (
    get_class_registrations,
    get_function_registrations,
    get_registrations,
)
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.utils import CLIColors


class CLIHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def _format_args(self, action: argparse.Action, default_metavar: str) -> str:
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = '%s' % get_metavar(1)
        elif action.nargs == argparse.OPTIONAL:
            result = '[%s]' % get_metavar(1)
        elif action.nargs == argparse.ZERO_OR_MORE:
            result = ''
        elif action.nargs == argparse.ONE_OR_MORE:
            result = ''
        elif action.nargs == argparse.REMAINDER:
            result = '...'
        elif action.nargs == argparse.PARSER:
            result = '%s ...' % get_metavar(1)
        else:
            formats = ['%s' for _ in range(action.nargs)]
            result = ' '.join(formats) % get_metavar(action.nargs)
        return result

    def _format_action(self, action):
        # determine the required width and the entry label
        help_position = min(self._action_max_length + 2, self._max_help_position)
        help_width = max(self._width - help_position, 11)
        action_width = help_position - self._current_indent - 2
        action_header = self._format_action_invocation(action)

        # no help; start on same line and add a final newline
        if not action.help:
            tup = self._current_indent, '', action_header
            action_header = '%*s%s\n' % tup

        # short action name; start on the same line and pad two spaces
        elif len(action_header) <= action_width:
            tup = self._current_indent, '', action_width, action_header
            action_header = '%*s%-*s  ' % tup
            indent_first = 0

        # long action name; start on the next line
        else:
            tup = self._current_indent, '', action_header
            action_header = '%*s%s\n' % tup
            indent_first = help_position
        # collect the pieces of the action help
        parts = [CLIColors.build_value_string(action_header)]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            help_lines = self._split_lines(help_text, help_width)
            parts.append('%*s%s\n' % (indent_first, '', help_lines[0]))
            for line in help_lines[1:]:
                parts.append('%*s%s\n' % (help_position, '', line))

        # or add a newline if the description doesn't end with one
        elif not action_header.endswith('\n'):
            parts.append('\n')

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_indented_subactions(action):
            parts.append(self._format_action(subaction))

        # return a single string
        return self._join_parts(parts)


class CLIParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formatter_class = lambda prog: CLIHelpFormatter(prog=prog)

    def error(self, _):
        self.print_help()
        sys.exit(2)


class CLI:
    def __init__(self, *args, **kwargs):
        self.cli_config = create_cli_config_from_cli(self.__class__)
        self._extend_cli(*args, **kwargs)
        self.root_parser = CLIParser()
        self._define_extension_flags()
        self.args = self.root_parser.parse_args()

    def print_hud(self):
        if settings.settings['debug']:
            print(CLIColors.build_info_string('DEBUG mode is ON'))

    def main(self):
        """The entry point to the CLI.  This is what runs it all."""
        self.print_hud()
        init()
        ext_name = self._get_flag_from_user_input()
        settings.settings['called_ext'] = ext_name
        self._run_extension(ext_name, *sys.argv[2:])

    def _get_flag_from_user_input(self) -> str:
        """Retrieve the flag to activate an extension."""
        try:
            return next(k for k, v in vars(self.args).items() if v != None)
        except StopIteration:
            self.root_parser.error('No arguments found')

    def _run_extension(self, extension_name, *args):
        """Runs the extension from the cli object dynamically."""
        ext = getattr(self, extension_name)
        if inspect.isfunction(ext):
            return ext(*args)
        ext.run_extension(*args)

    def _define_extension_flags(self):
        """Create the flags for function based extensions to be exposed to the user in the interface."""
        for registration in sorted(get_registrations(), key=lambda x: x.name):
            self.root_parser.add_argument(
                f'--{registration.name}',
                nargs='*',
                help=f'{registration.colored_registration_doc}\n',
            )

    def _extend_cli(self, *args, **kwargs):
        """Extend the cli object by injecting all of the extensions in to it."""
        for registration in get_class_registrations():
            cls_ext_obj = registration.extension
            _ = [setattr(cls_ext_obj, attr, attr_value) for attr, attr_value in kwargs.items()]
            setattr(cls_ext_obj, 'cli_config', self.cli_config)
            setattr(
                self,
                registration.name,
                cls_ext_obj,
            )

            setattr(
                cls_ext_obj, 'config', self.cli_config.get_extension_config(cls_ext_obj.get_name())
            )

        for registration in get_function_registrations():
            setattr(self, registration.name, registration.extension)

        return self
