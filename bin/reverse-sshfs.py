#!/usr/bin/env python3
import subprocess
import sys
import threading
import struct
import enum

# from https://tools.ietf.org/html/draft-ietf-secsh-filexfer-13
class SFTPCommand(enum.Enum):
    SSH_FXP_INIT = 1
    SSH_FXP_VERSION = 2
    SSH_FXP_OPEN = 3
    SSH_FXP_CLOSE = 4
    SSH_FXP_READ = 5
    SSH_FXP_WRITE = 6
    SSH_FXP_LSTAT = 7
    SSH_FXP_FSTAT = 8
    SSH_FXP_SETSTAT = 9
    SSH_FXP_FSETSTAT = 10
    SSH_FXP_OPENDIR = 11
    SSH_FXP_READDIR = 12
    SSH_FXP_REMOVE = 13
    SSH_FXP_MKDIR = 14
    SSH_FXP_RMDIR = 15
    SSH_FXP_REALPATH = 16
    SSH_FXP_STAT = 17
    SSH_FXP_RENAME = 18
    SSH_FXP_READLINK = 19
    SSH_FXP_SYMLINK = 20 # removed but some implementations still using this
    SSH_FXP_LINK = 21
    SSH_FXP_BLOCK = 22
    SSH_FXP_UNBLOCK = 23
    # ---
    SSH_FXP_STATUS = 101
    SSH_FXP_HANDLE = 102
    SSH_FXP_DATA = 103
    SSH_FXP_NAME = 104
    SSH_FXP_ATTRS = 105
    # ---
    SSH_FXP_EXTENDED = 200
    SSH_FXP_EXTENDED_REPLY = 201

    def includes_file_path(self):
        if self in [
            self.SSH_FXP_RENAME,
            self.SSH_FXP_SYMLINK,
            self.SSH_FXP_LINK,
        ]:
            return 2
        elif self in [
            self.SSH_FXP_OPEN,
            self.SSH_FXP_LSTAT,
            self.SSH_FXP_FSTAT,
            self.SSH_FXP_SETSTAT,
            self.SSH_FXP_FSETSTAT,
            self.SSH_FXP_OPENDIR,
            self.SSH_FXP_REMOVE,
            self.SSH_FXP_MKDIR,
            self.SSH_FXP_RMDIR,
            self.SSH_FXP_STAT,
            self.SSH_FXP_READLINK,
        ]:
            return 1
        elif self in [
            self.SSH_FXP_INIT,
            self.SSH_FXP_CLOSE,
            self.SSH_FXP_READ,
            self.SSH_FXP_WRITE,
            self.SSH_FXP_READDIR,
        ]:
            return 0
        else:
            print("Unknown", self)
            return 0

local_path, remote_host, remote_path = sys.argv[1:]

pserver = subprocess.Popen(["/usr/libexec/sftp-server"], cwd=local_path, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=sys.stderr)
pclient = subprocess.Popen(["ssh", remote_host, "sshfs", ":", remote_path, "-o", "slave"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=sys.stderr)

def is_acceptable_path(path: str):
    # TODO: replace with more better logic
    acceptable = not (path.startswith("/") or ("../" in path) or path.endswith(".."))
    if not acceptable:
        print("Denied", path)
    return acceptable

def filter_c2s():
    print("watching c2s...")
    try:
        while True:
            phead_format = ">IBI"
            phead_len = struct.calcsize(phead_format)
            phead = pclient.stdout.read(phead_len)
            plen, ptype, pid = struct.unpack_from(phead_format, phead)
            d = pclient.stdout.read(plen + 4 - phead_len)
            already_handled = False
            path_count = SFTPCommand(ptype).includes_file_path()
            should_accept = True
            if path_count == 1:
                path_len = struct.unpack_from(">I", d[0:4])[0]
                path = d[4:4+path_len].decode("UTF-8")
                should_accept = is_acceptable_path(path)
            elif path_count == 2:
                path1_len = struct.unpack_from(">I", d[0:4])[0]
                path1 = d[4:4+path1_len]
                d2 = d[4+path1_len:]
                path2_len = struct.unpack_from(">I", d2[0:4])[0]
                path2 = d2[4:4+path2_len]
            if not should_accept:
                already_handled = True
                msg = "Permission Denied".encode("UTF-8")
                payload = struct.pack(">BIII", SFTPCommand.SSH_FXP_STATUS.value, pid, 2, len(msg)) + msg + struct.pack(">I", 0)
                print(payload)
                pclient.stdin.write(struct.pack(">I", len(payload)))
                pclient.stdin.write(payload)
                pclient.stdin.flush()
            else:
                # print("c2s request", SFTPCommand(ptype))
                # print("c2s", plen, ptype, pid, phead, d)
                pass
            if not already_handled:
                pserver.stdin.write(phead)
                pserver.stdin.write(d)
                pserver.stdin.flush()
    finally:
        pserver.stdin.close()
t1 = threading.Thread(target=filter_c2s)
t1.start()

def filter_s2c():
    print("watching s2c...")
    try:
        while True:
            phead_format = ">IBI"
            phead_len = struct.calcsize(phead_format)
            phead = pserver.stdout.read(phead_len)
            plen, ptype, pid = struct.unpack_from(phead_format, phead)
            d = pserver.stdout.read(plen + 4 - phead_len)
            pclient.stdin.write(phead + d)
            pclient.stdin.flush()
    finally:
        pclient.stdin.close()
t2 = threading.Thread(target=filter_s2c)
t2.start()

try:
    pserver.wait()
    pclient.wait()
finally:
    pserver.terminate()
    pclient.terminate()
