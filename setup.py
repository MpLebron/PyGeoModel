from setuptools import setup, find_packages


def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "An intelligent Python toolkit for geographic modeling with smart model recommendations"


setup(
    name="PyGeoModel",
    version="1.0.16",
    author="Peilong Ma",
    author_email="mpl_gis@nnu.edu.cn",
    description="A Python package for integrating OpenGMS geographic model services.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/MpLebron/PyGeoModel",
    project_urls={
        "Documentation": "https://mplebron.github.io/PyGeoModel-docs/",
        "Source": "https://github.com/MpLebron/PyGeoModel",
    },
    py_modules=["scripts"],
    packages=find_packages(include=["pygeomodel", "pygeomodel.*", "ogmsServer2", "ogmsServer2.*"]),
    package_data={
        'pygeomodel': ['data/*.json', 'data/*.txt', 'data/*.csv'],
    },
    include_package_data=True,
    install_requires=[
        "ipywidgets>=7.6.0",
        "requests>=2.25.0",
        "openai>=1.0.0",
        "ipyfilechooser>=0.6.0",
        "markdown>=3.3.0",
        "nest-asyncio>=1.5.0",
        "geopandas>=0.10.0",
        "rasterio>=1.2.0",
        "nbformat>=5.1.0",
        "tenacity>=8.0.0"
    ],
    extras_require={
        "test": ["pytest>=8.0"],
    },
    python_requires=">=3.8",
    classifiers=[
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    keywords="geographic modeling, GIS, OpenGMS, model services, geospatial analysis, jupyter",
)
