from __future__ import division

from .api_client import get_client

import os, hashlib, requests
import ntpath
import threading
try:
    import queue
except ImportError:
    import Queue as queue


class BKP_SDK(object):
    hash_method = "md5"

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

    def __init__(self, host, token, port=80):
        self.client = get_client(host, token, 'v1', port)

    def upload(self, project_name, origin_name, file_path, file_hash=None, file_name=None):
        init_data = self._prepare_init_data(project_name, origin_name, file_path, file_hash, file_name)
        upload_data = self._init_upload(init_data)

        if upload_data['in_storage']:
            # File already uploaded
            return True

        upload_url = upload_data['upload_urls'][0]
        file_id = upload_data['file_id']

        results = queue.Queue()

        t = threading.Thread(target=upload_worker__stream, args=(results, file_path, init_data['size'], upload_url))
        t.daemon = True
        t.start()
        t.join()

        upload_success = True
        while not results.empty():
            if not results.get():
                upload_success = False

        if not upload_success:
            self.upload_close(file_id)
            raise self.UploadException("Upload was failed. Probably due the internet connection problems or "
                                       "API server maintenance.")

        resp = self.client.file.file_upload_end(id=file_id).result()

        if 'error_code' in resp:
            raise self.UploadException("Error code - %d: %s" % (resp['error_code'], resp['error_message']))

        return True

    def _prepare_init_data(self, project_name, origin_name, file_path, file_hash, file_name=None):
        if file_name is None:
            file_name = ntpath.basename(file_path)

        if file_hash is None:
            file_hash = get_file_hash(file_path, self.hash_method)

        return dict(
            project=project_name,
            origin=origin_name,
            size=os.path.getsize(file_path),
            hash=file_hash,
            file_name=file_name
        )


    def _init_upload(self, init_data):
        upload_data = self.client.file.file_create(**init_data).result()

        if 'error_code' in upload_data:
            code = int(upload_data['error_code'])

            if code in self.success_error_codes:
                return True

            if code in self.abort_error_codes:
                raise self.AbortException(upload_data['error_message'])

            raise self.UploadException(upload_data['error_message'])

        return upload_data



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


def get_file_hash(file_path, hash_method):
    hasher = getattr(hashlib, hash_method)()
    f = open(file_path, "rb")
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        hasher.update(chunk)
    return hasher.hexdigest()