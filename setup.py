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
    author="Your Name",  # 请替换为您的姓名
    author_email="your.email@example.com",  # 请替换为您的邮箱
    description="An intelligent Python toolkit for geographic modeling with smart model recommendations",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/PyGeoModel",  # 请替换为您的GitHub仓库
    py_modules=["scripts"],
    packages=find_packages(),
    package_data={
        'PyGeoModel': ['data/*.json', 'data/*.txt'],
        'ogmsServer2': ['data/*.tif', 'data/*/*.tif'],
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
