from .base import Requirements
from pip.req.req_file import join_lines, ignore_comments, process_line
# expand_env_variables
from ..model import Dependency


class RequirementsTxt(Requirements):
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
            # lines_enum = expand_env_variables(lines_enum)
        for line_number, line in lines_enum:
            req_iter = process_line(
                line, None, 0, None,
                None, None, None, None,
            )
            for req in req_iter:
                yield req, line_number

    def add(self, dependency):
        with open(self.path, 'r') as f:
            content = f.read()
        content = content.rstrip('\n') + '\n' + str(dependency.req)
        with open(self.path, 'w') as f:
            f.write(content)

    def remove(self, name):
        for req, line_number in self.__read_lines():
            if req.name == name:
                with open(self.path, 'r') as f:
                    content = f.read()
                lines = content.splitlines()
                lines.pop(line_number)
                content = '\n'.join(lines)
                with open(self.path, 'w') as f:
                    f.write(content)
                return
