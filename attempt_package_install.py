#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile

spec = sys.argv[1]

with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    subprocess.check_call(['grip', 'download', '--source', spec])
    name = os.listdir('.')[0]
    subprocess.call(['tar', 'xzf', name])
    while name.endswith(('.gz', '.tar', '.tgz')):
        name = os.path.splitext(name)[0]
    os.chdir(name)
    for x in sorted(os.listdir('.')):
        print(' -', x)
    #subprocess.check_call(['bash'])
    subprocess.check_call(['virtualenv', '-p', 'python3', 'venv'])
    try:
        subprocess.check_call(['grip', 'install'])
    except:
        os.rename(tmp, '/tmp/ws')
    subprocess.check_call(['grip', 'freeze'])
