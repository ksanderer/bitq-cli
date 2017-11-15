## installation

### Using PIP
Bitqwe cli tool may be installed directly using Python Package Index (PyPi):

```bash
pip install bitq
```

### From the source
Should you wish to download and install it using the source code,
you can do as follows:

```bash
git clone https://github.com/bitqwe/bitqwe-cli.
cd bitqwe-cli/
```
Install the package.

```bash
python3 setup.py install
```

## Getting Started
1. First and foremost you should setup main.conf config file:

        [settings]
            HOST=http://bitqwe.com
            AUTH_TOKEN=your_token_here
            BACKUP_DIR=tmp_dir

    Note that `BACKUP_DIR` both can be absolute or
    relative as well.

2. Now we are ready to configure our first project:

        pb new --name=project_name

    Or just create new `{PROJECTS_DIR}/project_name.conf` file from scratch.
    Detailed description on projects `.conf` files placed <a href="http://bitqwe.com/docs/cli/project">here</a>.

3. Adding cron job:

        crontab -e

        ----------
        0 * * * * bp backup

    We recommend to set hourly cron job. There can't be any process race conditions
    so you should not think about that. If on backup process already running new
    backup one would be killed.