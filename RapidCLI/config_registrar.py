"""This file is responsible for creating the config registry and validating the cli config.

The current root config is CLIConfig and it's schema is cli_config_schema.yml and the configuration
data for the python class CLIConfig is found in cli_config.yml.

The schema is used for validation purposes, it defines what is allowed to be CLIConfig data.
cli_config.yml is where the data lives.

The structure of the config is

CLIConfig
    - orgs
    - environments
    - {extension_name}
        - {extension_keys/values}

A extension is essentially a plugin that you are creating.  When you create a extension it gets registered to be used
by the CLI automatically.  This is meant to feel like 'Magic'.  Configs work the same way.

Configs are tightly coupled with Class based extensions.  Class based extensions can live without a config
but a config can not live without a class based extension besides CLIConfig.  That config is not for an extension
it is for the CLI.
"""
import functools
import sys
import traceback
from difflib import get_close_matches
from typing import Any, Callable, Dict, List, Union

from rapidcli.utils import (
    CLIColors,
    change_to_snake_case,
    get_erroring_attr,
    get_path_from_repo_root,
    iterate_down_to,
)
from yaml import safe_load

CONFIG_MODEL_SUFFIX = '_config'


config_registry = {}


def register_config(cls=None, root=False):
    functools.wraps(cls)

    def wrapper(cls):
        if root:
            config_registry['root'] = cls
        else:
            config_registry[cls.get_name()] = cls
        return cls

    return wrapper


class Config:
    CONFIG_SUFFIX = '_config'

    def __getattribute__(self, name) -> Any:
        closest_match = ''

        try:
            return super().__getattribute__(name)
        except AttributeError as ae:
            # chance to handle the attribute differently
            attr = get_erroring_attr(ae)
            try:
                closest_match = next(
                    match for match in get_close_matches(attr, vars(self).keys(), cutoff=0)
                )
            except StopIteration:
                print(
                    CLIColors.build_error_string(
                        'Looks like the CLIconfig has no attributes.  Probably improperly loaded.'
                    )
                )
                raise ae

            if closest_match:  # probably will have some threshold based on 'edit distance'
                ae.args = (
                    CLIColors.build_error_string(
                        f'You tried to access {CLIColors.build_value_string(attr)}. Did you mean {CLIColors.build_value_string(closest_match)}?'
                    ),
                )
                raise
            # if not, re-raise the exception
            raise

    def __getitem__(self, key: Union[List, Any]) -> Any:
        if isinstance(key, List):
            return iterate_down_to(vars(self), *key)

        return self.get_var(key)

    def __setitem__(self, key, value):
        self.set_var(key, value)

    def __str__(self) -> str:
        return self.__class__.__name__

    def __contains__(self, element) -> bool:
        return vars(self).get(element) is not None

    def __iter__(self):
        return vars(self).items()

    @classmethod
    def get_name(cls):
        """Retrieve the name of the class in snake_case format."""
        return change_to_snake_case(cls.__name__)

    def get_input_menu(self):
        """Retrieve the input map to be used for the extension menu."""
        return self.input_menu

    def add_var(self, attr_name: str, attr_value: Any):
        """Set an attribute variable on the config."""
        setattr(self, attr_name, attr_value)
        return self

    def set_var(self, attr_name: str, attr_value: Any):
        """Set an attribute variable on the config."""
        setattr(self, attr_name, attr_value)
        return self

    def get_var(self, attr_name: str):
        """Retrieve the value of the given attribute name."""
        return getattr(self, attr_name)

    def items(self):
        """Return the items iterator of the dictionary version of this config."""
        return self.__iter__()

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()


@register_config()
class ConfirmationMenuConfig(Config):
    def __init__(self):
        self.attrs: List[str] = None


@register_config()
class InputMenuConfig(Config):
    def __init__(self):
        ...


@register_config()
class SearchConfig(Config):
    def __init__(self):
        self.value_name: str = None
        self.source_file: str = None
        self.variable_path: str = None
        self.method: str = None
        self.is_resolved: bool = False
        self._value: Any = None
        self.data_loader: str = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.is_resolved = True
        self._value = value


@register_config(root=True)
class CLIConfig(Config):
    def get_extension_config(self, ext_name: str) -> Config:
        """Retreive this extensions config from the corresponding section in cli_config.yml."""
        # This is for when the config name is given fully
        config = vars(self).get(f'{ext_name}')
        if config:
            return config

        return Config()


# TODO(bgarrard): Move out of config_registrar in to a new file
# TODO(bgarrard): Break out loaders from the resolver in to a new class
class SearchResolver:
    def __init__(self) -> None:
        self.extraction_methods = self.get_base_extraction_methods()
        self.data_loaders = self.get_base_data_loaders()
        self.data_cache: Dict = {}

    def load_data_to_search(self, search_config: SearchConfig) -> Dict:
        try:
            if search_config.source_file in self.data_cache:
                return self.data_cache[search_config.source_file]
            data = self.data_loaders[search_config.data_loader](search_config.source_file)
            self.data_cache[search_config.source_file] = data
            return data
        except KeyError:
            traceback.print_exc()
            value_string = CLIColors.build_value_string(f'{search_config.data_loader}')
            error_string = CLIColors.build_error_string(
                f'There is no data loader method found named: {value_string}'
            )
            available_values = CLIColors.build_value_string(
                f"{', '.join(self.data_loaders.keys())}"
            )
            info_string = CLIColors.build_info_string(
                f'The available values are: {available_values}'
            )
            print(error_string)
            print(info_string)
            sys.exit()
        except FileNotFoundError:
            value_string = CLIColors.build_value_string(search_config.source_file)
            msg = CLIColors.build_info_string(f"Couldn't find {value_string}, SKIPPING")
            print(msg)

    def resolve_value(self, search_config: SearchConfig) -> SearchConfig:
        """Extract the value of a single search config."""
        try:
            source_data = self.load_data_to_search(search_config)
            value = iterate_down_to(source_data, *search_config.variable_path.split('/'))
            search_config.value = self.extraction_methods[search_config.method](value)
            return search_config
        except KeyError:
            traceback.print_exc()
            if search_config.method not in self.extraction_methods:
                value_string = CLIColors.build_value_string(f'{search_config.method}')
                error_string = CLIColors.build_error_string(
                    f'Unable to extract data. Extraction method {value_string} does not exist'
                )
                available_values = CLIColors.build_value_string(
                    f"{', '.join(self.extraction_methods.keys())}"
                )
                info_string = CLIColors.build_info_string(
                    f'The available extraction methods are: {available_values}'
                )
                print(error_string)
                print(info_string)
                sys.exit()
            value_name = CLIColors.build_value_string(search_config.value_name)
            msg = CLIColors.build_info_string(
                f'Warning extraction of {value_name} failed, skipping to next search'
            )
            print(msg)

    def resolve_values(self, search_config_list: List[SearchConfig]) -> List[SearchConfig]:
        """Extract all values in list of search configs."""
        for search_config in search_config_list:
            search_config = self.resolve_value(search_config)
        return search_config_list

    def load_yaml_without_anchors(self, file_path) -> Dict:
        """Remove anchors in yaml string and read the yaml file data."""
        file_path = get_path_from_repo_root(*file_path.split('/'))
        with open(file_path, 'r') as file:
            text = []
            for line in file.readlines():
                if '<<' in line:
                    continue
                text.append(line)
            data = safe_load('\n'.join(text))
            return self.merge_env_aware_dict(data)

    def merge_env_aware_dict(self, data_dict):
        if 'env_aware' not in data_dict:
            return data_dict

        data_dict = data_dict['vars']
        if 'common' in data_dict:
            prod_data = data_dict['common']
            prod_data.update(data_dict['kprod'])
            return {'vars': prod_data}

    def add_extraction_methods(self, *callable_args, **kwargs):
        """Add methods that should be available to be used in a search config extraction."""
        if kwargs:
            self.extraction_methods.update(kwargs)

        if callable_args:
            self.extraction_methods.update({arg.__name__: arg for arg in callable_args})

    def add_data_loader_methods(self, *callable_args, **kwargs):
        """Add methods that should be available to be used to load the data to be extracted from."""
        if kwargs:
            self.data_loaders.update(kwargs)

        if callable_args:
            self.data_loaders.update({arg.__name__: arg for arg in callable_args})

    def get_base_data_loaders(self):
        return {self.load_yaml_without_anchors.__name__: self.load_yaml_without_anchors}

    def get_base_extraction_methods(self) -> Dict[str, Callable]:
        return {
            self.first_occurrence.__name__: self.first_occurrence,
            self.as_is.__name__: self.as_is,
        }

    def first_occurrence(self, data: list):
        """Retrieve the first element of the given data."""
        if isinstance(data, list):
            return data[0]
        return data

    def as_is(self, data: Any):
        """Returns the data as it was given, no changes made."""
        if data:
            return data
