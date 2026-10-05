"""Linux workers must finish and wait for all processes they create.

A subreaper keeps orphaned descendants observable, including completed
double-fork children. Detached or unwaited processes are unsupported and
cannot produce a successful resource receipt.
"""
import ctypes
import os
from pathlib import Path


def subreaper_enabled():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    value = ctypes.c_int()
    pointer = ctypes.cast(ctypes.byref(value), ctypes.c_void_p).value
    if libc.prctl(37, pointer, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_GET_CHILD_SUBREAPER failed')
    return value.value == 1


def enable_subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(36, 1, 0, 0, 0) != 0 or not subreaper_enabled():
        raise RuntimeError('observable Linux child-subreaper required')


def direct_children():
    children = set()
    tasks = list(Path('/proc/self/task').glob('[0-9]*'))
    if not tasks:
        raise RuntimeError('process task children must be observable')
    for task in tasks:
        try:
            values = (task / 'children').read_text().split()
        except FileNotFoundError:
            if not task.exists():
                continue  # A worker thread can finish during enumeration.
            raise
        if any(not item.isdecimal() or int(item) <= 0 for item in values):
            raise RuntimeError('malformed process child inventory')
        children.update(map(int, values))
    return sorted(children)


def completed_lifecycle():
    children = direct_children()
    if not subreaper_enabled() or children:
        raise RuntimeError(f'unwaited worker descendants prevent admission: {children}')
    return {'subreaper_verified': True, 'remaining_children': [],
            'contract': 'all created descendants completed and waited; detached children unsupported'}
