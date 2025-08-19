#!/usr/bin/env python3
"""Setup script for K2Edit - Terminal Code Editor with Kimi-K2 AI Integration."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Read requirements from requirements.txt
def read_requirements():
    requirements_file = this_directory / "requirements.txt"
    requirements = []
    if requirements_file.exists():
        with open(requirements_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Skip git URLs for now - they need special handling
                    if not line.startswith('git+'):
                        requirements.append(line)
    return requirements

setup(
    name="k2edit",
    version="0.1.5",
    description="Terminal Code Editor with Kimi-K2 AI Integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="K2Edit",
    author_email="k2edit@example.com",
    url="https://github.com/k2edit/k2edit",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
        ],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "k2edit=k2edit.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Editors",
        "Topic :: Software Development :: User Interfaces",
    ],
    keywords="terminal editor ai kimi code assistance",
    project_urls={
        "Bug Reports": "https://github.com/k2edit/k2edit/issues",
        "Source": "https://github.com/k2edit/k2edit",
        "Documentation": "https://github.com/k2edit/k2edit#readme",
    },
)