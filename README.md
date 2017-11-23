## Documentation

[http://bitqwe.com/docs/cli](http://bitqwe.com/docs/cli)

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
git clone https://github.com/ksanderer/bitq-cli.git && cd bitq-cli/
```
Install the package.

```bash
pip install -e .
```

## Getting Started
1. First and foremost you should setup `main.conf` config file:

        [settings]
            HOST=bitqwe.com
            AUTH_TOKEN=your_token_here
            BACKUP_DIR=tmp_dir_to_store_files

    Note that `BACKUP_DIR` can be absolute or relative.

2. Now we are ready to configure our first project:

    You can use example project config file - [example file](https://github.com/ksanderer/bitq-cli/blob/master/bp/config/projects/project_name.conf)
    Detailed description on projects `.conf` files placed <a href="http://bitqwe.com/docs/cli/project-conf">here</a>.
    

3. Adding cron job:

        crontab -e

        ----------
        0 * * * * bitq backup

    We recommend to set hourly cron job. There can't be any process race conditions
    so you should not think about that. If on backup process already running new
    backup one would be killed.
