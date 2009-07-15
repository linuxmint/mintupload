
# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2
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
from configobj import ConfigObj



# i18n
gettext.install("messages", "/usr/lib/linuxmint/mintUpload/locale")



class CustomError(Exception):
	'''All custom defined errors'''

	observers = []

	def __init__(self, detail):
		type = self.__class__.__name__
		for observer in self.observers:
			observer.error(type, detail)

	@classmethod
	def addObserver(cls, observer):
		cls.observers.append(observer)



class cliErrorObserver:
	def error(self, type, detail):
		sys.stderr.write(os.linesep + type + ': ' + detail + os.linesep*2)

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
	def __init__(self):
		pynotify.init("mintUpload")

	def notify(self, detail, ntype="dialog-information"):
		pynotify.Notification("mintUpload", detail, ntype).show()



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
			except:
				raise ConnectionError(_("Could not get available space"))

			if self.filesize > self.available:
				raise FilesizeError(_("File larger than service's available space"))



class mintUploader(threading.Thread):
	'''Uploads the file to the selected service'''

	def __init__(self, service, file):
		threading.Thread.__init__(self)
		service = service.for_upload(file)
		self.service = service
		self.file = file
		self.name = os.path.basename(self.file)
		self.filesize = os.path.getsize(self.file)
		self.so_far = 0

		# Switch to required connect function, depending on service
		self.upload = {
			'MINT': self._ftp, # For backwards compatiblity
			'FTP' : self._ftp,
			'SFTP': self._sftp,
			'SCP' : self._scp}[self.service['type']]

	def run(self):
		self.upload()
		self.progress( _("File uploaded successfully."))
		if self.service.has_key('url'):
			self.progress( _("URL:") + " " + self.service['url'])

	def _ftp(self):
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
				try:	ftp.mkd(dir)
				except:	pass
				ftp.cwd(dir)

			f = open(self.file, "rb")
			self.progress(_("Uploading the file..."))
			self.pct(0)
			ftp.storbinary('STOR ' + self.name, f, 1024, callback=self.asciicallback)
			self.pct(1)

		finally:
			# Close any open connections
			try:	f.close()
			except:	pass
			try:	ftp.quit()
			except:	pass

	def getPrivateKey(self):
		'''Find a private key in ~/.ssh'''
		key_files = [home + '/.ssh/id_rsa', home + '/.ssh/id_dsa']
		for f in key_files:
			if os.path.exists(f):
				return paramiko.RSAKey.from_private_key_file(f)

	def _sftp(self):
		'''Connection process for SFTP services'''

		if not self.service['pass']:
			rsa_key = self.getPrivateKey()
			if not rsa_key:	raise ConnectionError(_("This service requires a password or private key."))
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
			try:	transport.open_session().exec_command('mkdir -p ' + path)
			except:	pass

			sftp = paramiko.SFTPClient.from_transport(transport)
			self.progress(_("Uploading the file..."))
			self.pct(0)
			sftp.put(self.file, path + self.name)
			self.pct(1)

		finally:
			# Close any open connections
			try:	sftp.close()
			except:	pass
			try:	transport.close()
			except:	pass

	def _scp(self):
		'''Connection process for SCP services'''

		if not self.service.has_key('port'):
			self.service['port'] = 22
		try:
			# Attempting to connect
			self.service['file'] = self.file
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
			self.pct(1)

		finally:
			# Close any open connections
			try:	scp.close()
			except:	pass

	def progress(self, message):
		print message

	def pct(self, pct):
		pct = int(pct*100)
		sys.stdout.write("\r " + str(pct) + "% [" + (pct/2)*"=" + ">" + (50-(pct/2)) * " " + "] " + sizeStr(self.so_far) + "     ")
		if pct == 100: #if finished
			sys.stdout.write("\n")
			n = config['notification']
			# If nofications are enabled AND the file is minimal x byte in size...
			if n['enable'] == "True" and self.so_far >= int(n['min_filesize']):
				# If when_focused is true OR window has no focus
				if n['when_focused'] == "True" or not self.wTree.get_widget("main_window").has_toplevel_focus():
					mintNotifier().notify(_("File uploaded successfully."))
		sys.stdout.flush()

	def asciicallback(self, buffer):
		self.so_far = self.so_far+len(buffer)-1
		self.pct(float(self.so_far)/self.filesize)
		return



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



ICONFILE = "/usr/lib/linuxmint/mintSystem/icon.png"
CONFIGFILE_GLOBAL = '/etc/linuxmint/mintUpload.conf'
CONFIGFILE_USER = home + '/.linuxmint/mintUpload.conf'

config = ConfigObj(CONFIGFILE_GLOBAL)
if os.path.exists(CONFIGFILE_USER):
	config.merge(ConfigObj(CONFIGFILE_USER))

if not config.has_key('paths'):
	print _("%s is not set in the config file found under %s or %s") %('paths', CONFIGFILE_GLOBAL, CONFIGFILE_USER)
	sys.exit(1)

if not config.has_key('defaults'):
	print _("%s is not set in the config file found under %s or %s") %('defaults', CONFIGFILE_GLOBAL, CONFIGFILE_USER)
	sys.exit(1)

config_paths = config['paths']
config_paths['user'] = config_paths['user'].replace('<HOME>',home)

defaults = config['defaults']
defaults['user'] = defaults['user'].replace('<USER>',os.environ['LOGNAME'])



class Service(ConfigObj):
	'''Object representing an upload service'''

	def __init__(self, *args):
		'''Get the details of an individual service'''

		ConfigObj.__init__(self, *args)
		self._fix()

	def merge(self, *args):
		'''Merge configuration with another'''

		ConfigObj.merge(self, *args)
		self._fix()

	def remove(self):
		'''Deletes the configuration file'''
		os.system("rm " + self.filename)

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

	def for_upload(self, file):
		'''Upload a file to the service'''

		s = defaults
		s.merge(self)

		timestamp = datetime.datetime.utcnow().strftime(s['format'])
		s['path'] = s['path'].replace('<TIMESTAMP>',timestamp)

		# Replace placeholders in url
		if s.has_key('url'):
			url_replace = {
				' ':'%20',
				'<TIMESTAMP>':timestamp,
				'<FILE>':os.path.basename(file),
				'<PATH>':s['path']
			}
			url = s['url']
			for k,v in url_replace.iteritems():
				url = url.replace(k,v)
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

