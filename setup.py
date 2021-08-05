from setuptools import setup, find_packages

setup(
    name="simpleland",
    version="0.0.1-dev",
    author="Brandyn Kusenda",
    author_email="pistar3.14@gmail.com",
    description="MultiAgent RL 2d Game Framework",
    long_description='MultiAgent RL 2d Game Framework',
    url="https://github.com/pistarlab/simpleland",
    license='',
    install_requires=[],
    package_data={'': ['assets/*']},
    packages=find_packages(),
    entry_points={},
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    python_requires='>=3.7',
)