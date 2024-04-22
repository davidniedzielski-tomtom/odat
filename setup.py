from setuptools import setup

setup(
    name='openlr-webtool-python',
    version='0.0.1',
    description='Python OpenLR clients',
    author='David Niedzielski',
    packages=[],
    py_modules=['webtool'],
    install_requires=[
        "openlr~=1.0.1",
        "openlr_dereferencer @ git+https://github.com/davidniedzielski-tomtom/openlr-dereferencer-python.git@master",
        "geoutils @ git+https://github.com/davidniedzielski-tomtom/geoutils.git@main",
        "psycopg2~=2.9.8",
        "psycopg2_binary~=2.9.8",
        "pyproj~=3.6.1",
        "pytest~=8.1.1",
        "shapely~=2.0.3",
        "pyproj~=3.6.1",
    ]
)
