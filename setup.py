"""Setup script for DNP3 driver package."""

from setuptools import setup, find_packages

setup(
    name="dnp3_driver",
    version="1.0.0",
    description="A pure Python DNP3 protocol driver for SCADA communication",
    author="DNP3 Driver Development",
    packages=find_packages(),
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
