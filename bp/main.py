import os, re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# sys.path.append("/".join([BASE_DIR, "bkp-cli/lib"]))
import atexit
from shutil import copyfile
import click
import requests
from .backup_project import BackupManager
from .lib.config import Config, Schedule
from .lib.helpers import *
# from .lib.bp_api import BPAPI
from .lib.bitq.bkp_sdk import BKP_SDK

PACKAGE_NAME = "bitq"
CONFIG_DIR = "/etc/%s" % PACKAGE_NAME
BACKUP_DIR = "backup_files"
PROJECTS_DIR = "projects"


def check_main_conf(ctx):
    if 'config' not in ctx.obj:
        if os.path.exists(ctx.obj['CONFIG_DIR']+"/main.conf"):
            click.echo("AUTH_TOKEN or WORKING_DIR not set in %s/main.conf" % ctx.obj['CONFIG_DIR'])
        else:
            click.echo("Missing required config file \"main.conf\" in %s" % ctx.obj['CONFIG_DIR'])
            click.echo(
                "In order to use default config dir /etc/bp you need to manually create it\r\n"
                "take a look at:\r\n"
                "\r\n"
                "Starting guide - http://bitqwe.com/docs/cli#getting-started\r\n"
                "Project config setup - http://bitqwe.com/docs/cli/project-conf\r\n"
            )

        return False

    return True


@click.command()
@click.option('--project', '-p', default=None,
              help='Project config name to backup ({project_name}.conf).'
                   'If no project specified then ALL projects will be processed.')
@click.option('--origin', '-o', default=None,
              help='Project\'s origin to backup. -p options is required.')
@click.option('--force', default=False,
              help='Force backup project even if it\'s time doesn\'t come yet.', is_flag=True)
@click.pass_context
def backup(ctx, project, origin, force):
    """Run backup project process."""

    if not check_main_conf(ctx):
        return

    if origin is not None and project is None:
        click.echo("--project option is required when --origin is set.")
        return

    bkp = ctx.obj["bkp"]

    if not os.path.exists(ctx.obj["PROJECTS_DIR"]):
        click.echo("Projects directory doesn't exists at %s" % ctx.obj["PROJECTS_DIR"])
        return

    if project is not None:
        bkp.project_load(project_name=project)
        bkp.backup(origin=origin, force=force)
    else:
        for file in os.listdir(ctx.obj["PROJECTS_DIR"]):
            if file.endswith(".conf"):
                project_name = file.replace(".conf", "")
                bkp.project_load(project_name=project_name)
                bkp.backup(origin=origin, force=force)


# @click.command()
# @click.option('--project', '-p') #help='Specify working project.'
# @click.option('--origin', '-o', default=None) #help='Specify origin to restore.'
# @click.pass_context
# def restore(ctx, project, origin):
#     """Restore latest project's origin."""
#
#     if not check_main_conf(ctx):
#         return
#
#     if not os.path.exists(ctx.obj["PROJECTS_DIR"]):
#         click.echo("Projects directory doesn't exists at %s" % ctx.obj["PROJECTS_DIR"])
#         return
#
#     ctx.obj['bkp'].project_load(project_name=project)
#     ctx.obj['bkp'].restore(origin=origin)


@click.command()
@click.option('--file', '-f')  # help='Specify working project.'
@click.option('--stream', default=False, is_flag=True)  # help='Specify working project.'
@click.pass_context
def download(ctx, file, stream):
    """Restore latest project's origin."""
    if not check_main_conf(ctx):
        return

    file = int(file)

    resp = ctx.obj['api'].client.file.file_download(id=file).result()

    if 'error_code' in resp:
        click.echo(resp['error_message'])
        return

    if stream:
        r = requests.get(resp['download_url'])
        stdout_binary = click.get_binary_stream('stdout')

        for chunk in r.iter_content(chunk_size=512 * 1024):
            stdout_binary.write(chunk)
    else:
        click.echo(resp['download_url'])


# @click.command()
# @click.pass_context
# def pwd(ctx):
#     """Shows package working directory"""
#     print(BASE_DIR)


def project_name_match(name):
    match = re.match(r'^(?P<name>[\w\d_]+)$', name)
    return match and match.groupdict()['name'] == name



@click.command()
@click.option('--project', '-p', help='Project to list files.')
@click.option('--origin', '-o', default=None, help='Project\'s origin to list files. -p options is required.')
@click.pass_context
def files(ctx, project, origin):
    if not check_main_conf(ctx):
        return

    if project is None:
        click.echo("Project name is missing. Specify project name 'bp files -p project_name'")
        return

    api = ctx.obj['api']

    resp = api.cleint.file.file_list(project_name=project, origin_name=origin)
    if not resp['success']:
        click.echo(resp['error_message'])
        return

    resp = resp['response']

    for project_name in resp.keys():
        click.echo("[%s]" % project_name)

        for origin_name in resp[project_name].keys():
            click.echo("\t[%s]" % origin_name)

            for file_item in resp[project_name][origin_name]:
                # print(resp[project_name][origin_name])
                # file_item = resp[project_name][origin_name][file_num]
                click.echo("\t\t[%s] %s (%s)" % (file_item['id'], file_item['name'], file_item['date']))

# @click.command()
# @click.argument('action')
# @click.argument('name')
# @click.pass_context
# def project(ctx, action, name):
#     """Run project action (create, edit, delete)"""
#     def action_switch(action):
#         actions = dict(
#             create=project_create,
#             edit=project_edit,
#             delete=project_delete
#         )
#
#         if action not in actions:
#             click.echo("There is no action with that name.")
#             return project_blank_action
#
#         return actions[action](ctx, name)
#
#     return action_switch(action)
#
#
# def project_blank_action():
#     pass
#
#
# def project_create(ctx, name):
#     """Shows package working directory (can be changed with --config-dir)"""
#     if not check_main_conf(ctx):
#         return
#
#     project_config_file = "%s/%s.conf" % (ctx.obj["PROJECTS_DIR"], name)
#
#     if os.path.exists(project_config_file):
#         click.echo("Project with name \"%s\" already exists!" % name)
#         return
#
#     if name is None or not project_name_match(name):
#         click.echo("Project name should match \"^[\w\d\_]$\" pattern.")
#         return
#
#     copyfile(BASE_DIR + "/resources/project.conf.default", project_config_file)
#     click.edit(filename=project_config_file)
#
#
# def project_edit(ctx, name):
#     """Shows package working directory (can be changed with --config-dir)"""
#     if not check_main_conf(ctx):
#         return
#
#     project_config_file = "%s/%s.conf" % (ctx.obj["PROJECTS_DIR"], name)
#
#     if not os.path.exists(project_config_file):
#         click.echo("Project with name \"%s\" not exists (Use 'bp project new my_project_name' to create it)!" % name)
#         return
#
#     click.edit(filename=project_config_file)
#
#
# def project_delete(ctx, name):
#     """Shows package working directory (can be changed with --config-dir)"""
#     if not check_main_conf(ctx):
#         return
#
#     project_config_file = "%s/%s.conf" % (ctx.obj["PROJECTS_DIR"], name)
#
#     if os.path.exists(project_config_file):
#         prompt_value = click.prompt("Are you sure about project deletion? It can't be restored after that. "
#                                   "Type project name to delete project",
#                                 default=None)
#
#         if prompt_value == name:
#             os.remove(project_config_file)
#             click.echo("Project \"%s\" was deleted." % name)
#         else:
#             click.echo("Project name didn't match your input. Operation declined.")



@click.group()
@click.option('--config', '-c', default=None, type=click.Path(),
              help='Config files directory. Default to %s.' % CONFIG_DIR)
@click.pass_context
def cli(ctx, config):
    """
    Hint: to get additional help on command run:

    bp COMMAND --help
    """

    config_dir = config

    if config_dir is None:
        config_dir = CONFIG_DIR

    setattr(ctx, "obj", {})
    ctx.obj['CONFIG_DIR'] = config_dir

    # main.conf does't exists in CONFIG_DIR
    main_conf_path = "%s/main.conf" % config_dir
    if not os.path.exists(main_conf_path):
        return

    conf_obj = Config(config_dir=config_dir)

    ctx.obj['PROJECTS_DIR'] = "%s/%s" % (config_dir, PROJECTS_DIR)
    ctx.obj["WORKING_DIR"] = conf_obj.main['settings']['WORKING_DIR']

    # WORKING_DIR not set in current main.conf
    if ctx.obj['WORKING_DIR'] == "/your/working/directory" or \
        ctx.obj['WORKING_DIR'] is None or \
        ctx.obj['WORKING_DIR'] == "":
        # click.echo("Specify WORKING_DIR in the '%s'" % main_conf_path)
        return

    # WORKING_DIR relative path checks
    if not ctx.obj['WORKING_DIR'].startswith("/"):
        if config_dir == CONFIG_DIR:
            click.echo("WORKING_DIR not allowed in %s" % CONFIG_DIR)
            return

        # If WORKING_DIR relative to the custom config directory, then
        # try to make absolute path from it
        ctx.obj['WORKING_DIR'] = "%s/%s" % (config_dir, ctx.obj['WORKING_DIR'])
        conf_obj.main['settings']['WORKING_DIR'] = ctx.obj['WORKING_DIR']

    # Define BACKUP_DIR when WORKING_DIR is ready for use
    ctx.obj["BACKUP_DIR"] = "%s/%s" % (ctx.obj["WORKING_DIR"], BACKUP_DIR)

    # AUTH_TOKEN not set in current main.conf
    if conf_obj.main['settings']['AUTH_TOKEN'] == "your_bitqwe_api_token":
        # click.echo("Specify AUTH_TOKEN in the '%s'" % main_conf_path)
        return

    # Cheack if all required_dirs are exists in ctx.obj[dir]
    # If not exists then try to create it
    required_dirs = ['WORKING_DIR', 'BACKUP_DIR']
    for dir in required_dirs:
        if not os.path.exists(ctx.obj[dir]):
            click.echo("Missing required directory '%s'" % ctx.obj[dir])
            try:
                os.makedirs(ctx.obj[dir])
                click.echo("Directory '%s' created successfully." % ctx.obj[dir])
            except:
                click.echo("There is no permission to create '%s' directory. You should create it manually." % ctx.obj[dir])

    # Add to config all defined variables 'WORKING_DIR', 'BACKUP_DIR', 'PROJECTS_DIR', 'CONFIG_DIR'
    for key in ctx.obj.keys():
        conf_obj.main
        conf_obj.main['settings'][key] = ctx.obj[key]

    ctx.obj["config"] = conf_obj

    # Register bp api
    auth_token = ctx.obj['config'].main['settings']['AUTH_TOKEN']
    host = ctx.obj['config'].main['settings']['HOST']
    ctx.obj['api'] = BKP_SDK(token=auth_token, host=host)

    # schedule tracks times to next backup project start
    schedule = Schedule(working_dir=ctx.obj["WORKING_DIR"])
    ctx.obj["bkp"] = BackupManager(config=conf_obj, schedule=schedule, logger=click.echo, bkp_sdk=ctx.obj["api"])

    atexit.register(schedule.save)
    # atexit.register(helpers.rm_dir__callback(ctx.obj["BACKUP_DIR"]))


cli.add_command(backup)
cli.add_command(download)
cli.add_command(files)

# cli.add_command(pwd)
# cli.add_command(project)

if __name__ == "__main__":
    cli(obj={})

