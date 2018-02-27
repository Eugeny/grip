import os
from .base import Requirements
from pip.req.req_file import join_lines, ignore_comments, process_line
from ..model import Dependency
import grip.ui as ui


class TxtRequirements(Requirements):
    def __init__(self, path):
        self.path = path

    def read(self):
        for req, line_number in self.__read_lines():
            yield Dependency(req)

    def __read_lines(self):
        with open(self.path) as f:
            lines = f.read().splitlines()
            lines_enum = enumerate(lines, start=1)
            lines_enum = join_lines(lines_enum)
            lines_enum = ignore_comments(lines_enum)
        for line_number, line in lines_enum:
            if line.startswith('-e '):
                ui.warn('requirements file flags are not supported yet:', line)
                continue
            req_iter = process_line(
                line, None, 0, None,
                None, None, None, None,
            )
            for req in req_iter:
                yield req, line_number

    def add(self, dependency):
        self.remove(dependency.name)
        with open(self.path, 'r') as f:
            content = f.read()
        content = content.rstrip('\n') + '\n' + str(dependency) + '\n'
        with open(self.path, 'w') as f:
            f.write(content)

    def remove(self, name):
        for req, line_number in self.__read_lines():
            if req.name == name:
                with open(self.path, 'r') as f:
                    content = f.read()
                lines = content.splitlines()
                lines.pop(line_number - 1)
                content = '\n'.join(lines) + '\n'
                with open(self.path, 'w') as f:
                    f.write(content)
                return

    def __str__(self):
        return os.path.basename(self.path)
