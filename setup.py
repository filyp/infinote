from setuptools import find_packages, setup

setup(
    name="infinote-md",
    version="0.2.1",  # Update the version number for new releases
    author="Filip Sondej",
    description="Feel the spatial freedom in your notes.",
    long_description_content_type="text/markdown",
    url="https://github.com/filyp/infinote",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PySide6",
        "pynvim",
        "colormath",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "infinote=infinote.main:main",
        ],
    },
)
