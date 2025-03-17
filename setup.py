#!/usr/bin/env python3
"""
Setup script for the SlowJams application.

This script uses setuptools to create a distributable package
that can be installed with pip.
"""

import os
import sys
from setuptools import setup, find_packages

# Read the README file for the long description
try:
    with open('README.md', 'r', encoding='utf-8') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "SlowJams - A tool for downloading and manipulating audio from online video sources."

# Define the version
VERSION = '0.1.0'  # Initial version

# Define the requirements
with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Define the optional GUI requirements
gui_requirements = ['PyQt5>=5.15.0']

# Define the development/testing requirements
dev_requirements = [
    'pytest>=6.2.5',
    'pytest-cov>=2.12.1',
    'flake8>=3.9.2',
    'black>=21.6b0',
    'mypy>=0.910',
]

setup(
    name="slowjams",
    version=VERSION,
    author="SlowJams Contributors",
    author_email="slowjams.app@example.com",
    description="A tool for downloading and manipulating audio from online video sources",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eblack17/slowjams",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'slowjams=slowjams_app:main',
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Conversion",
        "Topic :: Internet :: WWW/HTTP",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        'gui': gui_requirements,
        'dev': dev_requirements,
        'all': gui_requirements + dev_requirements,
    },
    include_package_data=True,
    zip_safe=False,
    # Add default config files to the package
    package_data={
        'config': ['default_config.ini'],
    },
)

# Print installation instructions if this is being run directly
if __name__ == "__main__":
    print("\nThank you for installing SlowJams!")
    print("\nTo install for development:")
    print("  pip install -e .[dev]")
    print("\nTo install with GUI support:")
    print("  pip install -e .[gui]")
    print("\nTo install with all dependencies:")
    print("  pip install -e .[all]")
    print("\nTo run the application:")
    print("  slowjams")
    print("  # or")
    print("  python -m slowjams_app")
    print("\nFor more information, visit: https://github.com/eblack17/slowjams")