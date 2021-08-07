from setuptools import setup, find_packages
import glob

config_files = [name.replace("landia/", "", 1) for name in glob.glob("landia/survival/**", recursive=True)]
binary_files = [name.replace("landia/", "", 1) for name in glob.glob("landia/assets/**", recursive=True)]

additional_files = binary_files + config_files

setup(
    name="landia",
    version="0.0.1-dev",
    author="Brandyn Kusenda",
    author_email="pistar3.14@gmail.com",
    description="MultiAgent RL 2d Game Framework",
    long_description='MultiAgent RL 2d Game Framework',
    url="https://github.com/pistarlab/landia",
    license='',
    install_requires=['lz4',
                      'pygame',
                      'pyinstrument',
                      'pytest',
                      'gym', 
                      'Pillow'
                      ],
    package_data={'': ['assets/*'],"landia":additional_files},
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'landia = landia.runner:main',
            'landia_env_test = landia.env:main'
        ]
    },
    include_data_files=True,
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    python_requires='>=3.7',
    zip_safe=False
)
