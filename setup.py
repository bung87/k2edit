#!/usr/bin/env python3
"""Setup script for tree-sitter-nim package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

setup(
    name="tree-sitter-nim",
    version="0.1.0",
    description="Tree-sitter Nim language support for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="K2Edit",
    author_email="k2edit@example.com",
    url="https://github.com/k2edit/tree-sitter-nim",
    packages=find_packages(),
    package_data={
        "tree_sitter_nim": ["*.so", "*.dylib", "*.dll"],
    },
    install_requires=[
        "tree-sitter>=0.20.0",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords="tree-sitter nim syntax highlighting parsing",
    project_urls={
        "Bug Reports": "https://github.com/k2edit/tree-sitter-nim/issues",
        "Source": "https://github.com/k2edit/tree-sitter-nim",
    },
)