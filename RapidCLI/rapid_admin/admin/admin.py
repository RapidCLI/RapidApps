from rapidcli.extension_registrar import register_extension
from rapidcli.extension import Extension
import shutil
import os


@register_extension()
class RapidAdmin(Extension):
    def start(self):
        self.show_input_menu("main_menu")
        print(self.config.what_to_create)
        if self.config.what_to_create == "cli":
            self.show_input_menu("cli_menu")
            self.create_cli(self.config.project_destination, self.config.project_name)

    def create_cli(self, project_dir: str = "", project_name: str = ""):
        """Given the project path, create a cli project at the project path."""
        new_cli_project_path = os.path.join(os.sep, project_dir, project_name)
        shutil.copytree(
            self.get_rendered_extension_templates("rapidcli"), destination_dir
        )
