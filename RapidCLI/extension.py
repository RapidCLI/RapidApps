import inspect
import os
import pathlib
import sys
from typing import Any, Callable, Dict, List, Tuple, Union

from tqdm import tqdm

from moveworks.cse_tools.internal.scripts.extensible_cli_framework import utils
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.app_loader import (
    render_config_args,
)
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.config_registrar import (
    CLIConfig,
    Config,
)
from moveworks.cse_tools.internal.scripts.extensible_cli_framework.utils import change_to_snake_case


class Extension:
    def __init__(self, handle: Callable = None):
        # either this is an extension object or it's a function that needs an extension wrapper
        self.handle = handle if handle else self
        self.is_function = inspect.isfunction(handle)
        self.name = self.get_name()
        self.doc_string = inspect.getdoc(self.handle)
        self.args = self.get_extension_args()
        self.config: Config = None
        self.cli_config: CLIConfig = None
        self.debug = False  # this will be used to debug each extension
        self.template_location = self.get_extension_template_directory()
        self.has_menu_header_been_displayed = False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.handle(*args, **kwargs)

    def __name__(self):
        return self.__class__.__name__

    def get_name(self):
        """Retrieve the name of the extension in snake_case."""
        obj_to_inspect = self.handle if self.is_function else self.handle.__class__
        members = inspect.getmembers(obj_to_inspect)
        for attr, value in members:
            if attr == '__name__':
                return change_to_snake_case(value)

    # TODO(bgarrard):  Find a way to have extension entry point with varying arguments
    # that can be visible when creating documentation and not throw W0221 error.
    def main(self, *args, **kwargs):
        """This method is the entry point to run a class based extension."""
        if self.is_function:
            return self.run_function(*args, **kwargs)

        raise NotImplementedError(
            f'The extension ({utils.CLIColors.build_value_string(self.get_name())}), has not implemented the main method'
        )

    def run_extension(self, *args, **kwargs):
        """This runs the extension in its lifecyle hooks to be used. ready() and start()."""
        self.ready()
        if type(self).start == Extension.start:
            self.main(*args, **kwargs)
        elif type(self).main != Extension.main:
            self.start()
            self.main(*args, **kwargs)
        else:
            self.start()

    def run_function(self, *args, **kwargs):
        """If the current extension is function based, just run it."""
        return self(*args[: len(self.args)])

    def show_input_menu(
        self,
        input_menu_name: str,
        input_transformer: Callable = None,
        choice_descriptions: List[str] = None,
    ):
        """Create a menu out of the input map of an extensions config to retrieve user input.

        This method can recieve a transformer that will take a str and output one.
        """
        extension_input_menu = self.config.get_var(input_menu_name).input_menu

        # Gather Config Inputs
        if not self.has_menu_header_been_displayed:
            print(utils.CLIColors.build_info_string(f"Welcome to {self.get_name()}'s menu!\n"))
            self.has_menu_header_been_displayed = True

        for config_attr, input_menu_value in extension_input_menu.items():
            if config_attr is 'input_menu':
                continue
            user_input = None
            try:
                question = input_menu_value['question']
                colored_message = utils.CLIColors.build_info_string(f'{question}')
                if 'choices' in input_menu_value:
                    user_input = self.get_user_input_from_choices(
                        input_menu_value['choices'], choice_descriptions, colored_message
                    )
                else:
                    user_input = input(colored_message)

                if user_input and input_transformer:
                    user_input = input_transformer(user_input)
                    # setting the input key to an attribute of the extension while in use
                    self.config.set_var(config_attr, user_input)
                elif user_input:
                    self.config.set_var(config_attr, user_input)
            except IndexError:
                raise IndexError(
                    f'The keys for the input map of this extension are not correct. Review the schema.'
                )

    def show_confirmation_menu(self):
        """Start a confirmation menu to the user for the given attributes on the extension config."""
        result = None
        # confirmation menu
        print(
            utils.CLIColors.build_info_string(
                'Confirm the Following Settings for the following inputs.'
            )
        )
        while result not in ['y', 'yes']:
            for config_attr in self.config.confirmation_menu.attrs:
                ext_config_attr_val = self.config.get_var(config_attr)
                print(f'{config_attr}: {utils.CLIColors.build_value_string(ext_config_attr_val)}')
            if result is not None:
                print("it seems you made an invalid selection before.  Please type 'y' or 'n'")
            result = input('Continue? y/n\n')  # nosec
            if result in ['n', 'no']:
                print('exiting setup')
                sys.exit()

    def get_extension_args(self):
        """Retrieve the arguments for an function based or class based extension."""
        if self.is_function:
            return inspect.getfullargspec(self.handle).args
        return inspect.getfullargspec(self.main).args[1:]

    def get_rendered_extension_templates(
        self, template_directory: str = None, render_args: Union[Dict, Config] = None
    ) -> List[Tuple[str, str]]:
        """Render all extension templates with the given renderable arguments.

        If template_directory is None then this will default to the default template directory in
        the cli_extensions/templates/{ext_name} folder.

        If render_args is None then the extension config is used to populate templates being rendered.
        Use render_args if you do not want to expose all of the extensions config variables when rendering.

        Returns:
        A list of tuples with the first element being the relative path of the file in relation to its template directory
        and the second element, the newly rendered text from the render_args/config.

        Relative path example, if the template is in "config_generator/vars/itsm_vars.template" then the return args would be

            [("vars/itsm_vars.template", {the rendered text of the template})]

        """
        if not template_directory:
            template_directory = self.template_location

        if not render_args:
            render_args = vars(self.config)

        ext_name = os.path.basename(template_directory)

        rendered_file_names_and_text = []
        for subdir, _, files in os.walk(template_directory):
            for f in tqdm(files, desc='Rendering Extension Templates via Jinja'):

                template_file_path = os.path.join(subdir, f).split(ext_name)[1]
                rendered_text = utils.render_template(
                    render_args, template_file_path, template_directory
                )

                rendered_file_names_and_text.append((template_file_path, rendered_text))

        return rendered_file_names_and_text

    def get_user_input_from_choices(
        self, choices: List[str], choice_descriptions: Dict[str, str], message: str
    ):
        """Recieve user selection from a displayed menu of choices."""
        if message:
            print(message)
        choice = None
        while not choice:
            self.display_choices(choices, choice_descriptions)
            choice = self.get_user_choice(choices)

        return choice

    def display_choices(self, choices: List[str], choice_descriptions: Dict[str, str] = None):
        for idx, choice in enumerate(choices):
            if choice_descriptions and choice in choice_descriptions:
                print(
                    f'{idx+1}. {utils.CLIColors.build_value_string(choice)} {utils.CLIColors.build_info_string(choice_descriptions[choice])}'
                )
            else:
                print(f'{idx+1}. {utils.CLIColors.build_value_string(choice)}')

    def get_user_choice(self, choices: List[str]):
        choice = input(f'Please select your choice [1-{len(choices)}]:')

        try:
            index = int(choice) - 1
            return choices[index]
        except ValueError:
            print(
                f'Value supplied, {utils.CLIColors.build_value_string(choice)}, is not an integer, try again.'
            )
        except IndexError:
            print(
                f'Value supplied, {utils.CLIColors.build_value_string(choice)}, is not a selection, try again.'
            )

    def get_extension_template_directory(self) -> str:
        """Retrieve the extension's template directory.

        Extension template directories are created with the name of extension as the template folder.
        """
        return os.path.join(
            pathlib.Path(inspect.getfile(inspect.getmodule(self.handle))).parent.parent.resolve(),
            self.name,
            'templates',
        )

    # Application Lifecycle hook
    def ready(self):
        """Lifecycle hook, this is mainly used to gather inputs from the user to be rendered in templates and etc using {{}} and jinja."""
        ...

    # Application Lifecycle hook
    def start(self):
        """Lifecycle hook, this is used in place of main or in conjunction."""
        ...

    def render_config_args(self):
        """Calls on the config to render {{}} in jinja using the key/values found in config itself."""
        setattr(self, 'config', render_config_args(self.config))
