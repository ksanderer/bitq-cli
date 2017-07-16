from backports import configparser
import time


class Config(object):
    MAIN_FILE_NAME = "main.conf"
    MAIN_FILE_PATH = None

    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.MAIN_FILE_PATH = "/".join([config_dir, self.MAIN_FILE_NAME])

        main = configparser.ConfigParser()
        main.optionxform = lambda option: option
        main.read(self.MAIN_FILE_PATH)

        self.main = main


class Schedule(object):
    SCHEDULE_FILE_NAME = ".schedule"
    SCHEDULE_FILE_PATH = None

    def __init__(self, working_dir):
        self.working_dir = working_dir
        self.SCHEDULE_FILE_PATH = "/".join([self.working_dir, self.SCHEDULE_FILE_NAME])

        schedule = configparser.ConfigParser()
        schedule.optionxform = lambda option: option
        schedule.read(self.SCHEDULE_FILE_PATH)

        # print("self.SCHEDULE_FILE_PATH", self.SCHEDULE_FILE_PATH)

        self.schedule = schedule

    def set_project_backup_time(self, project_name, origin):
        if project_name not in self.schedule:
            self.schedule[project_name] = {}

        self.schedule[project_name][origin] = str(time.time())

    def get_project_backup_time(self, project_name, origin):
        try:
            return float(self.schedule[project_name][origin])
        except:
            return 0

    def save(self):
        with open(self.SCHEDULE_FILE_PATH, 'w') as configfile:
            self.schedule.write(configfile)
