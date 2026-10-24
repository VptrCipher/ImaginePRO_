"""Owner-only Windows DPAPI storage for server credentials; env vars elsewhere."""
import ctypes
import os
from ctypes import wintypes
from .config import STORAGE


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value, decrypt=False):
    if os.name!='nt':
        raise RuntimeError('Use a server environment variable for credentials on this platform')
    buffer=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob()
    crypt=ctypes.windll.crypt32
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise RuntimeError('Unable to access the local credential store')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(target.data,ctypes.c_void_p))


def set_agenticorg_key(value):
    directory=STORAGE/'secrets'
    directory.mkdir(exist_ok=True)
    (directory/'agenticorg.dpapi').write_bytes(_crypt(value.encode('utf-8')))


def agenticorg_key():
    value=os.environ.get('AGENTICORG_API_KEY','').strip()
    if value:return value
    path=STORAGE/'secrets/agenticorg.dpapi'
    return _crypt(path.read_bytes(),decrypt=True).decode('utf-8') if path.exists() else ''
