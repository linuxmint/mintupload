
# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2
# of the License.

try:
	import sys
	import urllib
	import ftplib
	import os
	import datetime
	import gettext
	import paramiko
	import pexpect
	import commands
	from user import home
	from configobj import ConfigObj
except:
	print "You do not have all the dependencies!"
	sys.exit(1)

# i18n
gettext.install("messages", "/usr/lib/linuxmint/mintUpload/locale")

class CustomError(Exception):
	'''All custom defined errors'''
	def __init__(self, detail):
		sys.stderr.write(os.linesep + self.__class__.__name__ + ': ' + detail + os.linesep*2)

class ConnectionError(CustomError):
	'''Raised when an error has occured with an external connection'''
	pass

class FilesizeError(CustomError):
	'''Raised when the file is too large or too small'''
	pass

def sizeStr(size, acc=1, factor=1000):
	'''Converts integer filesize in bytes to textual repr'''

	thresholds = [_("B"),_("KB"),_("MB"),_("GB")]
	size = float(size)
	for i in reversed(range(1,len(thresholds))):
		if size >= factor**i:
			rounded = round(size/factor**i, acc)
			return str(rounded) + thresholds[i]
	return str(int(size)) + thresholds[0]

class spaceChecker:
	'''Checks that the filesize is ok'''

	def __init__(self, service, filesize):
		self.service = service
		self.filesize = filesize

	def checkspace(self):
		# Get the maximum allowed self.filesize on the service
		if self.service.has_key("maxsize"):
			if self.filesize > self.service["maxsize"]:
				raise FilesizeError(_("File larger than service's maximum"))

		# Get the available space left on the service
		if self.service.has_key("space"):
			try:
				spaceInfo = urllib.urlopen(self.service["space"]).read()
			except:
				raise ConnectionError(_("Could not get available space"))

			spaceInfo = spaceInfo.split("/")
			self.available = int(spaceInfo[0])
			self.total = int(spaceInfo[1])
			if self.filesize > self.available:
				raise FilesizeError(_("File larger than service's available space"))

class mintUploader:
	'''Uploads the file to the selected service'''

	def __init__(self, service, file):
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
			ftp.storbinary('STOR ' + self.name, f, 1024, callback=self.asciicallback)
			f.close()
			ftp.quit()

		except:
			# Close any open connections before raising error
			try:	f.close()
			except:	pass
			try:	ftp.quit()
			except:	pass
			raise

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
			if not rsa_key:	raise ConnectionError(_("Connection requires a password or private key!"))
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
			sftp.put(self.file, path + self.name)
			sftp.close()
			transport.close()

		except:
			# Close any open connections before raising error
			try:	sftp.close()
			except:	pass
			try:	transport.close()
			except:	pass
			raise

	def _scp(self):
		'''Connection process for SCP services'''

		try:
			# Attempting to connect
			scp_cmd = "scp " + self.file + " " + self.service['user'] + "@" + self.service['host'] + ':' + self.service['path']
			scp = pexpect.spawn(scp_cmd)

			if self.service['pass']:
				scp.expect('.*password:*')
				scp.sendline(self.service['pass'])

			self.progress(self.service['type'] + " " + _("connection successfully established"))

			scp.timeout = None
			received = scp.expect(['.*100\%.*','.*password:.*',pexpect.EOF])
			if received == 1:
				scp.sendline(' ')
				raise ConnectionError(_("Connection requires a password!"))

			scp.close()

		except:
			# Close any open connections before raising error
			try:	scp.close()
			except:	pass
			raise

	def progress(self, message):
		print message

	def asciicallback(self, buffer):
		self.so_far = self.so_far+len(buffer)-1
		pct = float(self.so_far)/self.filesize
		pct = int(pct * 100)
		print "so far:", pct, "%"
		return

