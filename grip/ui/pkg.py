from ..model import PackageGraph
from .echo import red, cyan, bold, green


def pkg(p, name=True, version=True):
    if not p:
        return red('none')
    if p.name == PackageGraph.PROJECT_PKG:
        return cyan(bold(p.name))
    if p.name == PackageGraph.USER_PKG:
        return green(bold(p.name))
    return (bold(p.name) if name else '') + (cyan('@' + str(p.version)) if version else '')


def dep(d, name=True, version=True):
    if d.url:
        return bold(d.url)
    return (bold(d.name) if name else '') + (cyan(str(d.specifier) or '(any)') if version else '')
