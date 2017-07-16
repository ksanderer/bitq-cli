from setuptools import setup

setup(
    name='bp',
    version='0.0.1',
    description='Backup cli tool.',
    url='http://github.com/storborg/funniest',
    author='Alex Temchenko',
    author_email='ksanderer@gmail.com',
    license='MIT',
    packages=[
        'bp',
        'bp.lib',
    ],
    install_requires=['configparser', 'requests', 'click', 'peewee'],
    entry_points={
        'console_scripts': [
              'bp = bp.main:cli'
          ]
    },
    data_files=[
        ('/etc/bp/', ['bp/config/main.conf']),
        ('/etc/bp/projects', ['bp/config/projects/project_name.conf']),
    ],

    zip_safe=True
)
