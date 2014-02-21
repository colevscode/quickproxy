import os
from distutils.core import setup

root = os.path.dirname(os.path.realpath(__file__))

setup(
    name='quickproxy',
    version='0.1.1',
    author='Cole Krumbholz',
    author_email='cole@brace.io',
    description='A lightweight, per-request customizable HTTP proxy for python.',
    packages=['quickproxy'],
    install_requires=open(root+"/requirements.txt").read().splitlines(),
    long_description=open(root+"/README.md").read(),
    license='LICENSE',
    package_data={'quickproxy': ['data/test.*']},
)