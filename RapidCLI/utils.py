import csv
import inspect
import json
import os
import pathlib
import re
import string
import subprocess
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Sequence

import git
import pandas as pd
import yaml
from colorama import Back, Fore
from google.protobuf.descriptor import Descriptor
from jinja2 import BaseLoader, Environment, FileSystemLoader

import rapidcli.settings as settings

cache = {}


def find_files_by_extension_in_directory(path, file_extension):
    files = []
    for r, _, f in os.walk(path):
        for file in f:
            if str(file).endswith(file_extension):
                files.append(os.path.join(r, file))
    return files


def get_erroring_attr(attr_error: AttributeError):
    """Get the attribute name that caused the error."""
    message = attr_error.args[0]
    _, error_attr_name = parse_attr_error_message(message)
    return error_attr_name


def parse_attr_error_message(attr_err_msg: str):
    """Parse and return the attribute that errored and the message of the erroe."""
    parsed_msg = re.findall("'([^']*)'", attr_err_msg)
    return parsed_msg


def run_subprocess_from_root(*args):
    """This temporarily changes the working directory to the root of the repo when runing a subpocess command."""
    current_working_dir = os.getcwd()

    # Temporarily change the dir to the repo where this file lives
    os.chdir(get_repo_root())
    subprocess.run(args)

    # Change back to the working directory we were just at.
    os.chdir(current_working_dir)


def debug_print(msg):
    cal_name = inspect.stack()[1][3]
    print(
        "\n".join(
            [f"Called from function {CLIColors.build_value_string(cal_name)}", str(msg)]
        )
    )


def get_cli_path(cli: type):
    return pathlib.Path(inspect.getfile(cli)).resolve()


def get_cli_parent_path(cli: type):
    return str(pathlib.Path(inspect.getfile(cli)).parent.resolve())


def get_absolute_file_paths(directory):
    """Gets the absolute file paths of all files in a directory."""
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def write_content(content: Any, dest_path: str, export_data_type: str = None):
    """Creates the directory of the last directory in filepath."""
    saved = False
    if not settings.settings["debug"]:
        dir_name = os.path.dirname(dest_path)
        if dir_name:
            safe_mkdir(dir_name)
        if isinstance(content, bytes):
            with open(dest_path, "wb") as fout:
                fout.write(content)
                saved = True
        elif isinstance(content, str):
            with open(dest_path, "w") as fout:
                fout.write(content)
                saved = True

        elif isinstance(content, pd.DataFrame):
            if export_data_type == "json":
                content.to_json(dest_path, index=False)
                saved = True
            elif export_data_type == "csv":
                content.to_csv(dest_path, index=False, quoting=csv.QUOTE_MINIMAL)
                saved = True
            elif export_data_type == "xlsx":
                content.to_excel(dest_path, index=False)
                saved = True

        elif isinstance(content, dict):
            with open(dest_path, "w") as file:
                json.dump(content, file, indent=2)
                saved = True

        elif isinstance(content, list):
            with open(dest_path, "w") as file:
                json.dump(content, file, indent=2)
                saved = True

    if saved:
        print_save_statement(dest_path)


def load_yaml(filepath, encoding="utf-8"):
    """Loads a yml file."""
    with open(filepath, encoding=encoding) as f:
        return yaml.safe_load(f)


def safe_mkdir(path):
    """Super-mkdir; create a leaf directory and all intermediate ones.

    Works like mkdir, except that any intermediate path segment (not just the rightmost) will be created if it does not exist.
    If the target directory already exists, raise an OSError if exist_ok is False.
    Otherwise no exception is raised. This is recursive.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        if not os.path.isdir(path):
            raise


def read_file(path: str):
    with open(path, "r") as file:
        return file.read()


def save_file(data: Any, path: str):
    with open(path, "w") as file:
        file.write(data)


def save_json_data(data: dict, path: str):
    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def get_repo_root():
    """Gets the root of the repo by changing working directory."""
    cache_key = "get_repo_root"

    if cache.get(cache_key):
        return cache[cache_key]

    current_working_dir = os.getcwd()

    # Temporarily change the dir to the repo where this file lives
    os.chdir(pathlib.Path(__file__).parent.resolve())
    with subprocess.Popen(
        ["git", "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    ) as process:
        repo_root = process.stdout.read().decode("UTF-8").replace("\n", "")
        process.kill()
    # Change back to the working directory we were just at.
    os.chdir(current_working_dir)
    cache["get_repo_root"] = repo_root

    return repo_root


def get_local_login_username():
    """Gets the currently logged in username."""
    with subprocess.Popen(
        ["whoami"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    ) as process:
        user_name = process.stdout.read().decode("UTF-8").replace("\n", "")
        process.kill()
        return user_name


def change_to_snake_case(s: str):
    """Converts any casing to snake case, except uppercase will just be lowered."""
    if is_snake_case(s):
        return s

    # It is all caps, can't determine difference in words
    if s.isupper():
        return s.lower()

    res = [s[0].lower()]
    for c in s[1:]:
        if c in string.ascii_uppercase:
            res.append("_")
            res.append(c.lower())
        else:
            res.append(c)

    return "".join(res)


def is_snake_case(s: str):
    """Checks if the given string is snake case."""
    if any(c in ["-"] for c in s):
        return False
    for c in s:
        if c.lower() != c:
            return False
    return True


def select_choice_from_proto(
    proto_descriptor_values,
    selection_message: str = None,
    vals_to_remove: Iterable[str] = None,
    vals_to_include: Iterable[str] = None,
):
    """Creates a selection menu out of a proto's descripter values.

    proto_descripter_values: The values given from the proto descriptor
    selection_message: The display message for the menu.
    vals_to_remove: A list of values to not be made available
    vals_to_include: Additional values to display not found on the proto
    """
    choices = get_enums_from_proto(proto_descriptor_values, vals_to_remove)
    if vals_to_include:
        choices.extend([(value, value) for value in vals_to_include])

    input_data = None
    while input_data is None:
        if selection_message:
            print(CLIColors.build_info_string(selection_message))
        for (i, item) in enumerate(choices):
            print(i + 1, CLIColors.build_value_string(item[0]))
        input_data = input(f"Select [1-{len(choices)}]: ")  # nosec
        try:
            input_data = choices[int(input_data) - 1][0]
        except IndexError:
            print_incorrect_selection_statement(input_data)
            input_data = None  # reset
        except ValueError:
            print_incorrect_selection_statement(input_data)
            input_data = None  # reset

    return input_data


def print_incorrect_selection_statement(selection: str):
    start_error_message = CLIColors.build_error_string(f"Incorrect Selection Made: ")
    colored_value = CLIColors.build_value_string(f"{selection}")
    print(CLIColors.build_error_string(f"{start_error_message}{colored_value}"))


def get_enums_from_proto(
    enum_descriptor_sequence: Sequence[Descriptor], vals_to_remove: Iterable[str] = None
) -> List[tuple]:
    """This function extracts enum names from Sequence of Proto Descriptors.

    Args:
        enum_descriptor_sequence: Sequence of proto Descriptors
        vals_to_remove: List of values to be removed from choice selection

    Returns:
        List of tuples [(proto_enum, friendly_name)] without data in vals_to_remove
    """
    if not vals_to_remove:
        return [
            (enum.name, enum.name.replace("_", " ").lower())
            for enum in enum_descriptor_sequence
        ]

    return [
        (enum.name, enum.name.replace("_", " ").lower())
        for enum in enum_descriptor_sequence
        if enum.name not in vals_to_remove
    ]


def iterate_down_to(data: Dict, *args, **kwargs):
    """Walk a dict object and return the value if key is found, else None.

    This is meant to be used like iterate_down_to(some_dict, "key1", "subkey2") and return
    None if one of the keys doesn't exist or the value of the last given key.

    If the key you are looking for is in a list and has nested dictionaries, if the key
    is found in the nested dictionary then it will retrieve all of the values in the list
    for each nested dictionary.
    """
    data_found = []

    def find_recursively(data):
        if isinstance(data, dict):
            for field, value in data.items():
                if field in args:
                    find_recursively(value)
                    if field == args[-1]:
                        appended_item = value
                        var_to_key = kwargs.get("var_to_key")
                        if var_to_key and var_to_key in data:
                            appended_item = {data[var_to_key]: value}
                        data_found.append(appended_item)

        if isinstance(data, list):
            for value in data:
                find_recursively(value)

    find_recursively(data)

    if len(data_found) == 1:
        return data_found[0]

    return data_found or None


def get_last_commit_of_file(file_path):
    """Retrieve the last commit of a file that was not made by the logged in user."""
    repo = git.Repo(get_repo_root(), odbt=git.GitCmdObjectDB)
    for commit in repo.iter_commits(paths=file_path, max_count=20):
        if get_local_login_username() not in repo.git.show("-s", commit.hexsha):
            return commit


def git_restore_file(filepath: str, source=None):
    """Restores the file to the last commit given as the source to return to."""
    commands = ["git", "restore"]
    if source:
        commands.extend([f"--source={source}", filepath])
    else:
        commands.append(filepath)

    with subprocess.Popen(
        commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    ) as process:
        process.communicate()
        process.kill()


def get_export_path(ext_name, *args, create_dir_if_not_found: bool = True):
    """This is a convenient method that creates all directories and sub directories and returns an absolute path.

    This method is used like get_export_path("get_merged_users", "another_dir", "some_file.txt").
    This creates the base exports folder "~/Desktop/exports", then "get_merged_users", "another_dir"
    and then finally stops creating directories and returns the absolute path to the new files location.

    It will not create "some_file.txt", the last variable is assumed to be the thing to save
    data to.
    """
    path = os.path.join(os.path.expanduser("~/Desktop/exports"), ext_name, *args)
    if create_dir_if_not_found:
        create_export_path(path)
    return path


def create_export_path(export_path: str):
    """Creates the the directories up to the last seen directory in the given path."""
    export_dir = os.path.dirname(export_path)
    colored_location = CLIColors.build_location_string(export_dir)
    if not os.path.isdir(export_path) and not os.path.exists(export_dir):
        safe_mkdir(export_dir + "/")
        colored_info_string = CLIColors.build_info_string("Created export directory")
        print(f"{colored_info_string}: {colored_location}")


def print_save_statement(saved_file_path: str, unfollowable=False):
    """Prints the standard CSE CLI saving statme with the location color."""
    save_msg = "Saving Complete. Location:"
    if unfollowable:
        save_msg = "Saving Complete. Unfollowable location:"

    print(
        CLIColors.build_info_string(
            f"{save_msg} {CLIColors.build_location_string(saved_file_path, unfollowable)}"
        )
    )


# TODO(bgarrard): Move this to the extension class
def render_template(
    render_args: dict, template_path: str, extension_root_template_dir: str
):
    """Retrieve the rendered Jinja template using the given render arguments."""
    templateLoader = FileSystemLoader(extension_root_template_dir)
    env = Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)

    for filter_key, jinja_filter in _get_filters().items():
        env.filters[filter_key] = jinja_filter

    template = env.get_template(template_path)
    return f"{template.render(**render_args)}\n"


def render_string(string_to_render: str, render_args: Dict):
    template = Environment(loader=BaseLoader()).from_string(string_to_render)
    return template.render(**render_args, trim_blocks=True, lstrip_blocks=True)


# TODO(bgarrard): Move this to the extension class
def _get_filters() -> Dict[str, Callable]:
    return {dict_to_yaml.__name__: dict_to_yaml}


# TODO(bgarrard): Move this to the extension class
def dict_to_yaml(data_dict: Dict):
    noalias_dumper = yaml.dumper.SafeDumper
    noalias_dumper.ignore_aliases = lambda self, data: True
    return yaml.dump(data_dict, default_flow_style=False, Dumper=noalias_dumper)


def get_path_from_repo_root(*args):
    """Convenience function that retrieves the repos root and builds the path from there.

    Usage:
        get_path_from_repo_root("first_dir", "second_dir")

        This produces "{repo_root}/first_dir/second_dir"
    """
    return os.path.join(os.sep, *get_repo_root().split("/"), *args)


def backup_file(file_path):
    """This will back the given file in your /tmp folder."""
    if os.path.exists(file_path):
        file_name = os.path.basename(file_path)
        new_file_name = f"{os.path.splitext(file_name)[0]}.bak"
        temp_path = os.path.join(
            os.sep, "tmp", f"{get_todays_date_string()}_{new_file_name}"
        )
        info_message = CLIColors.build_info_string(f"Backing up file:")
        colored_file_path = CLIColors.build_location_string(file_path)
        colored_temp_path = CLIColors.build_location_string(temp_path)
        colored_message = f"{info_message} {colored_file_path} to {colored_temp_path}"
        print(colored_message)

        os.rename(file_path, temp_path)


def provide_argument_help_string(given_arg: str, valid_args: List[str]) -> str:
    colored_value = CLIColors.build_value_string(given_arg)
    colored_valid_args = [CLIColors.build_value_string(arg) for arg in valid_args]
    messsage_builder = [
        CLIColors.build_error_string(
            f"The provided value is not valid: {colored_value}"
        )
    ]
    messsage_builder.append(
        CLIColors.build_info_string("A list of valid arguements is below")
    )
    messsage_builder.append("\n".join(colored_valid_args))
    return "\n".join(messsage_builder)


def get_todays_date_string():
    return datetime.today().strftime("%Y-%m-%d")


def transform_dict_list_to_dataframe(
    data_list: List[Dict], transform_map: Dict[str, List]
):
    """This is a function that helps transforms nested dicts in to a dataframe more easily.

    Give a list of dictionaries that are of the same structure, we can define a map to retrieve
    the value for any given column we want in our DataFrame output.

    If I have a map
    map = {
        "yolo": ["key1", "key2"]

    }

    Then the dictionary objects in the list have a structure of
    data = {
        "key1: {
            "key2" : "the_value_we_want"
        }
    }

    Which then makes the output of this as a table with.
    |       yolo      |
    |-----------------|
    |the_value_we_want|
    """
    df_dict = {k: [] for k, _ in transform_map.items()}
    for column, dict_walk_list in transform_map.items():
        for data_dict in data_list:
            value = iterate_down_to(data_dict, *dict_walk_list)
            df_dict[column].append(value)

    return pd.DataFrame.from_dict(df_dict)


def is_plural(string: str):
    """Check if a string is plural or not."""
    if string[-3:] == "ies":
        return True
    return string[-1] == "s"


def make_singular(string: str):
    """Returns a non plural version of given string."""
    if string[-3:] == "ies":
        return f"{string[:-3]}y"
    elif string[-2:] == "es" and string[-4:-2] == "ch":
        return f"{string[:-2]}"
    return string[:-1]


class CLIColors:
    """These are colors for the CLI framework itself."""

    INFO = "info"
    ERROR = "error"
    LOCATION = "location"
    VALUE = "value"
    NEUTRAL = "neutral"
    DOCSTRING = "doc"

    @staticmethod
    def sanitize(string: str, color: str):
        if not string:
            return ""
        else:
            return str(string).replace(Fore.RESET, color)

    @staticmethod
    def build_info_string(string: str):
        string = CLIColors.sanitize(string, Fore.GREEN)
        return f"{Fore.GREEN}{string}{Fore.RESET}"

    @staticmethod
    def build_error_string(string: str):
        string = CLIColors.sanitize(string, Fore.RED)
        return f"{Fore.RED}{string}{Fore.RESET}"

    @staticmethod
    def build_location_string(string: str, unfollowable: bool = False):
        if unfollowable:
            return CLIColors._build_unfollowable_location_string(string)

        string = CLIColors.sanitize(string, Fore.YELLOW)
        return f"{Fore.YELLOW}{string}{Fore.RESET}"

    @staticmethod
    def build_value_string(string: str):
        string = CLIColors.sanitize(string, Fore.CYAN)
        return f"{Fore.CYAN}{string}{Fore.RESET}"

    @staticmethod
    def build_neutral_string(string: str):
        string = CLIColors.sanitize(string, Fore.LIGHTGREEN_EX)
        return f"{Fore.LIGHTGREEN_EX}{string}{Fore.RESET}"

    @staticmethod
    def build_doc_string(string: str):
        string = CLIColors.sanitize(string, Fore.MAGENTA)
        return f"{Fore.MAGENTA}{string}{Fore.RESET}"

    @classmethod
    def color_strings(cls, text_type: str, *args):
        return list(map(getattr(cls, f"build_{text_type}_string"), args))

    @staticmethod
    def _build_unfollowable_location_string(string: str):
        string = CLIColors.sanitize(string, Fore.LIGHTYELLOW_EX)
        string = f"{Fore.LIGHTYELLOW_EX}{string}{Fore.RESET}"
        string = f"{Back.BLACK}{string}{Back.RESET}"
        return string
