import os
from contextlib import contextmanager
from termcolor import colored
from click import getchar
from .ansi import strip_ansi

styles = {
    'debug': ['debug', 'white'],
    'info': [' info', 'green'],
    'warn': [' warn', 'yellow'],
    'error': ['error', 'red'],
}

colors = [
    'grey',
    'red',
    'green',
    'yellow',
    'blue',
    'magenta',
    'cyan',
    'white',
]


def do_log(style, *parts, attrs=['bold']):
    print(
        colored(styles[style][0], styles[style][1], attrs=attrs),
        *parts,
    )


def bold(text):
    return colored(text, attrs=['bold'])


for style in styles:
    locals()[style] = lambda *parts, style=style: do_log(style, *parts)

for color in colors:
    locals()[color] = lambda text, color=color: colored(text, color)

for color in colors:
    locals()['dark' + color] = lambda text, color=color: colored(text, color, attrs=['dark'])


def yn(*parts):
    print(
        colored('  (?)', 'blue', attrs=['bold']),
        *parts,
        end=' ',
    )
    prompt = 'Yes / No '
    print(colored(prompt, attrs=['bold']), end='', flush=True)
    while True:
        key = getchar()
        if key in 'yn':
            break
    print('\b' * len(prompt) + '\033[K', end='')
    result = key == 'y'
    print(colored('Yes' if result else 'No', attrs=['bold']))
    return result


def prompt(*parts, default=None, validate=lambda x: x):
    while True:
        default_s = ''
        if default:
            default_s = colored(f'({default})', 'white', attrs=['dark'])

        print(
            colored('  (?)', 'blue', attrs=['bold']),
            *parts,
            default_s + colored(':', 'cyan'),
            end=' ',
            flush=True,
        )

        result = input()

        if not result:
            return default

        try:
            result = validate(result)
        except Exception as e:
            print('\033[F\033[K', end='')
            do_log('error', str(e))
            continue
        break

    return result


def table(header, rows, pad=2):
    max_w = [0] * len(header)
    for row in [header] + rows:
        for index, item in enumerate(row):
            max_w[index] = max(max_w[index], len(strip_ansi(item)))
    width = pad * (len(header) - 1) + sum(max_w)

    print()
    for row in [header, [colored('-' * width, 'white', attrs=['dark'])]] + rows:
        for index, item in enumerate(row):
            print(str(item) + ' ' * (max_w[index] + pad - len(strip_ansi(item))), end='')
        print()
    print()


@contextmanager
def log_line():
    prefix = colored('  ... ', 'blue', attrs=['bold'])
    width = os.get_terminal_size()[0] - 6
    print(prefix)

    def log(s):
        print('\033[F\033[K', end='')
        print(' ' * width + '\b' * width, end='')
        print(prefix, end='')
        s = s.replace('\n', ' ')
        if len(s) > width:
            s =  '...' + s[len(s) - width - 4:]
        print(s)

    yield log
