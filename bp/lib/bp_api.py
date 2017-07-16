import requests


class BPAPI(object):
    auth_token = None
    api_postfix = "api"

    class BPAPIException(Exception):
        pass

    def __init__(self, host, auth_token):
        self.auth_token = auth_token
        self.host = host

    # def project_list(self):
    #     pass
    #
    # def origin_list(self, project_name):
    #     return self._make_request('GET', 'origins', )
    def get_download_url(self, file_id):
        return self._make_request('get', 'download/%s' % file_id)

    def file_list(self, project_name, origin_name=None):
        params = dict(project=project_name)

        if origin_name is not None:
            params['origin'] = origin_name

        return self._make_request('get', 'files', params=params)

    def _get_endpoint(self, api_method_name):
        return "%s/%s/%s/" % (self.host, self.api_postfix, api_method_name)

    def _make_request(self, method, api_method_name, params={}, data={}):
        if not hasattr(requests, method):
            raise self.BPAPIException("There is no method name '%s'" % method)

        headers = {"Authorization": "Token %s" % self.auth_token}

        r = getattr(requests, method)(self._get_endpoint(api_method_name), params=params, data=data, headers=headers)

        return r.json()

