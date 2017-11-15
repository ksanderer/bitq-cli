# chunked file reading
from __future__ import division
import os, hashlib, requests
import ntpath
import threading
try:
    import queue
except ImportError:
    import Queue as queue
import json


# def get_chunks(file_size, start_byte, chunk_size=1024 * 1024 * 10):
#     chunk_start = start_byte
#     # chunk_size = 1024 * 1024 * 10# 0x20000  # 131072 bytes, default max ssl buffer size
#     while chunk_start + chunk_size < file_size:
#         yield(chunk_start, chunk_size)
#         chunk_start += chunk_size
#
#     final_chunk_size = file_size - chunk_start
#     yield(chunk_start, final_chunk_size)
#
#
# def file_streamer(file_path, file_size, start_byte):
#     with open(file_path, 'rb') as file_:
#         mb = 1024 * 1024
#         max_chunk_size = mb * 100
#
#         for chunk_start, chunk_size in get_chunks(file_size, start_byte, max_chunk_size):
#             yield file_.read(chunk_size)


def upload_worker__stream(result, file_path, file_size, upload_url):
    headers = {
        "Content-Length": "0",
        "Content-Range": "bytes */%s" % file_size,
    }

    r = requests.put(url=upload_url, headers=headers)

    if r.status_code == 308:
        if "Range" in r.headers:
            start_byte = r.headers['Range']
            start_byte = int(start_byte.split("-")[1]) + 1
        else:
            start_byte = 0
    else:
        if r.status_code == 200 or r.status_code == 201:
            result.put(True)
            return

        # print("Wrong status code on upload.", r.status_code, r.headers)
        result.put(False)
        return

    headers = {
        "Content-Length": str(file_size - start_byte),
        "Content-Range": "bytes %s-%s/%s" % (start_byte, file_size - 1, file_size)
    }

    file = open(file_path, 'rb')
    file.seek(start_byte)

    r = requests.put(url=upload_url, data=file, headers=headers)
    file.close()

    # print("\r\n\tgcs upload ->", r.text)

    success = (r.status_code == 200 or r.status_code == 201) and 'id' in r.json()
    result.put(success)


class GCSUploader(object):
    # 2 - File you try to upload already exists in storage. Virtual clone was created for timeline transparency.
    success_error_codes = [2]
    # Error codes list when we should abort upload and restart it.
    # 8 - Try to upload file with 0 size.
    abort_error_codes = [8]

    class UploadException(Exception):
        # Exception while uploading file.
        # Means we can resume upload later.
        pass

    class AbortException(Exception):
        # Non resumable upload exception.
        # We need to abort upload and delete file.
        pass

    def __init__(self, file_path, file_hash, data, auth_token, api_host, resume_upload=False):
        self.file_path = file_path
        self.file_hash = file_hash
        self.resume_upload = resume_upload

        self.data = data

        self.hash_method = 'md5'
        self.auth_token = auth_token
        self.api_host = api_host

        self.file_size = os.path.getsize(file_path)

    def upload(self):
        upload_data = self._prepare_file()

        # print("upload_data", upload_data)

        if not upload_data['success']:
            # print(self.UploadException(upload_data['error_message']))
            if 'error_code' in upload_data:
                code = int(upload_data['error_code'])

                if code in self.success_error_codes:
                    return True

                if code in self.abort_error_codes:
                    raise self.AbortException(upload_data['error_message'])

                raise self.UploadException(upload_data['error_message'])

            return False

        upload_url = upload_data['response']['upload_urls'][0]
        upload_end_url = upload_data['response']['upload_end_url']
        file_id = upload_data['response']['file_id']

        results = queue.Queue()

        t = threading.Thread(target=upload_worker__stream, args=(results, self.file_path, self.file_size, upload_url))
        t.daemon = True
        t.start()
        t.join()

        upload_success = True
        while not results.empty():
            if not results.get():
                upload_success = False

        if not upload_success:
            self.upload_close(upload_data['respons']['file_id'])
            raise self.UploadException("Upload was failed. Probably due the internet connection problems or "
                                       "API server maintenance.")
        # else:
        #     os.remove(self.file_path)

        # return True

        data = dict(
            file_id=file_id
        )

        headers = {"Authorization": "Token %s" % self.auth_token}
        r = requests.post(url=upload_end_url, data=data, headers=headers)
        # print(r.text)
        resp = r.json()

        success = resp['success']

        # if success:
        #     os.remove(self.file_path)

        return success

    def _prepare_file(self):
        try:
            data = self.data

            data['size'] = self.file_size
            data['hash'] = self.file_hash
            data['hash_method'] = self.hash_method
            data['file_name'] = ntpath.basename(self.file_path)

            headers = {"Authorization": "Token %s" % self.auth_token}

            r = requests.post(self.api_host + "/api/upload_large_file/start/", data=data, headers=headers)

            if r.status_code != 200:
                raise self.UploadException("Host responded with code %d\r\nResponse body:\r\n%s" % (r.status_code, r.text))

            return r.json()
        except requests.RequestException as ex:
            print("RLY?")
            raise self.UploadException("Host is unreachable.")

    def upload_close(self, file_id):
        headers = {"Authorization": "Token %s" % self.auth_token}
        data = dict(
            file_id=file_id
        )

        r = requests.post(self.api_host + "/api/upload_large_file/close/", data=data, headers=headers)
        return r.json()


def make_api_call(*args, **kwargs):
    return requests.post(*args, **kwargs)


# def get_file_size(file_path):
#     size = os.path.getsize(file_path)
#     f = open(file_path, "r")
#     header = f.readline()
#
#     return size - len(header)


# def file_hash(fname, hash_method):
#     hasher = getattr(hashlib, hash_method)()
#
#     with open(fname, "rb") as f:
#         for chunk in iter(lambda: f.read(4096), b""):
#             hasher.update(chunk)
#     return hasher.hexdigest()

# def file_reader(file_path, file_size, upload_token, upload_url, threads_count, work_request, work_demand, hash_method="md5"):
#     with open(file_path, 'rb') as file_:
#         progress = 0
#
#         mb = 1024 * 1024
#         max_chunk_size = mb * 100
#
#         for chunk_start, chunk_size in get_chunks(file_size, max_chunk_size):
#             # Block thread until chunk request
#             work_request.get()
#             print("work_request.get()")
#             file_chunk = file_.read(chunk_size)
#
#             work_demand.put([file_chunk, dict(
#                 offset=progress,
#                 size=chunk_size,
#                 hash_method=hash_method,
#                 upload_token=upload_token,
#                 upload_url=upload_url,
#                 full_size=file_size
#             )])
#
#             progress += len(file_chunk)
#             # print(chunk_start, chunk_size, progress/file_size)
#
#     for i in range(threads_count):
#         work_demand.put([None, None])
#
#     work_demand.task_done()
#     # print("file_reader - Work done")
#
#
# def upload_worker(work_request, work_demand, result):
#     while True:
#         work_request.put("request")
#         [file_chunk, data] = work_demand.get()
#
#         if file_chunk is None:
#             # print("upload_worker - Work done")
#             work_demand.task_done()
#             break
#
#         hasher = getattr(hashlib, data['hash_method'])()
#         hasher.update(file_chunk)
#         data['hash'] = hasher.hexdigest()
#
#         upload_url = data['upload_url']
#         del data['upload_url']
#
#         print(upload_url, data)
#
#         # headers = {"Authorization": "Token %s" % data['auth_token']}
#         # del data['auth_token']
#
#         # headers = {'content-type': 'application/json'}
#         # headers = {"Content-Type": "application/x-www-form-urlencoded"}
#
#         headers = {
#             "Content-Length": str(data['size']),
#             "Content-Range": "bytes %s-%s/%s" % (
#                 str(data['offset']),
#                 str(data['offset'] + data['size'] - 1),
#                 str(data['full_size'])
#             )
#         }
#
#         print("headers", headers)
#
#         req_number = 0
#         upload_success = False
#         files = dict(chunk=file_chunk)
#
#         chunk_uploaded = False
#         max_retries = 0
#         while not chunk_uploaded and max_retries < 3:
#             r = requests.put(url=upload_url, data=file_chunk, headers=headers)
#             print(req_number, r.status_code, r.headers)
#
#             if r.status_code == 308 and 'Range' in r.headers:
#                 upload_success = True
#                 break
#
#             max_retries += 1
#
#         # while req_number < 3:
#             # print(data)
#             # print("\r\n\r\n")
#             # print(files)
#             # r = requests.post(url=upload_url, data=data, files=files)
#             # r = requests.post(url=upload_url, data=data, files=files, headers=headers)
#             # start = time.time()
#             # r = requests.post(url=upload_url, params=data, files=files)
#             # r = requests.put(url=upload_url, data=file_chunk, headers=headers)
#
#             # print(r.status_code)
#             # resp = r.json()
#
#             # print(req_number, r.status_code, r.headers)
#
#             # try:
#             #     resp = r.json()
#             # except:
#             #     resp = dict(success=False)
#
#             # print("\r\n\r\n", resp)
#
#             # end = time.time()
#             #
#             # print("time", end - start)
#
#             # if resp['success']:
#             #     upload_success = True
#             #     break
#             # else:
#             #     req_number += 1
#
#         result.put(upload_success)