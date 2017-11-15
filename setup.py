from setuptools import setup
import os, errno

setup_options = dict(
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

try:
    os.mkdir('/etc/bp')
    setup(**setup_options)
except OSError as e:
    if type(e).__name__ == "FileExistsError":
        setup(**setup_options)
        exit()


    if type(e).__name__ == "PermissionError" or \
        e[0] == 13:

        print("installing..")
        # Can't copy files to /etc (no permissions)
        del setup_options['data_files']
        setup(**setup_options)

        print(
            "\r\n"
            "Warning!\r\n"
            "\r\n"
            "Can't write to /etc/bp (default config directory)\r\n"
            "In order to use default config dir /etc/bp you need to manually create it\r\n"
            "take a look at:\r\n"
            "\r\n"
            "Starting guide - http://bitqwe.com/docs/cli#getting-started\r\n"
            "Project config setup - http://bitqwe.com/docs/cli/project-conf\r\n"
        )

