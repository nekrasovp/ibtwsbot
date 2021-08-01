#!/usr/bin/env python

from setuptools import setup, find_packages

with open('README.md') as _f:
    _README_MD = _f.read()

_VERSION = '0.1'

setup(
    name='ibtwsbot',
    version=_VERSION,
    description='Interactive Brokers TWS bot',
    long_description=_README_MD,
    author="Nekrasov Pavel",
    author_email='nekrasovp@gmail.com',
    classifiers=[
        "Typing :: Typed"],
    url='https://github.com/nekrasovp/ibtwsbot',
    packages=find_packages(include=['ibtwsbot*']),
    test_suite="tests",
    setup_requires=[],
    tests_require=[],
    include_package_data=True,
    keywords='Interactive Brokers Trader Workstation bot script'
)
