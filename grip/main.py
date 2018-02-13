import os
import click
import sys
import grip.ui as ui
from .app import App, Package, PackageDep, USER_PKG

app = App()


class AliasedGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


@click.group(cls=AliasedGroup)
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
                    print('Folder name (venv): ', end='')
                    name = input() or 'venv'
                    print('Interpreter (python3): ', end='')
                    interpreter = input() or 'python3'
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


@cli.command()
def check():
    app.perform_check()


@cli.command()
def prune():
    app.perform_prune()
    app.perform_check(silent=True)


@cli.command()
def freeze():
    app.perform_freeze()


@cli.command()
@click.argument('packages', nargs=-1)
def install(packages=None):
    if len(packages):
        parent = Package(USER_PKG, None)
        app.perform_install([PackageDep(spec, parent=parent) for spec in packages])
    elif app.requirements:
        app.perform_install_requirements()
    else:
        ui.error('No packages specified and no requirements file found')
        sys.exit(1)
    app.perform_check(silent=True)


@cli.command()
@click.argument('packages', nargs=-1)
def uninstall(packages=None):
    app.perform_uninstall(packages)
    app.perform_check(silent=True)


@cli.command('list')
def cmd_list():
    app.perform_list()
    app.perform_check(silent=True)


@cli.command()
def outdated():
    app.perform_outdated()
