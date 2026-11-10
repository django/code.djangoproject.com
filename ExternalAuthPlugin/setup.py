from setuptools import find_packages, setup

setup(
    name="website-auth-plugin",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "Trac>=1.6",
        "PyJWT>=2,<3",
    ],
    entry_points={
        "trac.plugins": ["tracdjangoprojectauth = tracdjangoprojectauth.plugins"]
    },
)
