from distutils.core import setup

setup(
    name='quickproxy',
    version='0.1.0',
    author='Cole Krumbholz',
    author_email='cole@brace.io',
    description='A lightweight, per-request customizable HTTP proxy for python.',
    packages=['quickproxy'],
    install_requires=open("requirements.txt").read().splitlines(),
    long_description=open('README.md').read(),
    license='LICENSE',
)