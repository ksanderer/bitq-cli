import random, re, time
from string import digits, ascii_uppercase, ascii_lowercase
import shutil
import re, datetime


def rand_string(length=10, char_set=digits+ascii_uppercase+ascii_lowercase):
    return ''.join( random.choice(char_set) for _ in range(length) )


def replace__helper(x, d):
    # print('\r\n\r\nreplace__helper')
    # print(x.group(), d)
    replace_str = x.group()
    replace_str = replace_str.replace("{", "")
    replace_str = replace_str.replace("}", "")

    obj = d[replace_str]
    if callable(obj) or hasattr(obj, '__call__'):
        return obj()
    elif isinstance(obj, list):
        return " ".join(obj)
    else:
        return obj


def list_get__safe(l, idx, default):
  try:
    return l[idx]
  except IndexError:
    return default


def regex_dict_replace(s, d):
    '''
    Replace keys in {} with dict keys.

    >> s = "this is {FILE_NAME}."
    >> d = {"FILE_NAME": "file_name.zip", "PARAM2": 23}
    >> new_s = regex_dict_replace(s, d)
    >> news_s
    this is file_name.zip.

    :param s:
    :param d:
    :return:
    '''
    # print('(\{' + '\}|\{'.join(d.keys()) + r'\})')
    pattern = re.compile(r'(\{' + '\}|\{'.join(d.keys()) + r'\})')
    return pattern.sub(lambda x: replace__helper(x, d), s)


def parse_backup_interval(interval):
    mult = None
    letter = None

    if interval.find("m") > 0:
        mult = 60
        letter = "m"
    elif interval.find("h") > 0:
        mult = 60 * 60
        letter = "h"
    elif interval.find("d") > 0:
        mult = 60 * 60 * 24
        letter = "d"
    elif interval.find("w") > 0:
        mult = 60 * 60 * 24 * 7
        letter = "w"
    elif interval.find("M") > 0:
        mult = 60 * 60 * 24 * 30
        letter = "M"

    interval_number = int(interval.replace(letter, ""))

    return interval_number * mult


interval_regex = re.compile('(\d+)([hdwM]{1})')


def interval_str_to_seconds(interval):
    try:
        m = interval_regex.match(interval)
        matches = m.groups()

        number = int(matches[0])
        letter = matches[1]

        def letter_to_seconds(letter):
            return dict(
                h=60 * 60,
                d=60 * 60 * 24,
                w=60 * 60 * 24 * 7,
                M=60 * 60 * 24 * 30
            )[letter]

        return letter_to_seconds(letter) * number, letter

    except:
        raise Exception("Wrong time interval provided: %s (Should match '(\d+)(\w)' expression)" % interval)


def interval_seconds_to_str(seconds, letter):
    try:
        def seconds_to_letter(letter):
            return dict(
                h=60 * 60,
                d=60 * 60 * 24,
                w=60 * 60 * 24 * 7,
                M=60 * 60 * 24 * 30
            )[letter]

        return "%s %s" % (str(round(seconds / seconds_to_letter(letter), 2)), letter)

    except:
        raise Exception("parameters are passed seconds = int(), letter = str(h|d|w|M). Passed seconds = %s, letter = %s" % str(seconds), str(letter))


def rm_dir__callback(dir):
    def _callback():
        return rm_dir(dir)

    return _callback


def rm_dir(dir):
    shutil.rmtree(dir)