from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aishell",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="An intelligent command line tool with web search, shell capabilities, and LLM integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/aishell",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.1.0",
        "requests>=2.31.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "aishell=aishell.cli:main",
        ],
    },
)