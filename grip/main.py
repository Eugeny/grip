import os
import click
import subprocess
import sys
import grip.ui as ui
from .app import App
from .cli import AliasedGroup
from .model import PackageGraph, Package, Dependency

app = App()
CONTEXT_SETTINGS = { 'help_option_names': ['-h', '--help'] }
ALIASES = {
    'remove': 'uninstall',
}

@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS, aliases=ALIASES)
@click.option('--global', '-g', 'glob', is_flag=True, default=False, help='Act on the global site, not the local virtualenv')
@click.option('--cwd', '-d', default=None, help='Working directory')
@click.option('--interactive/--noninteractive', '-i/-n', default=lambda: os.isatty(0), help='Allow user interaction')
@click.option('--requirements', '-r', default=None, help='Requirements file')
def cli(glob=False, cwd=None, interactive=False, requirements=None):
    if requirements:
        requirements = os.path.abspath(requirements)

    if cwd:
        os.chdir(cwd)
        ui.debug('Working in', os.getcwd())

    app.interactive = interactive

    if glob:
        if app.virtualenv:
            ui.error('Cannot act on the global site when running inside a virtualenv shell.')
            ui.error('Run `deactivate` first.')
            sys.exit(1)
    else:
        virtualenv = app.locate_virtualenv()
        if virtualenv:
            app.set_virtualenv(virtualenv)
        else:
            ui.warn('Could not find a local virtualenv.')
            if app.interactive:
                if ui.yn('Create one?'):
                    def validate_interpreter(name):
                        try:
                            subprocess.check_call([name, '-V'])
                        except:
                            raise Exception('Could not find %s' % name)

                    name = ui.prompt('Folder name', default='venv')
                    interpreter = ui.prompt('Interpreter', default='python3', validate=validate_interpreter)
                    path = os.path.join(os.getcwd(), name)
                    app.create_virtualenv(path, interpreter)
                    app.set_virtualenv(path)
                else:
                    ui.error('Aborting.')
                    sys.exit(1)
            else:
                ui.error('Aborting.')
                sys.exit(1)

    ui.debug('Operating on:', app.site_packages)

    if not requirements:
        requirements = app.locate_requirements()

    if requirements:
        if not os.path.exists(requirements):
            ui.error(requirements, 'does not exist')
            sys.exit(1)
        app.set_requirements(requirements)
        ui.debug('Requirements file:', app.requirements)


@cli.command('check', help='Check consistency')
def cmd_check():
    '''
    Checks all dependencies for consistency and looks for extraneous packages
    '''
    app.perform_check()


@cli.command('prune', help='Remove extraneous packages')
def cmd_prune():
    '''
    Removes packages not required by anything
    '''
    app.perform_prune()
    app.perform_check(silent=True)


@cli.command('freeze', help='List all packages')
def cmd_freeze():
    '''
    Lists every installed package and its version
    '''
    app.perform_freeze()


@cli.command('install', help='Install dependencies')
@click.argument('packages', metavar='<dependencies>', nargs=-1)
def cmd_install(packages=None):
    '''
    Installs listed dependencies

    Specific dependencies:

      grip install django celery==4.0.0

     From the requirements.txt file:

      grip install

     From a different file:

      grip -r reqs-test.txt install
    '''
    if len(packages):
        parent = Package(PackageGraph.USER_PKG, None)
        app.perform_install([Dependency(spec, parent=parent) for spec in packages])
    elif app.requirements:
        app.perform_install_requirements()
    else:
        ui.error('No packages specified and no requirements file found')
        sys.exit(1)
    app.perform_check(silent=True)


@cli.command('uninstall', help='Remove packages')
@click.argument('packages', metavar='<package names>', nargs=-1)
def cmd_uninstall(packages=None):
    '''
    Removes listed packages (alias: remove)

    Example:

     grip uninstall django
    '''
    app.perform_uninstall(packages)
    app.perform_check(silent=True)


@cli.command('list', help='List installed packages')
def cmd_list():
    '''
    Lists installed packages and their dependencies
    '''
    app.perform_list()
    app.perform_check(silent=True)


@cli.command('outdated', help='Check for updates')
def cmd_outdated():
    '''
    Checks for the newest versions of the installed packages
    '''
    app.perform_outdated()
