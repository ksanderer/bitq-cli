from backports import configparser

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import requests
import hashlib

from .lib.bkp.bkp_sdk import BKP_SDK
# from .lib.gcs_uploader import GCSUploader
from .lib.helpers import *

from .models import OriginLock, locks_db, init_databases


class ReservedConfigKeys(object):
    BACKUP_COMMAND = "BACKUP_COMMAND"
    RECOVER_COMMAND = "RECOVER_COMMAND"

REQUIRED_PROJECT_KEYS = dict(
    settings=[
        "ENABLED",
        "PROJECT_NAME",
    ],
    origin=[
        "BACKUP_INTERVAL",
        "BACKUP_COMMAND",
    ]
)

storage_defaults = dict(
    gcs=dict(
        hash_method="md5"
    ),
    b2=dict(
        hash_method="sha1"
    )
)


def lock_worker(lock_obj, stop_event):
    while not stop_event.is_set():
        lock_obj.lock_update()
        time.sleep(1)


class LockManager:
    lock_thread = None
    lock_running = False
    lock_thread__stop_event = None

    def __init__(self, project_name, origin_name):
        self.project_name = project_name
        self.origin_name = origin_name
        self.lock_obj, self.lock_created = OriginLock.get_lock(self.project_name, origin_name)
        self.lock_run()

    @staticmethod
    def process_running():
        return OriginLock.process_running()

    def lock_init(self, file_path=None, file_hash=None):
        """
        Start file lock lock.

        upload_file_path: File path to upload during lock. If None it means that we will resume existing file upload.
        :return:
        """

        with locks_db.atomic() as transaction:  # Opens new transaction.
            try:
                self.lock_obj.lock_init(file_path=file_path, file_hash=file_hash)
            except Exception as ex:
                locks_db.rollback()
                raise ex

    def lock_run(self):
        self.lock_thread__stop_event = threading.Event()
        self.lock_thread = threading.Thread(
            target=lock_worker, kwargs=dict(lock_obj=self.lock_obj, stop_event=self.lock_thread__stop_event)
        )
        self.lock_thread.daemon = False
        self.lock_thread.start()
        self.lock_running = True

    def lock_stop(self):
        """
        Lock still exists but not updated. It means that file was not uploaded properly and we can resume upload later.
        :return:
        """
        if self.lock_running:
            # print("lock_end -> start")
            self.lock_thread__stop_event.set()
            self.lock_thread.join()
            self.lock_running = False

            self.lock_obj.timestamp = self.lock_obj.timestamp - OriginLock.lock_timeout
            self.lock_obj.save()
            # print("thread.join()")

    def lock_delete(self):
        """
        End lock for current file. Stop writing timestamps and deleteing lock file.
        :return:
        """
        self.lock_stop()
        # print(self.lock_obj.file_path)
        self.lock_obj.delete_instance()
        # print(self.lock_obj.file_path)
        # print("self.lock_obj.lock_delete()")

    def is_locked(self):
        """
        Check if current file is locked by another process.
        :return:
        """
        return self.lock_obj.is_locked()


def blank_logger(*args, **kwargs):
    pass


class BackupManager(object):
    project_name = None

    def __init__(self, config, schedule, logger=None, bkp_sdk=None):
        self.storage_service = "gcs"

        self.config = config
        self.schedule = schedule
        self.host = config.main['settings']['HOST']
        self.working_dir = config.main['settings']['WORKING_DIR']
        self.projects_dir = config.main['settings']['PROJECTS_DIR']
        self.backup_dir = config.main['settings']['BACKUP_DIR']
        self.auth_token = config.main['settings']['AUTH_TOKEN']
        self.project_loaded = False
        self.project_config = None
        self.settings = None
        self.logger = logger

        if bkp_sdk is not None:
            self.bkp_sdk = bkp_sdk
        else:
            self.bkp_sdk = BKP_SDK(self.host, self.auth_token)

        if self.logger is None:
            self.logger = blank_logger

        init_databases(self.working_dir)

    def project_load(self, project_name):
        self.project_name = project_name

        config = configparser.ConfigParser()
        config.optionxform = lambda option: option

        config_path = "%s/%s.conf" % (self.projects_dir, project_name)

        if not os.path.isfile(config_path):
            class ProjectConfigNotFound(Exception):
                pass

            raise ProjectConfigNotFound("Project config file doesn't exists at: %s" % config_path)

        config.read(config_path)

        for key in REQUIRED_PROJECT_KEYS['settings']:
            if key not in config['settings']:
                raise Exception("Project \"%s\" missing required key - \"%s\" in \"%s\" section." % (
                    self.project_name, key, "settings"
                ))

        self.project_config = config
        self.settings = dict()
        self.project_loaded = True

        for key in config['settings']:
            self.settings[key] = config['settings'][key]

        self.settings['ENABLED'] = not (
            'ENABLED' in config['settings'] and config['settings']['ENABLED'].lower() == "false")

        if 'BACKUP_EXPIRES' not in self.settings:
            self.settings['BACKUP_EXPIRES'] = ""

    def backup(self, origin=None, force=False):
        class SkipException(Exception):
            """
            Special exception to skip origin sections via try/catch approach
            """
            pass

        if LockManager.process_running():
            self.logger("Another backup process is running. Shutting down.")
            return

        if not self.project_loaded:
            self.logger("No project loaded")
            return

        if not self.settings['ENABLED']:
            self.logger("Project %s is disabled. To enable it set ENABLE variable to 'True'" % self.project_name)
            return

        for section in self.project_config.sections():
            lock = None
            file_hash = None

            try:
                lock = LockManager(self.project_name, section)
                if origin is not None and origin != section:
                    # if origin explicitly specified than we should start backup process only for it
                    raise SkipException()

                if section == "settings":
                    # settings is only one reserved name that can't be an origin
                    raise SkipException()

                origin_enabled = not (
                    'ENABLED' in self.project_config[section] and
                    self.project_config[section]['ENABLED'].lower() == "false"
                )

                if not origin_enabled:
                    if origin == section:
                        # Print info only if origin explicitly specified.
                        self.logger("Origin [%s] is disabled." % section)

                    raise SkipException()

                KEYS = self._keys_init(section)

                # Check BACKUP_INTERVAL and latest backup times.
                backup_interval, interval_letter = interval_str_to_seconds(self.project_config[section]['BACKUP_INTERVAL'])
                backup_latest = self.schedule.get_project_backup_time(self.project_name, section)

                # min_ago = round((time.time() - backup_latest) / 60, 2)
                sec_ago = time.time() - backup_latest

                if time.time() < backup_interval + backup_latest:
                    self.logger("[%s] -> [%s] skipping.. latest backup %s ago (out of %s).\r\n" % (
                        self.project_name, section, interval_seconds_to_str(sec_ago, interval_letter), self.project_config[section]['BACKUP_INTERVAL']
                    ))
                    raise SkipException()

                # Starting project origin backup
                self.logger("[%s] -> [%s]... " % (
                    self.project_name, section
                ))

                resume_upload = not lock.lock_created and lock.lock_obj.file_path is not None

                upload_file_exists = False
                if resume_upload:
                    upload_file_exists = os.path.exists(lock.lock_obj.file_path)

                    if not upload_file_exists:
                        # if there is lock entry in db and corresponding file was deleted
                        # we should delete lock and create blank one
                        lock.lock_delete()
                        lock = LockManager(self.project_name, section)

                if resume_upload and upload_file_exists:
                    self.logger("\tResuming upload.")
                    file_path = lock.lock_obj.file_path
                    file_hash = lock.lock_obj.file_hash
                else:
                    self.logger("\tStarting new upload.")
                    cmd = KEYS[ReservedConfigKeys.BACKUP_COMMAND]
                    file_path = KEYS['BKP_FILE_PATH']

                    _eval_command_in_thread(cmd)
                    # self._eval_command(cmd)
                    file_hash = get_file_hash(file_path, storage_defaults[self.storage_service]['hash_method'])

                if not os.path.exists(file_path):
                    self.logger("Backup file we should upload doesn't exists. "
                                "Probably due the error during BACKUP_COMMAND execution.")
                    raise SkipException()

                # print("resume_upload =", resume_upload, file_path, file_hash)

                lock.lock_init(file_path=file_path, file_hash=file_hash)

                upload_success = self.bkp_sdk.upload(project_name=self.settings['PROJECT_NAME'],
                        origin_name=section, file_path=file_path, file_hash=file_hash)

                # fu = GCSUploader(
                #     file_path=file_path,
                #     file_hash=file_hash,
                #     resume_upload=resume_upload,
                #     data=dict(
                #         expires=KEYS['BACKUP_EXPIRES'],
                #         project=self.settings['PROJECT_NAME'],
                #         origin=section,
                #     ),
                #     auth_token=self.auth_token,
                #     api_host=self.host
                # )

                # upload_success = fu.upload()

                if upload_success:
                    lock.lock_delete()
                    os.remove(file_path)

                    self.schedule.set_project_backup_time(self.project_name, section)

                    self.logger("\tUploaded -> %s" % str(upload_success))
            except OriginLock.AlreadyLocked:
                self.logger("Project's [%s] origin [%s] is locked by another process." % (
                    self.project_name, section
                ))
            except SkipException:
                # self.logger("->> SkipException")
                lock.lock_delete()
            except KeyboardInterrupt:
                lock.lock_delete()
                os.remove(file_path)
                raise KeyboardInterrupt()
            except BKP_SDK.AbortException as ex:
                self.logger("\tAborting: %s" % ex.__str__())
                lock.lock_delete()
                os.remove(file_path)
            except BKP_SDK.UploadException as ex:
                self.logger("\t%s" % ex.__str__())
                # lock.lock_reset()
            finally:
                lock.lock_stop()

    def restore(self, origin=None):
        for section in self.project_config.sections():
            if origin is not None and origin != section:
                continue

            if section == "settings":
                continue

            KEYS = self._keys_init(section)

            data = {
                "project": self.settings['PROJECT_NAME'],
                "origin": section
            }

            # TODO implement latest download
            self._backup_download(
                self.host + "/api/file_download/",
                data,
                KEYS['BKP_FILE_PATH']
            )

            cmd = KEYS[ReservedConfigKeys.RECOVER_COMMAND]
            self._eval_command(cmd)
            code = os.remove(KEYS['BKP_FILE_PATH'])

    def _keys_init(self, section_name):
        if section_name != "settings":
            for key in REQUIRED_PROJECT_KEYS['origin']:
                if key not in self.project_config[section_name]:
                    raise Exception("Project \"%s\" missing required key - \"%s\" in \"%s\" section." % (
                        self.project_name, key, section_name
                    ))

        keys = self.settings.copy()
        keys['RANDOM_STRING'] = rand_string
        keys['SECTION_NAME'] = section_name
        keys['BACKUP_DIR'] = self.backup_dir

        for key in self.project_config[section_name]:
            # print("reading ->", key)
            if self.project_config[section_name][key].find("\n") >= 0:
                keys[key] = self.project_config[section_name][key].split("\n")

            if key in keys and isinstance(keys[key], list):
                tmp_key = []
                for item in keys[key]:
                    tmp_key.append(regex_dict_replace(item, keys))

                keys[key] = tmp_key
            else:
                keys[key] = regex_dict_replace(self.project_config[section_name][key], keys)

        return keys

    @staticmethod
    def _eval_command(cmd):
        if isinstance(cmd, list):
            for cmd_item in cmd:
                os.system(cmd_item)
        else:
            os.system(cmd)

    def _backup_download(self, url, data, file_name):
        headers = {
            "Authorization": "Token %s" % self.auth_token
        }

        r = requests.get(url, params=data, headers=headers)

        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        return

    def is_project_loaded(self):
        class ProjectNotLoadedException(Exception):
            pass

        if not self.project_load:
            raise ProjectNotLoadedException()


def get_file_hash(file_path, hash_method):
    hasher = getattr(hashlib, hash_method)()
    f = open(file_path, "rb")
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        hasher.update(chunk)
    # return base64.b64encode(hasher.digest())
    return hasher.hexdigest()


import threading, multiprocessing


def _eval_command__worker(cmd):
    if isinstance(cmd, list):
        for cmd_item in cmd:
            os.system(cmd_item)
    else:
        os.system(cmd)


def _eval_command_in_thread(cmd):
    # print(cmd)
    t = multiprocessing.Process(target=_eval_command__worker, args=(cmd,))
    t.daemon = False
    t.start()
    t.join()
