from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase
import datetime
import sqlite3
locks_db = SqliteExtDatabase('locks.db')


# class BaseModel(Model):
#     class Meta:
#         database = db


class OriginLock(Model):
    class Meta:
        database = locks_db
        indexes = (
            (("project", "origin"), True),
        )

    project = CharField()
    origin = CharField()
    timestamp = TimestampField(default=0)

    file_path = CharField(default=None, null=True)
    file_hash = CharField(default=None, null=True)

    # Project considered as locked for 5 seconds after lock file update
    lock_timeout = datetime.timedelta(seconds=5)

    class AlreadyLocked(Exception):
        pass

    class LockException(Exception):
        pass

    @classmethod
    def process_running(cls):
        # print("========process_running========")
        # print(cls.select().where((OriginLock.timestamp >= datetime.datetime.now() - cls.lock_timeout)))
        # print(cls.select().where((OriginLock.timestamp >= datetime.datetime.now() - cls.lock_timeout)).exists())
        # print("===============================")
        return cls.select().where((OriginLock.timestamp >= datetime.datetime.now() - cls.lock_timeout)).exists()

    def is_locked(self):
        curr_instance = OriginLock.get(OriginLock.project == self.project, OriginLock.origin == self.origin)

        if curr_instance.timestamp is None:
            return False

        now = datetime.datetime.now()

        return now - curr_instance.timestamp < self.lock_timeout

    def lock_init(self, file_path=None, file_hash=None):
        if (file_path is None) != (file_hash is None):
            raise self.LockException("Both file_path and file_hash should be provided.")

        if self.file_path is not None and file_path is not None and self.file_path != file_path:
            raise self.LockException("New file_path doesn't match old one from the current lock. "
                                     "You should create new lock or resume upload for current one")

        if self.file_hash is not None and file_hash is not None and self.file_hash != file_hash:
            raise self.LockException("New file_hash doesn't match old one from the current lock. "
                                     "You should create new lock or resume upload for current one")

        self.file_path = file_path
        self.file_hash = file_hash

        if self.file_path is None:
            raise self.LockException("file_path is required for lock_init (used to resume failed uploads)")

        if self.file_hash is None:
            raise self.LockException("file_hash is required for lock_init (used to resume failed uploads)")

        self.timestamp = datetime.datetime.now()
        self.save()

        # if not self.is_locked():
        #     pass
        # else:
        #     raise self.LockException("Can't lock. Origin already locked!")

    def lock_update(self):
        self.timestamp = datetime.datetime.now()
        self.save()

    @classmethod
    def get_lock(cls, project_name, origin_name):
        created = False

        # print(project_name, origin_name)
        # print("get_lick ->", project_name, origin_name)

        try:
            project = cls.get(cls.project == project_name, cls.origin == origin_name)
        except cls.DoesNotExist:
            project = cls(project=project_name, origin=origin_name, timestamp=0)
            created = True
            project.save()

        return project, created

    @staticmethod
    def lock_start(lock_instance, file_name):
        with locks_db.atomic() as transaction:  # Opens new transaction.
            try:
                lock_instance.lock_init(file_name)
            except Exception as ex:
                locks_db.rollback()
                raise ex

    @staticmethod
    def lock_end(lock_instance):
        with locks_db.atomic() as transaction:  # Opens new transaction.
            try:
                lock_instance.delete()
            except Exception as ex:
                locks_db.rollback()
                raise ex


def init_databases(path):
    locks_db.init(path + "/locks.db")
    locks_db.connect()
    tables = [OriginLock]
    for table in tables:
        try:
            locks_db.create_tables([table])
        except Exception as ex:
            pass