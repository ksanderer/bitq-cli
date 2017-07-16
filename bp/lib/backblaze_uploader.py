import datetime
import requests
import json
import threading
import queue
import hashlib
import os
import configparser
import ntpath


class BackblazeAPIException(Exception):
    status = None
    code = None
    message = None

    def __init__(self, status, code, message):
        super().__init__(message)

        self.status = status
        self.code = code
        self.message = message


class B2Uploader(object):

    class UploadException(Exception):
        pass

    def __init__(self, file_path, file_hash, data, auth_token, api_host, resume_upload=False,
                 threads_limit=10, memory_limit=200, min_part_size=50, max_part_size=100, upload_speed_limit=100):

        self.upload_speed_per_thread = 50
        self.small_file_size = 1024 * 1024 * 5

        self.file_path = file_path
        self.file_hash = file_hash
        self.resume_upload = resume_upload
        # dict(project, origin, expires)
        self.data = data

        self.threads_limit = threads_limit
        self.threads_count = None
        self.file_size = os.path.getsize(self.file_path)

        self.auth_token = auth_token
        self.api_host = api_host
        self.memory_limit = memory_limit
        self.part_size = min_part_size
        self.max_part_size = max_part_size
        self.upload_speed_limit = upload_speed_limit

        self.upload_url_array = None
        self.threads_count = None


        # if threads_count is None:
        self._set_max_threads__from_file_size()

    def _set_max_threads__from_file_size(self):
        threads_limits = list()
        threads_limits.append(self.threads_limit)
        threads_limits.append(self.upload_speed_limit // self.upload_speed_per_thread)
        threads_limits.append(self.memory_limit // self.part_size)

        """ Return the tuple ((x-x%y)/y, x%y).  Invariant: div*y + mod == x. """
        d, m = divmod(self.memory_limit, self.part_size)
        self.part_size += m // d
        self.part_size = self.part_size if self.part_size < self.max_part_size else self.max_part_size

        self.threads_count = min(threads_limits)

        print("self.threads_count", self.threads_count)
        print("self.part_size", self.part_size)

    def upload(self):
        if self.file_size <= self.small_file_size:
            self._upload_small_file()
        else:
            self._upload_large_file()

    def _upload_large_file(self):
        upload_data = self._prepare_file()

        print(upload_data)
        parts_uploaded = {}
        if self.resume_upload:
            parts_uploaded = self._get_uploaded_parts(upload_data['file_id'])
            # print(parts_data)
        # return

        # file_parts_upload_progress = configparser.ConfigParser()
        # file_parts_upload_progress__file_name = self.file_path + ".lock"

        # parts_uploaded = {}
        # if os.path.exists(file_parts_upload_progress__file_name):
        #     file_parts_upload_progress.read(file_parts_upload_progress__file_name)
        #
        #     for key, val in file_parts_upload_progress.items("parts"):
        #         parts_uploaded[key] = val

        upload_success, part_upload_results = large_file_uploader(
            upload_url_array=upload_data['upload_urls'],
            parts_uploaded=parts_uploaded,
            file_path=self.file_path,
            chunk_size=1024 * 1024 * self.part_size
        )

        if not upload_success:
            # file_parts_upload_progress = configparser.ConfigParser()
            #
            # for item in part_upload_results:
            #     if item['success']:
            #         file_parts_upload_progress[item['part_number']] = item['sha1']
            #
            # with open(self.file_path + ".lock", 'w') as upload_lock_file:
            #     file_parts_upload_progress.write(upload_lock_file)

            return False

        # Seems that file was successfully uploaded (all parts was)
        # Now sending file upload_end status to server.
        # Server will check storage and return file upload status

        headers = {"Authorization": "Token %s" % self.auth_token}
        data = dict(
            sha1_array=[item['sha1'] for item in part_upload_results],
            file_id=upload_data['file_id']
        )
        r = requests.post(url=upload_data['upload_end_url'], data=data, headers=headers)
        resp = r.json()

        print(resp)

        if resp['success']:
            os.remove(self.file_path)
            # os.remove(self.file_path + ".lock")

        return resp['success']

    def _upload_small_file(self):
        try:
            data = self.data
            data['size'] = self.file_size
            data['hash'] = self.file_hash

            data['hash_method'] = 'sha1'
            data['file_name'] = ntpath.basename(self.file_path)

            headers = {"Authorization": "Token %s" % self.auth_token}
            fl = open(self.file_path, 'r')
            next(fl)
            # fl_data = fl.read()
            # print(fl_data)
            # return
            files = {'file': fl}

            r = requests.post(self.api_host + "/api/upload_small_file", data=data, files=files, headers=headers)

            if r.status_code != 200:
                raise self.UploadException(
                    "Host responded with code %s\r\nResponse body:\r\n%s" % (str(r.status_code), r.text))

            return r.json()['success']
        except requests.RequestException as ex:
            raise self.UploadException("Host is unreachable.")

    def _get_uploaded_parts(self, file_id):
        try:
            data = self.data
            data['file_id'] = str(file_id)

            headers = {"Authorization": "Token %s" % self.auth_token}

            r = requests.post(self.api_host + "/api/upload_large_file/get_parts", data=data, headers=headers)
            resp = r.json()
            print(r.text)

            if not resp['success']:
                raise self.UploadException(
                    "Host responded with code %s\r\nResponse body:\r\n%s" % (str(r.status_code), r.text))

            return resp['response']['parts']
        except requests.RequestException as ex:
            raise self.UploadException("Host is unreachable.")

    def _prepare_file(self):
        try:
            data = self.data
            data['size'] = self.file_size
            data['hash'] = self.file_hash
            data['hash_method'] = 'sha1'
            data['file_name'] = ntpath.basename(self.file_path)
            data['threads_count'] = self.threads_count

            headers = {"Authorization": "Token %s" % self.auth_token}

            r = requests.post(self.api_host + "/api/upload_large_file/start", data=data, headers=headers)

            if r.status_code != 200:
                raise self.UploadException("Host responded with code %s\r\nResponse body:\r\n%s" % (str(r.status_code), r.text))

            return r.json()['response']
        except requests.RequestException as ex:
            raise self.UploadException("Host is unreachable.")


def get_parts(file_size, part_count, start_part_number=1, chunk_size=1024 * 1024 * 10):
    chunk_start = chunk_size * start_part_number
    # chunk_size = 1024 * 1024 * 10# 0x20000  # 131072 bytes, default max ssl buffer size

    part_number = start_part_number
    while chunk_start + chunk_size < file_size and (part_count is not None and part_number < start_part_number + part_count):
        yield(part_number, chunk_start, chunk_size)
        chunk_start += chunk_size
        part_number += 1

    final_chunk_size = file_size - chunk_start
    yield(part_number, chunk_start, final_chunk_size)


def parts_array_uploader(upload_url, upload_token, file_path, file_size, parts_uploaded,
                         part_start, part_count, chunk_size, part_upload_results):
    file = open(file_path, 'rb')
    print("(part_start - 1) * chunk_size == ", (part_start - 1) * chunk_size, "    ||   ", part_start, chunk_size)
    file.seek((part_start - 1) * chunk_size)

    if part_start == 1:
        # skip the header row at start of the file
        next(file)

    for part_number, chunk_start, chunk_size in get_parts(file_size=file_size, start_part_number=part_start,
                                                          part_count=part_count, chunk_size=chunk_size):

        part_number_str = str(part_number)
        if part_number_str in parts_uploaded:
            res = dict(part_number=part_number_str, sha1=parts_uploaded[part_number_str])
            print("already uploaded", res)
            part_upload_results.put(res)
            continue

        file_chunk = file.read(chunk_size)

        hasher = hashlib.sha1()
        hasher.update(file_chunk)
        sha1_str = hasher.hexdigest()

        try:
            data = b2_upload_part(upload_url=upload_url, upload_file=file_chunk, upload_token=upload_token, part_number=part_number,
                           content_length=chunk_size, sha1=sha1_str, stream=False)

            part_upload_results.put(dict(part_number=part_number, sha1=data['contentSha1']))
        except Exception as ex:
            print("\r\n\t")
            print("error during upload", ex)
            print("\r\n\t")
            part_upload_results.put(dict(error=ex))

    return True


def large_file_uploader(upload_url_array, file_path, parts_uploaded={}, chunk_size=1024 * 1024 * 10):
    file_size = os.path.getsize(file_path)
    threads_count = len(upload_url_array)

    print("file_size, chunk_size", file_size, chunk_size)
    parts, remainder = divmod(file_size, chunk_size)
    print("parts, remainder", parts, remainder)

    parts_per_thread = parts // threads_count
    parts_reminder = parts % threads_count

    print("parts_per_thread, parts_reminder", parts_per_thread, parts_reminder)

    part_upload_results = queue.Queue()
    threads_data = []
    # len(upload_url_array) == threads_count
    part_start = 1
    for upload_url_data in upload_url_array:
        threads_data.append(dict(
            part_start=part_start,
            part_count=parts_per_thread,
            parts_uploaded=parts_uploaded,
            upload_url=upload_url_data['url'],
            upload_token=upload_url_data['token'],
            file_path=file_path,
            file_size=file_size,
            chunk_size=chunk_size,
            part_upload_results=part_upload_results
        ))

        part_start += parts_per_thread

    threads_data[0]['part_start'] = 1
    # threads_count > parts_reminder : always True (because - parts_reminder = parts % threads_count)
    for i in range(0, parts_reminder):
        threads_data[i]['part_count'] += 1
        threads_data[i + 1]['part_start'] = threads_data[i]['part_start'] + threads_data[i]['part_count'] + 1

    if remainder != 0:
        threads_data[-1]['part_count'] += 1

    print("====threads_data====")

    for item in threads_data:
        keys = ['part_start', 'part_count']
        new_item = {}
        for key in keys:
            new_item[key] = item[key]
        print(new_item)

    threads = []
    for t_data in threads_data:
        t = threading.Thread(target=parts_array_uploader, kwargs=t_data)
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    upload_success = True
    part_upload_results_arr = []
    while not part_upload_results.empty():
        res = part_upload_results.get()
        part_upload_results_arr.append(res)
        if 'sha1' not in res:
            upload_success = False
            print(res['error'])

    print(part_upload_results_arr)

    part_upload_results_arr = sorted(part_upload_results_arr, key=lambda x: int(x['part_number']))

    return upload_success, part_upload_results_arr


def b2_upload_part(upload_url, upload_file, upload_token, part_number, content_length, sha1, stream=False, retries=3):
    headers = {
        "Authorization": upload_token,
        "X-Bz-Part-Number": str(part_number),
        "Content-Length": str(content_length),
        "X-Bz-Content-Sha1": sha1,
    }

    # if stream=True supplied then file should be generator function
    for i in range(0, retries):
        try:
            resp = _make_request(upload_url, data=upload_file() if stream else upload_file, headers=headers)
            return resp
        except BackblazeAPIException as ex:
            print("got en Exception. Retry №%s" % str(i), " || ", ex)

    # If there would be an error in API response it will be raised at _make_request
    # return True


def _make_request(url, data, headers):
    print("making request")
    print("url ->", url)
    r = requests.post(url, data=data, headers=headers)
    resp = r.json()

    print(r.status_code, "->", resp)

    if r.status_code != 200:
        raise BackblazeAPIException(**resp)

    return resp

