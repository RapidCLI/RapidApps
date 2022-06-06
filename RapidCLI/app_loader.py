import importlib
import inspect
import json
import os
import traceback
from typing import Any, Dict

import rapidcli.settings as settings
from rapidcli.config_registrar import (
    CLIConfig,
    Config,
    config_registry,
)
from rapidcli.utils import (
    CLIColors,
    get_cli_parent_path,
    is_plural,
    load_yaml,
    make_singular,
    render_string,
    write_content,
)
from rapidcli.rapid_admin import (
    rapid_admin,
)  # lets just import the admin CLI for now.  We can update it later.


def load_framework_cli(cli: type):
    cli_config_data = retrieve_cli_config_data(cli)
    admin_cli_path = get_cli_parent_path(cli)
    admin_project_path = ["rapidcli"] + [
        path for path in admin_cli_path.split("rapidcli")[1].split(os.sep) if path
    ]
    for app in cli_config_data["apps"]:
        app_path = os.path.join(admin_cli_path, app)
        modules = get_app_modules(app_path)
        for module in modules:
            pyless_module = module.split(".")[0]
            importlib.import_module(".".join(admin_project_path + [app, pyless_module]))


def load_cli_settings(cli: type):
    """Loads the settings for the given CLI."""
    mod = inspect.getmodule(cli)
    mod.settings = retrieve_cli_config_data(cli)
    settings.settings.update(mod.settings)


def load_apps_in_cli(cli: type):
    """Load the apps for a given CLI."""
    if cli == rapid_admin.RapidAdmin:
        load_framework_cli(cli)
        return

    cli_config_data = retrieve_cli_config_data(cli)
    _load_apps(cli_config_data, get_cli_parent_path(cli))


def load_apps_from_file(cli_config_path: str, apps_directory: str):
    cli_config_data = load_yaml(cli_config_path)
    _load_apps(cli_config_data, apps_directory)


def _load_modules(app, app_py_files):
    for app_py_file in app_py_files:
        try:
            importlib.import_module(f"{app}.{app_py_file.split('.')[0]}")
        except ModuleNotFoundError:
            # If in the same directory as the app when executing just import the file
            importlib.import_module(app_py_file.split(".")[0])


def _load_apps(cli_config_data: Dict, apps_dir: str):
    for app in cli_config_data["apps"]:
        app_path = os.path.join(apps_dir, app)
        _load_modules(app, get_app_modules(app_path))


def compile_app_configs_into_cli_config_from_data(cli_data: Dict, apps_dir: str):
    """Compile app configs in to main CLI config given the CLI."""
    return _compile_configs(apps_dir, cli_data["apps"])


def _compile_configs(apps_dir: str, app_list):
    compiled_config_data = {}
    for app in app_list:
        config_path = os.path.join(apps_dir, app, "app_config.yml")
        if not os.path.exists(config_path):
            continue
        data = load_yaml(config_path)
        if data:
            compiled_config_data.update(data)

    return compiled_config_data


def create_cli_config_from_cli(cli: type):
    load_cli_settings(cli)
    load_apps_in_cli(cli)
    cli_data = retrieve_cli_config_data(cli)
    # Always just recreate the tool config to enable allow for config updates
    return create_cli_config_from_cli_from_data(cli_data, get_cli_parent_path(cli))


def create_cli_config_from_cli_from_data(cli_config_yaml_data: Dict, apps_dir: str):
    """Build the CLIConfig object by instantiating all dicts in the cli_config.yml as config objects."""
    cli_data = compile_app_configs_into_cli_config_from_data(
        cli_config_yaml_data, apps_dir
    )
    cli_config: CLIConfig = config_registry["root"]()

    return instantiate_configs_in_dict(cli_data, cli_config)


def get_app_config(app_dir: str):
    return [file for file in os.listdir(app_dir) if file == "app_config.yml"]


def get_app_modules(app_dir: str):
    try:
        return [file for file in os.listdir(app_dir) if file.endswith(".py")]
    except FileNotFoundError:
        traceback.print_exc()
        app_value = CLIColors.build_value_string(os.path.basename(app_dir))
        error_msg = CLIColors.build_error_string(f"The app {app_value} was not found.")
        print(error_msg)


# TODO(bgarrard): redefine/replace the whole model instantiation process
def instantiate_configs_in_dict(config_dict: Dict, config_to_set: Config = None):
    def recursively_set_attrs(instance, attr: str, vals: Any):
        """Create basic configs and expose attributes for use.  Create a linked list of Config objects."""
        if isinstance(vals, dict):
            config_name = f"{attr}{Config.CONFIG_SUFFIX}"
            new_config = (
                config_registry[config_name]()
                if config_name in config_registry
                else Config()
            )

            for att, val in vals.items():
                recursively_set_attrs(new_config, att, val)

            instance.add_var(attr, new_config)
        elif isinstance(vals, list):
            new_configs = []
            # If the naming of the attribute is plural, we assume that the name
            # of the objects in the list are the singular versions.
            # We only want to create python objects with key/value pair types.
            # So checking the first element if it can be an object is necessary
            if is_plural(attr) and hasattr(vals[0], "items"):
                config_name = f"{make_singular(attr)}{Config.CONFIG_SUFFIX}"
                config_definition = config_registry.get(config_name)
                for item in vals:
                    new_config = config_definition() if config_definition else Config()
                    if hasattr(item, "items"):
                        for n_attr, n_value in item.items():
                            recursively_set_attrs(new_config, n_attr, n_value)
                    new_configs.append(new_config)

            instance.add_var(attr, new_configs or vals)
        else:
            instance.add_var(attr, vals)

    if not config_to_set:
        config_to_set = Config()

    # Transferring the data from the yaml file to an in memory object.  The config field of
    # the object should match the field of the cli_config.yml
    for ext_name, ext_values in config_dict.items():
        # Configs have the suffix in their class definition, but I want the name of the extension more easily accessible.
        config_name = f"{ext_name}{Config.CONFIG_SUFFIX}"
        # specific tool configs are only one level below the root tool config
        config_instance = (
            config_registry[config_name]()
            if config_name in config_registry
            else Config()
        )
        val_to_set = config_instance
        if ext_values is not None:
            if isinstance(ext_values, dict):
                for ext_attr, ext_params in ext_values.items():
                    recursively_set_attrs(config_instance, ext_attr, ext_params)
            elif isinstance(ext_values, list):
                new_configs = []
                for item in ext_values:
                    config_name = f"{make_singular(ext_name)}{Config.CONFIG_SUFFIX}"
                    config_definition = config_registry.get(config_name)
                    new_config = config_definition() if config_definition else Config()
                    if hasattr(item, "items"):
                        for n_attr, n_value in item.items():
                            recursively_set_attrs(new_config, n_attr, n_value)
                    new_configs.append(new_config)
                    val_to_set = new_configs
        config_to_set.add_var(ext_name, val_to_set)

    return config_to_set


def get_cli_config_path(cli: type):
    """Retrieve the cli_config.yml path near the cse_cli.py."""
    cli_config_path = os.path.join(get_cli_parent_path(cli), "cli_config.yml")

    # DESIGN CHOICE: The CLI must have a cli_config.yml
    if not os.path.exists(cli_config_path):
        write_content("", cli_config_path)
    return cli_config_path


def retrieve_cli_config_data(cli: type):
    return load_yaml(get_cli_config_path(cli))


def render_config_args(config_obj: Config):
    render_args = convert_to_dict(config_obj)
    new_dict = json.loads(render_string(json.dumps(render_args), render_args))
    rendered_config = instantiate_configs_in_dict(new_dict, Config())
    for already_set_field, already_set_value in config_obj.items():
        # TODO(bgarrard): This is absolutely terrible.  Need to find a better way to not overwrite already set fields
        if (
            isinstance(already_set_value, str)
            and not isinstance(already_set_value, Config)
            and not isinstance(already_set_value, list)
        ):
            rendered_config.set_var(already_set_field, already_set_value)
    return rendered_config


def convert_to_dict(obj: Any) -> Dict:
    """Convert all python objects, even nested ones, into dicts."""
    if not hasattr(obj, "__dict__"):
        return obj
    result = {}
    for key, val in obj.__dict__.items():
        if key.startswith("_"):
            continue
        element = []
        if isinstance(val, list):
            for item in val:
                element.append(convert_to_dict(item))
        else:
            element = convert_to_dict(val)
        result[key] = element
    return result
