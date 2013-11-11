# coding=utf-8
import hashlib
from datetime import datetime, timedelta
import requests


class Storage(object):
    def update_expired(fn):
        def wrapper(*args, **kwargs):
            auth = args[0].auth
            if auth.expired():
                args[0].authenticate()
            return fn(*args, **kwargs)
        return wrapper

    class Auth(object):
        THRESHOLD = 300

        def __init__(self, token, storage, expires):
            self.token = token
            self.storage = storage
            self.expires = datetime.now() + timedelta(seconds=int(expires))

        def expired(self):
            left = datetime.now() - self.expires
            return (left.total_seconds() < self.THRESHOLD)

    def __init__(self, user, key):
        self.url = "https://auth.selcdn.ru/"
        self.user = user
        self.key = key
        self.authenticate()

    def authenticate(self):
        headers = {"X-Auth-User": self.user, "X-Auth-Key": self.key}
        r = requests.get(self.url, headers=headers, verify=True)
        if r.status_code != 204:
            raise Exception("Selectel: Unexpected status code: " +
                            r.status_code)
        auth = self.Auth(r.headers["X-Auth-Token"],
                         r.headers["X-Storage-Url"],
                         r.headers["X-Expire-Auth-Token"])
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": self.auth.token})

    @update_expired
    def list(self, container, path):
        url = "%s%s/" % (self.auth.storage, container)
        params = {"format": "json", "path": path}
        r = self.session.get(url, params=params, verify=True)
        r.raise_for_status()
        return {x["name"]: x for x in r.json()}

    @update_expired
    def get(self, container, path, headers=None):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        if headers is None:
            headers = {}
        r = self.session.get(url, headers=headers, verify=True)
        r.raise_for_status()
        return (r.content, r.headers)

    @update_expired
    def get_stream(self, container, path, headers=None, chunk=2**20):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        if headers is None:
            headers = {}
        r = self.session.get(url, headers=headers, stream=True, verify=True)
        r.raise_for_status()
        return (r.headers, r.iter_content(chunk_size=chunk))

    @update_expired
    def put(self, container, path, content, headers=None):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        if headers is None:
            headers = {}
        headers["ETag"] = hashlib.md5(content).hexdigest()
        r = self.session.put(url, data=content, headers=headers, verify=True)
        r.raise_for_status()
        return r.headers

    @update_expired
    def save_stream(self, container, path, descriptor,
                    headers=None, chunk=2**20):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        if headers is None:
            headers = {}

        def gen():
            data = descriptor.read(chunk)
            while data:
                yield data
                data = descriptor.read(chunk)

        r = self.session.put(url, data=gen(), headers=headers, verify=True)
        r.raise_for_status()
        return r.headers

    @update_expired
    def save_file(self, container, path, filename, headers=None):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        if headers is None:
            headers = {}
        with open(filename, 'r+b') as file:
            r = self.session.put(url, data=file, headers=headers, verify=True)
            r.raise_for_status()
            return r.headers

    @update_expired
    def remove(self, container, path, force=False):
        url = "%s%s/%s" % (self.auth.storage, container, path)
        r = self.session.delete(url, verify=True)
        if force:
            if r.status_code == 404:
                return r.headers
            else:
                r.raise_for_status()
        else:
            r.raise_for_status()
        return r.headers

    @update_expired
    def copy(self, container, src, dst, headers=None):
        dst = "%s%s/%s" % (self.auth.storage, container, dst)
        src = "%s/%s" % (container, src)
        if headers is None:
            headers = {}
        headers["X-Copy-From"] = src
        r = self.session.put(dst, headers=headers, verify=True)
        r.raise_for_status()
        return r.headers
