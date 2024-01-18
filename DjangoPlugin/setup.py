from setuptools import setup

setup(
    name="Django Plugin",
    version="1.1",
    packages=["tracdjangoplugin"],
    include_package_data=True,
    entry_points={"trac.plugins": ["tracdjangoplugin = tracdjangoplugin"]},
)
