from pathlib import Path

from setuptools import find_packages, setup

from business_rules_genai import __version__ as version

PROJECT_ROOT = Path(__file__).parent
README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
HISTORY = (PROJECT_ROOT / "HISTORY.md").read_text(encoding="utf-8")

setup(
    name="business-rules-genai",
    version=version,
    description="Composable business rules engine with JSON-friendly DSL",
    long_description=f"{README}\n\n{HISTORY}",
    long_description_content_type="text/markdown",
    author="business-rules-genai maintainers",
    url="https://github.com/venmo/business-rules",
    packages=find_packages(),
    include_package_data=True,
    license="MIT",
    python_requires=">=3.9",
    install_requires=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development",
    ],
)
