from werkzeug.wrappers.request import Request as WerkzeugRequest

_original_url_root = WerkzeugRequest.url_root.fget

def patched_url_root(self):
    return _original_url_root(self).replace("http://", "https://")

WerkzeugRequest.url_root = property(patched_url_root)
