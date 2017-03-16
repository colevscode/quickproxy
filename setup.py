import os
from distutils.core import setup

root = os.path.dirname(os.path.realpath(__file__))

setup(
    name='quickproxy3',
    version='0.3.0',
    author='Cole Krumbholz',
    author_email='cole@brace.io',
    description='A lightweight, per-request customizable HTTP proxy for python.',
    packages=['quickproxy3'],
    install_requires=open(root + "/requirements.txt").read().splitlines(),
    long_description=open(root + "/README.md").read(),
    license='LICENSE',
    package_data={'quickproxy3': ['data/test.*']},
)
