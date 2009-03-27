#!/usr/bin/python

import os
import re
from SocketServer import *
import signal
import sys

import auth
import client
import command
import editor
import report
import socket

import generate as gen
from config import config
from errors import *

addr_family = socket.AF_INET
all_interfaces = "0.0.0.0"
if socket.has_ipv6:
    addr_family = socket.AF_INET6
    all_interfaces = "::"

MAX_DBG_MLEN = 1000
verbose = False

ipv4_re = re.compile(r'\d{1,3}(\.\d{1,3}){3,3}')
def is_ipv4_addr(ip):
    return ipv4_re.match(ip) is not None

class SvnServer(ForkingTCPServer):
    address_family = addr_family
    allow_reuse_address = True
    def __init__(self, log=None, ip=None, port=3690):
        self.log = log
        if ip is None:
            ip = all_interfaces
        elif socket.has_ipv6 and is_ipv4_addr(ip):
            ip = '::ffff:%s' % ip
        if socket.has_ipv6:
            address = (ip, port, 0, 0)
        else:
            address = (ip, port)
        ForkingTCPServer.__init__(self, address, SvnRequestHandler)

    def start(self, foreground=False, debug=False):
        if debug:
            self.log = None

        if foreground or debug:
            return self.run()

        if os.fork() == 0:
            self.run()
            os._exit(0)

    def stop(self, *args):
        print 'stopped serving'
        if self.log is not None:
            sys.stdout.flush()
            sys.stdout.close()
        sys.exit(0)

    def run(self):
        signal.signal(signal.SIGTERM, self.stop)

        if self.log is not None:
            sys.stdout = open(self.log, 'a')
            sys.stderr = sys.stdout

        print 'start serving'

        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass

        print 'stopped serving'

        if self.log is not None:
            sys.stdout.flush()
            sys.stdout.close()


class SvnRequestHandler(StreamRequestHandler):
    def __init__(self, request, client_address, server):
        self.mode = 'connect'
        self.client_caps = None
        self.repos = None
        self.auth = None
        self.data = None
        self.url = None
        self.command = None
        if server.log is not None:
            sys.stdout = open(server.log, 'a')
            sys.stderr = sys.stdout
        StreamRequestHandler.__init__(self, request, client_address, server)

    def set_mode(self, mode):
        if mode not in ['connect', 'auth', 'announce',
                        'command', 'editor', 'report']:
            raise ModeError("Unknown mode '%s'" % mode)

        self.mode = mode

    def read_msg(self):
        t = self.rfile.read(1)

        while t in [' ', '\n', '\r']:
            t = self.rfile.read(1)

        if len(t) == 0:
            raise EOF()

        if t != '(':
            raise ReadError(t)

        depth = 1

        while depth > 0:
            ch = self.rfile.read(1)

            if ch == '(':
                depth += 1

            if ch == ')':
                depth -= 1

            t += ch

        debug('%d<%s' % (os.getpid(), t))
        return t

    def read(self, count):
        data = ''

        while len(data) < count:
            s = self.rfile.read(count - len(data))

            if len(s) == 0:
                raise EOF

            data += s

        debug('%d<%s' % (os.getpid(), data))
        return data

    def read_str(self):
        ch = self.rfile.read(1)

        if len(ch) == 0:
            raise EOF

        l = ""
        while ch not in [':', '']:
            l += ch
            ch = self.rfile.read(1)

        bytes = int(l)
        data = ''

        while len(data) < bytes:
            s = self.rfile.read(bytes - len(data))

            if len(s) == 0:
                raise EOF

            data += s

        debug('%d<%s' % (os.getpid(), data))
        return data

    def send(self, msg):
        debug('%d>%s' % (os.getpid(), msg))
        self.wfile.write('%s' % msg)
        self.wfile.flush()

    def send_msg(self, msg):
        self.send('%s\n' % msg)

    def send_server_id(self):
        self.send_msg(gen.success(gen.string(self.repos.get_uuid()),
                                  gen.string(self.repos.get_base_url())))

    def handle(self):
        sys.stderr.write('%d: -- NEW CONNECTION --\n' % os.getpid())
        try:
            while True:
                sys.stdout.flush()
                try:
                    if self.mode == 'connect':
                        self.url, self.client_caps, self.repos = \
                                  client.connect(self)

                        if self.client_caps is None or self.repos is None:
                            return

                        self.mode = 'auth'

                    elif self.mode == 'auth':
                        if self.auth is None:
                            self.auth = auth.auth(self)
                            self.repos.set_username(self.auth.username)
                            self.mode = 'announce'
                        else:
                            self.auth.reauth()
                            self.repos.set_username(self.auth.username)
                            self.mode = self.data

                        if self.auth is None:
                            return

                    elif self.mode == 'announce':
                        self.send_server_id()
                        self.mode = 'command'

                    elif self.mode == 'command':
                        if self.command is None:
                            self.command = command.process(self)
                        else:
                            self.command = self.command.process()

                    elif self.mode == 'editor':
                        editor.process(self)

                    elif self.mode == 'report':
                        report.process(self)

                    else:
                        raise ModeError("unknown mode '%s'" % self.mode)

                except ChangeMode, cm:
                    self.mode = cm.args[0]
                    if len(cm.args) > 1:
                        self.data = cm.args[1]
        except EOF:
            msg = 'EOF'
        except socket.error, e:
            errno, msg = e
        sys.stderr.write('%d: -- CLOSE CONNECTION (%s) --\n' %
                         (os.getpid(), msg))
        sys.stderr.flush()


def debug(msg):
    if not verbose:
        return
    if len(msg) > MAX_DBG_MLEN:
        sys.stderr.write('%s...\n' % (msg[:MAX_DBG_MLEN]))
    else:
        sys.stderr.write('%s\n' % (msg))


def main():
    config.load('test.cfg')

    server = SvnServer((all_interfaces, 3690))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
