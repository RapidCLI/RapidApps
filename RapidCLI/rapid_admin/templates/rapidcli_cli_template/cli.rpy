from rapidcli.cli import CLI


class {{project_name| capitalize}}(CLI):
    """{{project_description}}"""
    ...

if __name__ == "__main__":
    cli = {{project_name | capitalize}}()
    cli.main(debug=True)