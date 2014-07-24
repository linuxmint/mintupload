#!/usr/bin/env python

# mintUpload
#       Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 3
# of the License.



import sys
import urllib
import ftplib
import os
import datetime
import gettext
import paramiko
import pexpect
import threading
import pynotify
from user import home
sys.path.append('/usr/lib/linuxmint/common')
from configobj import ConfigObj


VERSION = "3.7.4"
__version__ = VERSION

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

class CustomError(Exception):
    '''All custom defined errors'''

    observers = []

    def __init__(self, summary, err=None):
        self.type = self.__class__.__name__
        self.summary = summary
        if err: self.detail = repr(err)
        else:   self.detail = ''
        for observer in self.observers:
            observer.error(self)

    @classmethod
    def addObserver(cls, observer):
        cls.observers.append(observer)


class cliErrorObserver:
    '''All custom defined errors, using stderr'''
    def error(self, err):
        sys.stderr.write(os.linesep + err.type + ': ' + err.summary)
        if err.detail:
            sys.stderr.write(os.linesep + '\tDetail: ' + err.detail)
        sys.stderr.write(os.linesep*2)

CustomError.addObserver(cliErrorObserver())



class ConnectionError(CustomError):
    '''Raised when an error has occured with an external connection'''
    pass



class FilesizeError(CustomError):
    '''Raised when the file is too large or too small'''
    pass



def sizeStr(size, acc=None, factor=None):
    '''Converts integer filesize in bytes to textual repr'''

    if not factor:
        factor = int(config['filesize']['factor'])
    if not acc:
        acc = int(config['filesize']['accuracy'])
    if config['filesize']['binary_units'] == "True":
        thresholds = [_("B"),_("KiB"),_("MiB"),_("GiB")]
    else:
        thresholds = [_("B"),_("KB"),_("MB"),_("GB")]
    size = float(size)
    for i in reversed(range(1,len(thresholds))):
        if size >= factor**i:
            rounded = round(size/factor**i, acc)
            return str(rounded) + thresholds[i]
    return str(int(size)) + thresholds[0]



class mintNotifier:
    '''Enables integration with external notifiers'''
    def __init__(self):
        pynotify.init("mintUpload")

    def notify(self, detail):
        pynotify.Notification("mintUpload", detail, ICONFILE).show()



class mintSpaceChecker(threading.Thread):
    '''Checks that the filesize is ok'''

    def __init__(self, service, filesize):
        threading.Thread.__init__(self)
        self.service = service
        self.filesize = filesize

    def run(self):
        try:
            self.check()
            return True
        except FilesizeError:
            return False

    def check(self):
        # Get the maximum allowed self.filesize on the service
        if self.service.has_key("maxsize"):
            if self.filesize > self.service["maxsize"]:
                raise FilesizeError(_("File larger than service's maximum"))

        # Get the available space left on the service
        if self.service.has_key("space"):
            try:
                spaceInfo = urllib.urlopen(self.service["space"]).read()
                spaceInfo = spaceInfo.split("/")
                self.available = int(spaceInfo[0])
                self.total = int(spaceInfo[1])
            except Exception as e:
                raise ConnectionError(_("Could not get available space"), e)

            if self.filesize > self.available:
                raise FilesizeError(_("File larger than service's available space"))



class mintUploader(threading.Thread):
    '''Uploads the file to the selected service'''

    def __init__(self, service, files):
        threading.Thread.__init__(self)
        service = service.for_upload()
        self.service = service
        self.focused = True
        self.files = files

        # Switch to required connect function, depending on service
        self.uploader = {
                'MINT': self._ftp, # For backwards compatiblity
                'FTP' : self._ftp,
                'SFTP': self._sftp,
                'SCP' : self._scp}[self.service['type']]

    def run(self):
        for f in self.files:
            self.upload(f)
        self.progress( _("File uploaded successfully."))


    def upload(self, file):
        self.name = os.path.basename(file)
        self.filesize = os.path.getsize(file)
        self.uploader(file)
        self.success()

    def _ftp(self, file):
        '''Connection process for FTP services'''

        if not self.service.has_key('port'):
            self.service['port'] = 21
        try:
            # Attempting to connect
            ftp = ftplib.FTP()
            ftp.connect(self.service['host'], self.service['port'])
            ftp.login(self.service['user'], self.service['pass'])
            self.progress(self.service['type'] + " " + _("connection successfully established"))

            # Create full path
            for dir in self.service['path'].split(os.sep):
                try:    ftp.mkd(dir)
                except: pass
                ftp.cwd(dir)

            f = open(file, "rb")
            self.progress(_("Uploading the file..."))
            self.pct(0)
            self.so_far = 0
            ftp.storbinary('STOR ' + self.name, f, 1024, callback=self.my_ftp_callback)

        finally:
            # Close any open connections
            try:    f.close()
            except: pass
            try:    ftp.quit()
            except: pass

    def getPrivateKey(self):
        '''Find a private key in ~/.ssh'''
        key_files = [home + '/.ssh/id_rsa', home + '/.ssh/id_dsa']
        for f in key_files:
            if os.path.exists(f):
                return paramiko.RSAKey.from_private_key_file(f)

    def _sftp(self, file):
        '''Connection process for SFTP services'''

        if not self.service['pass']:
            rsa_key = self.getPrivateKey()
            if not rsa_key: raise ConnectionError(_("This service requires a password or private key."))
        if not self.service.has_key('port'):
            self.service['port'] = 22
        try:
            # Attempting to connect
            transport = paramiko.Transport((self.service['host'], self.service['port']))
            if self.service['pass']:
                transport.connect(username = self.service['user'], password = self.service['pass'])
            else:
                transport.connect(username = self.service['user'], pkey = rsa_key)
            self.progress(self.service['type'] + " " + _("connection successfully established"))

            # Create full remote path
            path = self.service['path']
            try:    transport.open_session().exec_command('mkdir -p ' + path)
            except: pass

            sftp = paramiko.SFTPClient.from_transport(transport)
            self.progress(_("Uploading the file..."))
            self.pct(0)
            sftp.put(file, path + self.name, self.my_sftp_callback)

        finally:
            # Close any open connections
            try:    sftp.close()
            except: pass
            try:    transport.close()
            except: pass

    def _scp(self, file):
        '''Connection process for SCP services'''

        if not self.service.has_key('port'):
            self.service['port'] = 22
        try:
            # Attempting to connect
            self.service['file'] = file
            scp_cmd = "scp -P %(port)i %(file)s %(user)s@%(host)s:%(path)s"%self.service
            scp = pexpect.spawn(scp_cmd)

            # If password is not defined, or is the empty string, use password-less scp
            if self.service['pass']:
                scp.expect('.*password:*')
                scp.sendline(self.service['pass'])

            self.progress(self.service['type'] + " " + _("connection successfully established"))

            scp.timeout = None
            self.pct(0)
            received = scp.expect(['.*100\%.*','.*password:.*',pexpect.EOF])
            if received == 1:
                scp.sendline(' ')
                raise ConnectionError(_("This service requires a password."))

        finally:
            # Close any open connections
            try:    scp.close()
            except: pass

    def progress(self, message):
        print message

    def pct(self, so_far, total=None):
        if not total: total = self.filesize
        if total: pct = float(so_far)/total
        else:     pct = 1.0
        pct = int(pct*100)
        sys.stdout.write("\r " + str(pct) + "% [" + (pct/2)*"=" + ">" + (50-(pct/2)) * " " + "] " + sizeStr(so_far) + "     ")
        sys.stdout.flush()
        return pct

    def success(self):
        self.pct(self.filesize)
        sys.stdout.write("\n")
        # Print URL
        if self.service.has_key('url'):
            url = self.service['url'].replace('<FILE>', self.name)
            self.url = url.replace(' ', '%20')
            self.progress( _("URL:") + " " + self.url)

        n = config['notification']
        # If nofications are enabled AND the file is minimal x byte in size...
        if n['enable'] == "True" and self.filesize >= int(n['min_filesize']):
            # If when_focused is true OR window has no focus
            if n['when_focused'] == "True" or not self.focused:
                mintNotifier().notify(_("File uploaded successfully."))

    def my_ftp_callback(self, buffer):
        self.so_far = self.so_far+len(buffer)-1
        self.pct(self.so_far)
        return

    def my_sftp_callback(self, so_far, total=None):
        return self.pct(so_far, total)


def read_services():
    '''Get all defined services'''

    services = []
    for loc, path in config_paths.iteritems():
        os.system("mkdir -p " + path)
        for file in os.listdir(path):
            try:
                s = Service(path + file)
            except:
                pass
            else:
                s['loc'] = loc
                services.append(s)
    return services


ICONFILE = "/usr/share/linuxmint/mintUpload/icon.svg"
CONFIGFILE_GLOBAL = '/etc/linuxmint/mintUpload.conf'
CONFIGFILE_USER = home + '/.linuxmint/mintUpload.conf'

config = ConfigObj(CONFIGFILE_GLOBAL)
if os.path.exists(CONFIGFILE_USER):
    config.merge(ConfigObj(CONFIGFILE_USER))

if not config.has_key('paths'):
    print _("%(1)s is not set in the config file found under %(2)s or %(3)s") % {'1':'paths', '2':CONFIGFILE_GLOBAL, '3':CONFIGFILE_USER}
    sys.exit(1)

if not config.has_key('defaults'):
    print _("%(1)s is not set in the config file found under %(2)s or %(3)s") % {'1':'defaults', '2':CONFIGFILE_GLOBAL, '3':CONFIGFILE_USER}
    sys.exit(1)

config_paths = config['paths']
config_paths['user'] = config_paths['user'].replace('<HOME>',home)

defaults = config['defaults']
defaults['user'] = defaults['user'].replace('<USER>',os.environ['USER'])



class Service(ConfigObj):
    '''Object representing an upload service'''

    def __init__(self, *args):
        ConfigObj.__init__(self, *args)
        self._fix()

    def merge(self, *args):
        ConfigObj.merge(self, *args)
        self._fix()

    def remove(self):
        os.system("rm '" + self.filename + "'")

    def move(self, newname, force=False):
        if force or not os.path.exists(newname):
            os.system("mv '" + self.filename + "' '" + newname + "'")
            self.filename = newname

    def copy(self, newname, force=False):
        if force or not os.path.exists(newname):
            oldname = self.filename
            self.filename = newname
            self.write()
            self.filename = oldname

    def _fix(self):
        '''Format values correctly'''

        for k,v in self.iteritems():
            if v:
                if type(v) is list:
                    self[k] = ','.join(v)
            else:
                self.pop(k)

        if self.filename:
            self['name'] = os.path.basename(self.filename)

        if self.has_key('type'):
            self['type'] = self['type'].upper()

        if self.has_key('host'):
            h = self['host']
            if h.find(':') >= 0:
                h = h.split(':')
                self['host'] = h[0]
                self['port'] = h[1]

        ints = ['port', 'maxsize', 'persistence']
        for k in ints:
            if self.has_key(k):
                self[k] = int(self[k])

    def for_upload(self):
        '''Prepare a service for uploading'''

        s = defaults
        s.merge(self)

        timestamp = datetime.datetime.utcnow().strftime(s['format'])
        s['path'] = s['path'].replace('<TIMESTAMP>',timestamp)

        # Replace placeholders in url
        if s.has_key('url'):
            url_replace = {
                    '<TIMESTAMP>':timestamp,
                    '<PATH>':s['path']
            }
            url = s['url']
            for k,v in url_replace.iteritems():
                url = url.replace(k,v)
            # Must be done after other replaces to function correctly
            url = url.replace(' ','%20')
            s['url'] = url

        # Ensure trailing '/', after url <PATH> replace
        if s['path']:
            s['path'] = os.path.normpath(s['path'])
        else:
            s['path'] = os.curdir
        s['path'] += os.sep

        return s



def my_storbinary(self, cmd, fp, blocksize=8192, callback=None):
    '''Store a file in binary mode.'''

    self.voidcmd('TYPE I')
    conn = self.transfercmd(cmd)
    while 1:
        buf = fp.read(blocksize)
        if not buf: break
        conn.sendall(buf)
        if callback: callback(buf)
    conn.close()
    return self.voidresp()

def my_storlines(self, cmd, fp, callback=None):
    '''Store a file in line mode.'''

    self.voidcmd('TYPE A')
    conn = self.transfercmd(cmd)
    while 1:
        buf = fp.readline()
        if not buf: break
        if buf[-2:] != CRLF:
            if buf[-1] in CRLF: buf = buf[:-1]
            buf = buf + CRLF
        conn.sendall(buf)
        if callback: callback(buf)
    conn.close()
    return self.voidresp()

# Use the patched versions
ftplib.FTP.storbinary = my_storbinary
ftplib.FTP.storlines = my_storlines
