import os
import click
import pkg_resources
from pip.req.req_file import parse_requirements
from pip.download import PipSession, path_to_url
from pip.index import PackageFinder, FormatControl, Link
from pip.locations import USER_CACHE_DIR
from pip.wheel import WheelCache
from .model.requirements import Requirements
from .model.package import Package


@click.group()
@click.option('--global', '-g', 'glob', is_flag=True, default=False, help='Act on the global site, not the local virtualenv')
@click.option('--cwd', '-d', default=None, help='Working directory')
def cli(glob=False, cwd=None):
    if cwd:
        os.chdir(cwd)


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
            all_candidates = finder.find_all_candidates(package.req.req.name)
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
