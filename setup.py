from setuptools import setup, find_packages


def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "An intelligent Python toolkit for geographic modeling with smart model recommendations"


setup(
    name="PyGeoModel",
    version="1.0.4",
    author="Peilong Ma",
    author_email="mpl_gis@nnu.edu.cn",
    description="A Python package for geographic modeling.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/MpLebron/PyGeoModel",
    py_modules=["scripts", "pygeomodel"],
    packages=find_packages(),
    package_data={
        '': ['data/*.json', 'data/*.txt', 'config/*.json'],
        'ogmsServer2': ['data/*.tif', 'data/*/*.tif'],
        'config': ['*.json'],
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
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
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
    keywords="geographic modeling, GIS, machine learning, model recommendation, geospatial analysis, jupyter",
)
