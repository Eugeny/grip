import sys
from termcolor import colored
from click import getchar
from contextlib import contextmanager


styles = {
    'info': ['info ', 'cyan'],
    'warn': ['warn ', 'yellow'],
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

def do_log(style, *parts):
    print(
        colored(styles[style][0], styles[style][1], attrs=['bold']),
        *parts,
    )

for style in styles:
    locals()[style] = lambda *parts, style=style: do_log(style, *parts)

for color in colors:
    locals()[color] = lambda text, color=color: colored(text, color)


def yn(*parts):
    print(
        colored(' (?) ', 'blue', attrs=['bold']),
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
        print(
            colored(' (?) ', 'blue', attrs=['bold']),
            *parts,
            colored(':', 'cyan'),
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
