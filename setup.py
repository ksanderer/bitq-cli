from setuptools import setup
import os, errno

DEFAULT_CONFIG_DIR = '/etc/bitq/'

setup_options = dict(
    name='bitq',
    version='0.0.1',
    description='bitqwe.com CLI tool',
    url='https://github.com/ksanderer/bitq-cli',
    author='Alex Temchenko',
    author_email='ksanderer@gmail.com',
    license='MIT',
    packages=[
        'bp',
        'bp.lib',
        'bp.lib.bitq',
    ],
    install_requires=['configparser', 'requests', 'click', 'peewee', 'bravado'],
    entry_points={
        'console_scripts': [
              'bitq = bp.main:cli'
          ]
    },
    data_files=[
        (DEFAULT_CONFIG_DIR, ['bp/config/main.conf']),
        (DEFAULT_CONFIG_DIR + 'projects', ['bp/config/projects/project_name.conf']),
    ],
    zip_safe=True
)

try:
    try:
        os.mkdir(DEFAULT_CONFIG_DIR)
    except OSError as e:
        if type(e).__name__ == "FileExistsError":
            pass
        else:
            raise e

    setup(**setup_options)
except OSError as e:
    if type(e).__name__ == "FileExistsError":
        setup(**setup_options)


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
            "Can't write to " + DEFAULT_CONFIG_DIR + " (default config directory)\r\n"
            "In order to use default config dir /etc/bp you need to manually create it\r\n"
            "take a look at:\r\n"
            "\r\n"
            "Starting guide - http://bitqwe.com/docs/cli#getting-started\r\n"
            "Project config setup - http://bitqwe.com/docs/cli/project-conf\r\n"
        )

