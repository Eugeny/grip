import os
import multiprocessing.pool
import click
import pkg_resources
import sys
from pip.req.req_file import parse_requirements
from pip.download import PipSession, path_to_url
from pip.index import PackageFinder, FormatControl, Link
from pip.locations import USER_CACHE_DIR
from pip.wheel import WheelCache
from pip._vendor.packaging.version import Version
import pip.utils.logging
import grip.ui as ui
from .app import App
from .model.requirements import Requirements
from .model.package import Package

app = App()


@click.group()
@click.option('--global', '-g', 'glob', is_flag=True, default=False, help='Act on the global site, not the local virtualenv')
@click.option('--cwd', '-d', default=None, help='Working directory')
@click.option('--interactive/--noninteractive', '-i/-n', default=lambda: os.isatty(0), help='Allow user interaction')
def cli(glob=False, cwd=None, interactive=False):
    if cwd:
        os.chdir(cwd)

    app.interactive = interactive

    if glob:
        if app.virtualenv:
            ui.error('Cannot act on the global site when running inside a virtualenv shell.')
            ui.error('Run `deactivate` first.')
            sys.exit(1)
    else:
        virtualenv = app.locate_virtualenv()
        if not virtualenv:
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


@cli.command()
def outdated():

    session = PipSession(cache=os.path.join(USER_CACHE_DIR, 'http'))
    finder = PackageFinder([], ['https://pypi.org/simple/'], session=session)

    installed = load_installed('venv/lib/python3.6/site-packages')

    reqs = list(parse_requirements('requirements.txt', session=session))

    def process_single(req):
        pip.utils.logging._log_state.indentation = 0
        req.req.name = pkg_resources.safe_name(req.req.name).lower()
        if req.name in installed:
            installed_version = Version(installed[req.name].version)
        else:
            installed_version = None

        all_candidates = finder.find_all_candidates(req.name)
        compatible_versions = set(
            req.req.specifier.filter(
                [str(c.version) for c in all_candidates],
                prereleases=False
            )
        )
        applicable_candidates = [
            c for c in all_candidates if str(c.version) in compatible_versions
        ]

        best_candidate = None
        best_release = None
        if applicable_candidates:
            best_candidate = max(applicable_candidates, key=finder._candidate_sort_key)
        if all_candidates:
            best_release = max(all_candidates, key=finder._candidate_sort_key)

        if best_release and best_release.version > (installed_version or Version('0')):
            return (
                req.name,
                installed_version,
                best_candidate.version if best_candidate else None,
                best_release.version if best_release else None,
            )

    with multiprocessing.pool.ThreadPool(processes=16) as pool:
        with click.progressbar(pool.imap_unordered(process_single, reqs), length=len(reqs), label='Checking latest versions') as bar:
            results = [x for x in bar if x]

    click.secho(f'Outdated packages: {len(results)}', fg='white', bold=True)
    for result in sorted(results, key=lambda x: x[0]):
        click.echo(f' {result[0]}:\n  {click.style(str(result[1] or "Not installed"), fg="yellow")}', nl=False)
        if result[2] and result[2] > (result[1] or Version('0')):
            click.echo(f' -> {click.style(str(result[2]), fg="cyan")}', nl=False)
        if result[3]:
            if result[3] > (result[1] or Version('0')):
                click.echo(f' (latest: {click.style(str(result[3]), fg="green")})')
            else:
                click.echo(' (latest)')
