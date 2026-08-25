import os
import re

from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = "https://github.com/theflash2k/pyserve"
RAW = "https://raw.githubusercontent.com/theflash2k/pyserve/main/"

def read_version():
    """Single source of truth for the version: pyserve/__init__.py."""
    source = open(os.path.join(HERE, "pyserve", "__init__.py"), encoding="utf-8").read()
    found = re.search(r'^__version__ = "([^"]+)"', source, re.M)
    if not found:
        raise RuntimeError("Could not find __version__ in pyserve/__init__.py")
    return found.group(1)

def read_readme():
    """The README with relative links made absolute so PyPI can render them."""
    text = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    text = re.sub(r'(<img\s+src=")(?!https?://)([^"]+)', r"\1" + RAW + r"\2", text)
    text = re.sub(r"(\]\()(?!https?://|#)([^)]+)", r"\1" + REPO + r"/blob/main/\2", text)
    return text

setup(
    name="pyserve-http",
    version=read_version(),
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={
        "pyserve": [
            "assets/*.html",
            "assets/*.css",
            "assets/*.js",
            "assets/*.png",
            "assets/*.ico",
            "assets/*.ignore",
        ]
    },
    author="TheFlash2k",
    author_email="alitaqi2000@gmail.com",
    description="A glorified python3 -m http.server alternative: directory browser, "
                "ignore rules, uploads, search, authentication and per user access control.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url=REPO,
    project_urls={
        "Documentation": REPO + "/blob/main/docs/README.md",
        "Source": REPO,
        "Issues": REPO + "/issues",
    },
    license="Apache-2.0",
    keywords="http server file-server directory-listing upload iam static-files",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Filesystems",
        "Topic :: Utilities",
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "pyserve=pyserve.cli:main",
        ],
    },
    python_requires=">=3.7",
)
