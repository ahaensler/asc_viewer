import io
import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

setup(
    name="asc_viewer",
    version="1.0",
    description="A viewer for LTspice ASC schematics implemented in wxPython",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='http://github.com/ahaensler/asc_viewer',
    scripts=["bin/asc_viewer"],
    packages=["asc_viewer"],
    author="Adrian Haensler",
    license='MIT',
    python_requires=">=3.8.0",
    install_requires=[
        "rtreelib>=0.2.0",
        "wxPython>=4.2.0",
    ],
)
