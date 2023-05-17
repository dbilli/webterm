
from setuptools import find_packages
from distutils.core import setup

setup(
	name='webterm',
	version='0.1.0',
	description='Simple SSH Web terminal',

	author='Diego Billi',
	author_email='diegobilli@gmail.com',

	url='',
	
	setup_requires='setuptools',
	
	packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"webterm": ["templates/*.*"]},
    
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'webterm=webterm.webterm:webterm_main',
        ]
    },
    
    install_requires=[
        'webssh==1.6.1',
    ]    
)
