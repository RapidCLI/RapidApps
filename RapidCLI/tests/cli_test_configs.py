from typing import List

from rapidcli.config_registrar import (
    Config,
    InputMenuConfig,
    register_config,
)


@register_config()
class TestExtensionConfig(Config):
    def __init__(self):
        self.input_menu: InputMenuConfig = None


@register_config()
class NestedObjInExtensionConfig(Config):
    def __init__(self):
        self.tables: List[TableConfig] = None


@register_config()
class TableConfig(Config):
    def __init__(self):
        self.name: str = None
        self.methods: List[str] = None
        self.columns: List[str] = None
        self.nested_obj_in_list: NestedObjInListConfig = None


@register_config()
class NestedObjInListConfig(Config):
    def __init__(self):
        self.random_attr: str = None
