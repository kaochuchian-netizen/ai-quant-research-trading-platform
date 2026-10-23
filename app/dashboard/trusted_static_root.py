"""Pinned correction-publication root. One explicit alias, no descendant links.

No implicit trust discovery. Public filesystem operations are relative to held
O_DIRECTORY/O_NOFOLLOW descriptors, never a previously resolved string path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

VERSION = 'correction_static_root_trust_v1'
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def identity(st):
    return {'device': st.st_dev, 'inode': st.st_ino, 'uid': st.st_uid}


def absolute(path):
    raw = os.fspath(path)
    if not raw.startswith('/') or '..' in raw.split('/'):
        raise ValueError('CORRECTION_PATH_TRAVERSAL')
    return Path(raw)


def parts(relative):
    raw = os.fspath(relative)
    if not raw or raw.startswith('/') or any(p in ('', '.', '..') for p in raw.split('/')):
        raise ValueError('CORRECTION_PATH_TRAVERSAL')
    return raw.split('/')


def _walk(path):
    """Return a directory fd and every traversed identity; caller closes fd."""
    path = absolute(path)
    fd = os.open('/', DIR_FLAGS)
    seen = {'/': identity(os.fstat(fd))}
    current = Path('/')
    try:
        for name in path.parts[1:]:
            new = os.open(name, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
            current /= name
            seen[str(current)] = identity(os.fstat(fd))
        return fd, seen
    except BaseException:
        os.close(fd)
        raise


def load_policy(path):
    path = absolute(path)
    parent, _ = _walk(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd) as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid not in (0, os.geteuid()) or st.st_mode & 0o022:
                raise ValueError('CORRECTION_TRUST_CONFIG_PERMISSIONS')
            value = json.load(stream)
    finally:
        os.close(parent)
    return value


class StaticRoot:
    def __init__(self, logical, policy=None):
        self.logical = absolute(logical)
        self.policy = policy
        self.fds = []
        self.pins = {}
        self.alias_pin = None

    def __enter__(self):
        try:
            return self._enter()
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _enter(self):
        if self.policy is None:
            self.physical = self.logical
        else:
            p = self.policy
            required = {'schema_version','logical_root','physical_root','alias_identity','root_identity'}
            if not isinstance(p, dict) or set(p) != required or p['schema_version'] != VERSION:
                raise ValueError('CORRECTION_TRUST_CONFIG_SCHEMA')
            for key in ('alias_identity','root_identity'):
                if not isinstance(p[key],dict) or set(p[key]) != {'device','inode','uid'} or any(type(v) is not int or v < 0 for v in p[key].values()):
                    raise ValueError('CORRECTION_TRUST_CONFIG_IDENTITY')
            if absolute(p['logical_root']) != self.logical:
                raise ValueError('CORRECTION_ROOT_ALLOWLIST_MISMATCH')
            self.physical = absolute(p['physical_root'])
            if self.logical == self.physical:
                raise ValueError('CORRECTION_ROOT_ALLOWLIST_MISMATCH')
            parent, pins = _walk(self.logical.parent)
            self.fds.append(parent)
            self.pins.update(pins)
            st = os.stat(self.logical.name,dir_fd=parent,follow_symlinks=False)
            if not stat.S_ISLNK(st.st_mode) or identity(st) != p['alias_identity'] or os.readlink(self.logical.name,dir_fd=parent) != str(self.physical):
                raise ValueError('CORRECTION_ROOT_ALIAS_MISMATCH')
            self.alias_pin = identity(st)
        fd,pins = _walk(self.physical)
        self.fds.append(fd)
        self.fd = fd
        self.pins.update(pins)
        if self.policy and identity(os.fstat(fd)) != self.policy['root_identity']:
            raise ValueError('CORRECTION_ROOT_IDENTITY_MISMATCH')
        self.check()
        return self

    def __exit__(self, *args):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()

    def check(self):
        """Abort if root, alias or any opened directory name changed."""
        for path,pinned in self.pins.items():
            fd,_ = _walk(Path(path))
            try:
                if identity(os.fstat(fd)) != pinned:
                    raise ValueError('CORRECTION_ROOT_OR_DIRECTORY_REPLACED')
            finally:
                os.close(fd)
        if self.alias_pin is not None:
            fd,_ = _walk(self.logical.parent)
            try:
                st=os.stat(self.logical.name,dir_fd=fd,follow_symlinks=False)
                if identity(st) != self.alias_pin or not stat.S_ISLNK(st.st_mode) or os.readlink(self.logical.name,dir_fd=fd) != str(self.physical):
                    raise ValueError('CORRECTION_ROOT_ALIAS_REPLACED')
            finally:
                os.close(fd)

    def directory(self, relative, *, create=False):
        names=parts(relative)
        fd=self.fd
        current=self.physical
        if os.fstat(fd).st_mode & 0o005 != 0o005:
            raise ValueError('CORRECTION_PUBLIC_DIRECTORY_MODE')
        for name in names:
            current /= name
            self.check()
            created=False
            if create:
                try:
                    os.mkdir(name,mode=0o755,dir_fd=fd)
                    created=True
                    os.fsync(fd)
                except FileExistsError:
                    pass
            child=os.open(name,DIR_FLAGS,dir_fd=fd)
            self.fds.append(child)
            if created:
                os.fchmod(child,0o755)
            if os.fstat(child).st_mode & 0o005 != 0o005:
                raise ValueError('CORRECTION_PUBLIC_DIRECTORY_MODE')
            key=str(current); pin=identity(os.fstat(child))
            if key in self.pins and self.pins[key] != pin:
                raise ValueError('CORRECTION_ROOT_OR_DIRECTORY_REPLACED')
            self.pins[key]=pin
            fd=child
        self.check()
        return fd

    def relative(self, path):
        """Translate only within the configured logical/physical root."""
        path=absolute(path)
        for root in (self.logical,self.physical):
            try:
                value=path.relative_to(root).as_posix()
            except ValueError:
                continue
            parts(value)
            return value
        return None

    def read(self, relative):
        names=parts(relative)
        parent=self.directory('/'.join(names[:-1])) if len(names)>1 else self.fd
        return read_at(parent,names[-1])


def read_at(parent,name):
    if len(parts(name)) != 1:
        raise ValueError('CORRECTION_PATH_TRAVERSAL')
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('CORRECTION_NONREGULAR_FILE')
        return stream.read()


def stat_at(parent,name):
    if len(parts(name)) != 1:
        raise ValueError('CORRECTION_PATH_TRAVERSAL')
    try:
        st=os.stat(name,dir_fd=parent,follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        raise ValueError('CORRECTION_SYMLINK_OR_NONREGULAR')
    return st
