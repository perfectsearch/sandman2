#!/usr/bin/python3
import subprocess
import os
import shutil

local_build_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'build')
build_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../built.linux_x86-64/sandman2')
os.chdir(local_build_dir)
subprocess.check_call(['bash', 'build.sh'])
shutil.rmtree(os.path.join(build_dir, 'install'), ignore_errors=True)
shutil.rmtree(os.path.join(build_dir, 'files'), ignore_errors=True)
shutil.move('install', build_dir)
shutil.move('files', build_dir)
