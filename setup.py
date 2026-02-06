"""Setup script for DNP3 driver package."""

import re
from pathlib import Path

from setuptools import setup, find_packages

# Repo root is the dnp3py package (not a dnp3py/ subdir), so map it explicitly.
_root = Path(__file__).resolve().parent
_subpackages = find_packages(
    where=str(_root),
    exclude=["tests", "tests.*"],
)
# Ensure we don't install the tests package; keep core, layers, objects, utils, examples.
packages = ["dnp3py"] + [f"dnp3py.{p}" for p in _subpackages]

# Single source of version: read from package __init__.py
_version_file = _root / "__init__.py"
_version_match = re.search(
    r'__version__\s*=\s*["\']([^"\']+)["\']',
    _version_file.read_text(encoding="utf-8"),
)
if not _version_match:
    raise RuntimeError("__version__ not found in __init__.py")
version = _version_match.group(1)

# Long description for PyPI / pip show
_long_description = (_root / "README.md").read_text(encoding="utf-8")

setup(
    name="dnp3py",
    version=version,
    description="A pure Python DNP3 protocol driver for SCADA communication",
    long_description=_long_description,
    long_description_content_type="text/markdown",
    author="DNP3 Driver Development",
    package_dir={"dnp3py": "."},
    packages=packages,
    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Networking",
        "Topic :: System :: Hardware",
    ],
)
