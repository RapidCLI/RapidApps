"""Naming convention the cli_config.yml.

Naming conventions are enforced for certain data types.

Enforced Conventions
DataType:
    List: attributes must be named in a plural way

NonEnforced Conventions:
1. A preceding item in a List is treated like an object if it has "items"
   in its attributes.  Since the type definition doesn't exist in the List item,
   the framework uses the singular version of the attr that houses the list of
   items to instantiate objects.  So if you have a list of tables and 'tables'
   being the name of the attr, then if a config is registered as TableConfig,
   that will replace the list of attrs, with a list of 'TableConfig' objects.
"""


class NamingConventionException(Exception):
    """Raise when a value does not meet naming convention standards."""

    ...
