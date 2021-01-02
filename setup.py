from setuptools import setup, find_packages

with open('README.md') as f:
  readme = f.read()

setup(
    name='karo',
    version='0.0.0',
    description='1d extrusion code',
    long_description=readme,
    author='Simon Grosse-Holz',
    packages=find_packages(exclude=('tests', 'docs')),
    )
