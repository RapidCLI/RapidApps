"""This file is responsible for collecting and registering the extensions for the CSECLI.

The only thing that is needed for the extension registrar is to use the @register_extension decorator
on the extension class and import it in the file cse_cli to have registration take place.

@register_extension(alias=True) registers the object to be set up in zshrc file if you run the setup_cse_tools
from the CLI.  Aliasing only works on non-class functions at the moment.  See base_extensions.py for examples on how
to register and create a function.  Remember to expose it in the actual interface in cse_cli.py
"""
import functools
import inspect
import os
import pathlib
from typing import Any, Callable, Dict, Set, Union

from moveworks.cse_tools.internal.scripts.extensible_cli_framework.extension import Extension
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.utils import (
    CLIColors,
    get_repo_root,
)


class Registration:
    def __init__(
        self, handle: Union[Callable, Extension], zshrc_alias=False, alt_alias=None, is_cli=False
    ):
        self.is_function = inspect.isfunction(handle)

        self.extension = (
            Extension(handle) if self.is_function else handle()
        )  # Either function extension or a class extension
        self.name = self.extension.get_name()
        self.alias = self.name if zshrc_alias else None
        self.alt_alias = alt_alias
        self.is_cli = is_cli
        self.registration_doc = self.get_registration_doc()
        self.colored_registration_doc = self.get_colored_registration_doc()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the extension callable with the arguments that it orginally needs."""
        if not self.extension.is_function:
            raise TypeError(
                f'The extension named {self.name} is not a function based extension and not callable.'
            )
        return self.extension(*args, **kwargs)

    def get_aliases(self) -> str:
        """Retrieve all the aliases that are available for the extension."""
        return [alias for alias in [self.alias, self.alt_alias] if alias]

    def get_colored_registration_doc(self) -> str:
        """Get the docstring of the extension colored along with the functions arguments."""
        doc = []

        if self.extension.args and not self.is_cli:
            colored_args = CLIColors.build_value_string(f"args: ({', '.join(self.extension.args)})")
            doc.append(colored_args)
        else:
            colored_args = CLIColors.build_value_string(f'args: (ext_name)')
            doc.append(colored_args)

        if not self.is_cli:
            colored_doc_string = CLIColors.build_doc_string(self.extension.doc_string)
            doc.append(colored_doc_string)
        return '\n'.join(doc)

    def get_registration_doc(self) -> str:
        """Get the docstring of the extension along with the extensions arguments."""
        if self.is_cli:
            return ''

        doc = []
        if self.extension.args:

            if not self.is_cli:
                doc.append(f"args: ({', '.join(self.extension.args)})")

        doc.append(self.extension.doc_string if self.extension.doc_string else '')
        return '\n'.join(doc)

    def _py_to_sh_cli_arguments_string(self):
        """Convert python argument list to positional argument list for bash."""
        if not self.is_cli:
            return ' '.join([f'${arg_pos+1}' for arg_pos in range(len(self.extension.args))])
        else:
            return ' '.join(
                [f'${arg_pos+1}' for arg_pos in range(get_greatest_num_args_in_registrations() + 1)]
            )

    def _py_to_sh_docstring(self):
        sh_docstring_list = []
        sh_docstring_list.append(f"<<'###'")

        if self.is_cli:
            return ''

        if not self.is_cli:
            sh_docstring_list.append(f"# args: {', '.join(self.extension.args)}")

        sh_docstring_list.append(f'{self.extension.doc_string}')
        sh_docstring_list.append(f'###')
        return '\n'.join(sh_docstring_list)

    def _colored_py_to_sh_docstring(self):
        sh_docstring_list = []
        sh_docstring_list.append(f"<<'###'")

        if not self.is_cli:
            sh_docstring_list.append(
                f"# args: {CLIColors.build_value_string(', '.join(self.extension.args))}"
            )
        else:
            sh_docstring_list.append(
                f'# args: # args: equal to the underlying extension being called'
            )

        sh_docstring_list.append(CLIColors.build_doc_string(self.extension.doc_string))
        sh_docstring_list.append(f'###')
        return '\n'.join(sh_docstring_list)

    def get_alias_strings(self):
        """Convert python functions registered as aliases to bash alias string."""
        CLI_FROM_ROOT_PATH = 'moveworks/cse_tools/internal/scripts/cse_cli/cse_cli.py'
        alias_strings = []
        for alias in self.get_aliases():
            alias_builder = [f'function {alias}() {{']
            alias_builder.append(self._py_to_sh_docstring())
            if not self.is_cli:
                alias_builder.append(
                    f'\tpython {os.path.join(get_repo_root(), CLI_FROM_ROOT_PATH)} --{self.name} {self._py_to_sh_cli_arguments_string()}'
                )
            else:
                alias_builder.append(
                    f'\tpython {os.path.join(get_repo_root(), CLI_FROM_ROOT_PATH)} {self._py_to_sh_cli_arguments_string()}'
                )
            alias_builder.append(f'}}')

            alias_strings.append('\n'.join(alias_builder))
        return alias_strings


def register_extension(
    ext: Union[Callable, Extension] = None,
    zshrc_alias: bool = False,
    alt_alias: str = None,
    is_cli=False,
):
    """Decorate any class or function as an extension.

    This function decorates any class of function as an extension to be registered
    with the CLI.  This makes it immediately available in the commandline arguments.

    You can check to see if it showed up by running python cse_cli.py --help

    You can make the extension an alias to be stored in the ~/.zshrc file by setting zshrc to True.
    """

    @functools.wraps(ext)
    def wrapper(ext):
        registration = Registration(ext, zshrc_alias, alt_alias, is_cli)
        extension_registry[registration.name] = registration
        return ext

    return wrapper


extension_registry: Dict[str, Registration] = {}


def get_alias_registrations():
    """Get all registrations for extensions if they have are supposed to have a zsrhc alias."""
    return {registration for registration in extension_registry.values() if registration.alias}


def get_function_registrations():
    """Retrieve the functions in the registry."""
    return [
        registration for registration in extension_registry.values() if registration.is_function
    ]


def get_class_registrations():
    """Retrieve the classes in the registry."""
    return [
        registration for registration in extension_registry.values() if not registration.is_function
    ]


def get_registrations() -> Set[Registration]:
    """Retrieve the registrations present in the extension registry."""
    return set(extension_registry.values())


def get_extension_template_directory(ext: Union[Callable, Extension, Registration]) -> str:
    """Retrieve the extension's template directory.

    Extension template directories are created with the name of extension as the template folder.
    """
    if isinstance(ext, Registration):
        return os.path.join(
            pathlib.Path(inspect.getfile(ext.extension.handle)).parent.parent.resolve(),
            'templates',
            ext.extension.name,
        )
    elif isinstance(ext, Extension):
        return os.path.join(
            pathlib.Path(inspect.getfile(inspect.getmodule(ext.handle))).parent.parent.resolve(),
            'templates',
            ext.name,
        )


def get_greatest_num_args_in_registrations():
    return max(len(registration.extension.args) for registration in extension_registry.values())
