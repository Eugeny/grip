import click

class AliasedGroup(click.Group):
    def __init__(self, aliases={}, *args, **kwargs):
        self.aliases = aliases
        click.Group.__init__(self, *args, **kwargs)

    def get_command(self, ctx, cmd_name):
        cmd_name = self.aliases.get(cmd_name, cmd_name)
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

    def list_commands(self, ctx):
        commands = click.Group.list_commands(self, ctx)
        return sorted(commands + list(self.aliases))
