import os
import click
import pkg_resources
import sys
import grip.ui as ui
from .app import App
from .model.requirements import Requirements
from .model.package import Package

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
def cli(glob=False, cwd=None, interactive=False):
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

    ui.info('Operating on:', app.site_packages)


@cli.command()
@click.argument('packages', nargs=-1)
def install(packages=None):
    app.perform_install(packages)


@cli.command()
@click.argument('packages', nargs=-1)
def uninstall(packages=None):
    app.perform_uninstall(packages)


@cli.command('list')
def cmd_list():
    app.perform_list()


@cli.command()
def outdated():
    app.perform_outdated()


'''

def load_installed(path):
    installed = {}
    for dir in os.listdir(path):
        if dir.endswith('.dist-info'):
            dist_info = os.path.join(path, dir)
            dists = pkg_resources.distributions_from_metadata(dist_info)
            for dist in dists:
                installed[pkg_resources.safe_name(dist.project_name).lower()] = dist
    return installed

@cli.command()
def sync():
    session = PipSession(cache=os.path.join(USER_CACHE_DIR, 'http'))
    finder = PackageFinder([], ['https://pypi.python.org/simple/'], session=session)
    allow_all_prereleases = True

    installed = load_installed('venv/lib/python3.6/site-packages')

    req = list(parse_requirements('requirements.txt', session=session))
    reqs = Requirements(req)

    target_tree = Package(None)

    for req in reqs.reqs:
        print(req)

        if req.name in installed:
            print(' Installed:', installed[req.name])
            if installed[req.name].version in req.specifier:
                print(' Is compatible!')

        target_tree.dependencies.append(Package(req))
        print()

    ALREADY_INSTALLED = 'installed'

    dependency_resolution_queue = target_tree.dependencies[:]
    wheel_cache = WheelCache(USER_CACHE_DIR, FormatControl(set(), set()))

    while len(dependency_resolution_queue):
        package = dependency_resolution_queue.pop(0)
        print('Resolving deps for', package.req)
        install_source = None
        if package.req.name in installed and installed[package.req.name].version in package.req.specifier:
            # Installed and satisfied
            install_source = Link(path_to_url(ALREADY_INSTALLED))
            meta_path = installed[package.req.name].egg_info
            print(' Found installed')
        elif package.req.link:
            install_source = package.req.link
            print(' Using URL:', package.req.link)
        else:
            all_candidates = finder.find_all_candidates(package.req.name)
            compatible_versions = set(
                package.req.req.specifier.filter(
                    [str(c.version) for c in all_candidates],
                    prereleases=allow_all_prereleases
                )
            )
            applicable_candidates = [
                c for c in all_candidates if str(c.version) in compatible_versions
            ]

            #for candidate in applicable_candidates:
            #    print(' ', candidate)

            best_candidate = None
            if applicable_candidates:
                best_candidate = max(applicable_candidates, key=finder._candidate_sort_key)

            install_source = best_candidate.location
            print(' Found link:', best_candidate.location)

        wheel = wheel_cache.cached_wheel(install_source, package.req.name)
        if wheel and wheel.is_wheel:
            install_source = wheel
            print(' Found wheel:', wheel)

        print()

    click.echo('Synching')
'''
