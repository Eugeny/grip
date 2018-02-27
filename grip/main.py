import os
import click
import sys
import grip.ui as ui
from .app import App
from .cli import AliasedGroup
from .model import PackageGraph, Package, Dependency
from .requirements import TxtRequirements

app = App()
CONTEXT_SETTINGS = { 'help_option_names': ['-h', '--help'] }
ALIASES = {
    'ls': 'list',
    'remove': 'uninstall',
}

@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS, aliases=ALIASES)
@click.option('--global', '-g', 'glob', is_flag=True, default=False, help='Act on the global site, not the local virtualenv')
@click.option('--cwd', '-d', default=None, help='Working directory')
@click.option('--interactive/--noninteractive', '-i/-n', default=lambda: os.isatty(0), help='Allow user interaction')
@click.option('--requirements', '-r', 'requirements_path', default=None, help='Requirements file')
def cli(glob=False, cwd=None, interactive=False, requirements_path=None):
    if requirements_path:
        requirements_path = os.path.abspath(requirements_path)

    if cwd:
        os.chdir(cwd)
        ui.debug('Working in', os.getcwd())

    app.interactive = interactive

    '''
    if glob:
        if app.virtualenv:
            ui.error('Cannot act on the global site when running inside a virtualenv shell.')
            ui.error('Run `deactivate` first.')
            sys.exit(1)
    '''

    if requirements_path:
        if not os.path.exists(requirements_path):
            ui.error(requirements_path, 'does not exist')
            sys.exit(1)

        requirements = TxtRequirements(requirements_path)
    else:
        requirements = app.locate_requirements()

    if requirements:
        app.set_requirements(requirements)
        ui.debug('Requirements file:', app.requirements)


@cli.command('init', help='Set up a new project')
def cmd_init():
    '''
    Sets up a new PyPI project in the current folder
    '''
    app.ensure_virtualenv()
    app.perform_init()


@cli.command('run', help='Run a virtualenv binary')
@click.argument('command', metavar='<command>')
@click.argument('args', metavar='<args>', nargs=-1)
def cmd_run(command=None, args=[]):
    '''
    Runs a binary provided by one of the installed packages
    '''
    app.perform_run(command, args)



@cli.command('check', help='Check consistency')
def cmd_check():
    '''
    Checks all dependencies for consistency and looks for extraneous packages
    '''
    app.ensure_virtualenv()
    app.perform_check()


@cli.command('prune', help='Remove extraneous packages')
def cmd_prune():
    '''
    Removes packages not required by anything
    '''
    app.ensure_virtualenv()
    app.perform_prune()
    app.perform_check(silent=True)


@cli.command('freeze', help='List all packages')
def cmd_freeze():
    '''
    Lists every installed package and its version
    '''
    app.ensure_virtualenv()
    app.perform_freeze()


@cli.command('install', help='Install dependencies')
@click.argument('packages', metavar='<dependencies>', nargs=-1)
@click.option('--save', '-S', is_flag=True, help='Add to the requirements file')
@click.option('--upgrade', '-U', is_flag=True, help='Upgrade already installed packages')
def cmd_install(packages=None, save=False, upgrade=False):
    '''
    Installs listed dependencies

    Specific dependencies:

      grip install django celery==4.0.0

     From the requirements.txt file:

      grip install

     From a different file:

      grip -r reqs-test.txt install
    '''
    app.ensure_virtualenv()
    if len(packages):
        parent = Package(PackageGraph.USER_PKG, None)
        app.perform_install([Dependency(spec, parent=parent) for spec in packages], save=save, upgrade=upgrade)
    elif app.requirements:
        app.perform_install_requirements()
    else:
        ui.error('No packages specified and no requirements file found')
        sys.exit(1)
    app.perform_check(silent=True)


@cli.command('download', help='Download dependency packages')
@click.option('--source', is_flag=True, help='Download source package only')
@click.argument('dependencies', metavar='<dependencies>', nargs=-1)
def cmd_download(dependencies=None, source=False):
    '''
    Downloads packages from PyPI into the current directory

    Example:

     grip download django==2.0
    '''
    app.perform_download([Dependency(x) for x in dependencies], source=source)



@cli.command('uninstall', help='Remove packages')
@click.argument('packages', metavar='<package names>', nargs=-1)
def cmd_uninstall(packages=None):
    '''
    Removes listed packages (alias: remove)

    Example:

     grip uninstall django
    '''
    app.ensure_virtualenv()
    app.perform_uninstall(packages)
    app.perform_check(silent=True)


@cli.command('list', help='List installed packages')
def cmd_list():
    '''
    Lists installed packages and their dependencies
    '''
    app.ensure_virtualenv()
    app.perform_list()
    app.perform_check(silent=True)


@cli.command('outdated', help='Check for updates')
def cmd_outdated():
    '''
    Checks for the newest versions of the installed packages
    '''
    app.ensure_virtualenv()
    app.perform_outdated()


@cli.command('why', help='Figure out the dependency chain')
@click.argument('package', metavar='<package>')
def cmd_why(package=None):
    '''
    Figures out why a package was installed and what depends on it

    Example:

     grip why six
    '''
    app.ensure_virtualenv()
    app.perform_why(package)
