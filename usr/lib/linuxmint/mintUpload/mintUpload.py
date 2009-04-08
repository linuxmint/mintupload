#!/usr/bin/env python

# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2
# of the License.
#
# Changelog
# =========
#
# - Uses /etc/ for the services
# - Now supports FTP with optional path option
# - Now supports scp - jayemdaet
# - Now supports ssh/sftp - emorrp1
# - github test, sorry!


import sys

try:
	import pygtk
	pygtk.require("2.0")
except:
	pass

try:
	import gtk
	import gtk.glade
	import urllib
	import ftplib
	import os
	import threading
	import datetime
	import gettext
	import paramiko
	import pexpect
except:
	print "You do not have all the dependencies!"
	sys.exit(1)

gtk.gdk.threads_init()

# i18n
gettext.install("messages", "/usr/lib/linuxmint/mintUpload/locale")

class ConnectionError(Exception):
	'''Custom error to raise for errors during connections'''
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

class spaceChecker(threading.Thread):
	'''Checks that the filesize is fine'''

	def run(self):
		global statusbar
		global context_id
		global wTree
		global selected_service

		wTree.get_widget("combo").set_sensitive(False)
		wTree.get_widget("upload_button").set_sensitive(False)
		statusbar.push(context_id, _("Checking space on the service..."))
		wTree.get_widget("main_window").window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
		self.ready = True

		try:
			# Get the file's persistence on the service
			if selected_service['persistence']:
				wTree.get_widget("txt_persistence").set_label(selected_service['persistence'] + " " + _("days"))
			else:
				wTree.get_widget("txt_persistence").set_label(_("N/A"))

			# Get the maximum allowed filesize on the service
			if selected_service['maxsize']:
				maxsize = float(selected_service['maxsize'])
				if filesize > maxsize:
					self.ready = False
				maxsizeStr = sizeStr(maxsize)
				wTree.get_widget("txt_maxsize").set_label(maxsizeStr)
			else:
				wTree.get_widget("txt_maxsize").set_label(_("N/A"))

			# Get the available space left on the service
			if selected_service['space']:
				spaceInfo = urllib.urlopen(selected_service['space']).read().split('/')
				spaceAvailable = float(spaceInfo[0])
				spaceTotal = float(spaceInfo[1])
				if spaceAvailable < filesize:
					self.ready = False
				pctSpace = spaceAvailable / spaceTotal * 100
				pctSpaceStr = sizeStr(spaceAvailable) + " (" + str(int(pctSpace)) + "%)"
				wTree.get_widget("txt_space").set_label(pctSpaceStr)
			else:
				wTree.get_widget("txt_space").set_label(_("N/A"))

			# Activate the upload button if the space is OK
			if self.ready:
				wTree.get_widget("upload_button").set_sensitive(True)
				statusbar.push(context_id, "<span color='green'>" + _("Service ready. Space available.") + "</span>")
			else:
				wTree.get_widget("upload_button").set_sensitive(False)
				statusbar.push(context_id, "<span color='red'>" + _("File too big or not enough space on the service.") + "</span>")
			label = statusbar.get_children()[0].get_children()[0]
			label.set_use_markup(True)

		except Exception, detail:
			print detail
			statusbar.push(context_id, "<span color='red'>" + _("Could not connect to the service.") + "</span>")
			label = statusbar.get_children()[0].get_children()[0]
			label.set_use_markup(True)
			wTree.get_widget("upload_button").set_sensitive(False)

		finally:
			wTree.get_widget("main_window").window.set_cursor(None)
			wTree.get_widget("combo").set_sensitive(True)

class mintUploader(threading.Thread):
	'''Uploads the file to the selected service'''

	def run(self):
		global so_far
		global filesize
		global progressbar
		global statusbar
		global selected_service
		global filename
		global wTree
		global url
		global name

		wTree.get_widget("combo").set_sensitive(False)
		wTree.get_widget("upload_button").set_sensitive(False)
		statusbar.push(context_id, _("Connecting to the service..."))
		wTree.get_widget("main_window").window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))

		try:
			so_far = 0
			progressbar.set_fraction(0)
			progressbar.set_text("0%")

			# Switch to required connect function, depending on service
			supported_services = {
				'MINT': self._ftp, # For backwards compatiblity
				'FTP' : self._ftp,
				'SSH' : self._sftp,
				'SFTP': self._sftp,
				'SCP' : self._scp}[selected_service['type']]()

			# Report success
			progressbar.set_fraction(1)
			progressbar.set_text("100%")
			if selected_service['url']:
				wTree.get_widget("txt_url").set_text(selected_service['url'])
				wTree.get_widget("copy_button").set_sensitive(True)
			else:
				wTree.get_widget("txt_url").set_text(_("N/A"))
				wTree.get_widget("copy_button").set_sensitive(False)
			statusbar.push(context_id, "<span color='green'>" + _("File uploaded successfully.") + "</span>")
			label = statusbar.get_children()[0].get_children()[0]
			label.set_use_markup(True)

		except Exception, detail:
			print detail
			statusbar.push(context_id, "<span color='red'>" + _("Upload failed.") + "</span> -- " + str(detail).encode("ascii", "ignore"))
			label = statusbar.get_children()[0].get_children()[0]
			label.set_use_markup(True)

		finally:
			wTree.get_widget("main_window").window.set_cursor(None)
			wTree.get_widget("combo").set_sensitive(False)
			wTree.get_widget("upload_button").set_sensitive(False)

	def _ftp(self):
		'''Connection process for FTP services'''

		if not selected_service['port']:
			selected_service['port'] = 21
		try:
			# Attempting to connect
			ftp = ftplib.FTP()
			ftp.connect(selected_service['host'], selected_service['port'])
			ftp.login(selected_service['user'], selected_service['pass'])
			statusbar.push(context_id, selected_service['type'] + _(" connection successfully established"))

			# Create full path
			for dir in selected_service['path'].split("/"):
				try:	ftp.mkd(dir)
				except:	pass
				ftp.cwd(dir)

			f = open(filename, "rb")
			statusbar.push(context_id, _("Uploading the file..."))
			ftp.storbinary('STOR ' + name, f, 1024, callback=self.asciicallback)
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
		key_files = ['~/.ssh/id_rsa','~/.ssh/id_dsa']
		for f in key_files:
			f = os.path.expanduser(f)
			if os.path.exists(f):
				return paramiko.RSAKey.from_private_key_file(f)

	def _sftp(self):
		'''Connection process for SSH/SFTP services'''

		if not selected_service['pass']:
			rsa_key = self.getPrivateKey()
			if not rsa_key:	raise ConnectionError("Connection requires a password or private key!")
		if not selected_service['port']:
			selected_service['port'] = 22
		try:
			# Attempting to connect
			transport = paramiko.Transport((selected_service['host'], selected_service['port']))
			if selected_service['pass']:
				transport.connect(username = selected_service['user'], password = selected_service['pass'])
			else:
				transport.connect(username = selected_service['user'], pkey = rsa_key)
			statusbar.push(context_id, selected_service['type'] + _(" connection successfully established"))

			# Create full remote path
			path = selected_service['path']
			try:	transport.open_session().exec_command('mkdir -p ' + path)
			except:	pass

			sftp = paramiko.SFTPClient.from_transport(transport)
			statusbar.push(context_id, _("Uploading the file..."))
			sftp.put(filename, path + name)
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
			scp_cmd = "scp " + filename + " " + selected_service['user'] + "@" + selected_service['host'] + ':' + selected_service['path']
			scp = pexpect.spawn(scp_cmd)

			if selected_service['pass']:
				scp.expect('.*password:*')
				scp.sendline(selected_service['pass'])

			statusbar.push(context_id, selected_service['type'] + _(" connection successfully established"))

			scp.timeout = None
			received = scp.expect(['.*100\%.*','.*password:.*',pexpect.EOF])
			if received == 1:
				scp.sendline(' ')
				raise ConnectionError("Connection requires a password!")

			scp.close()

		except:
			# Close any open connections before raising error
			try:	scp.close()
			except:	pass
			raise

	def asciicallback(self, buffer):
		global so_far
		global progressbar
		global filesize

		so_far = so_far+len(buffer)-1
		pct = float(so_far)/filesize
		progressbar.set_fraction(pct)
		pct = int(pct * 100)
		progressbar.set_text(str(pct) + "%")
		print "so far:", pct, "%"
		return

class mintUploadWindow:
	"""This is the main class for the application"""

	def __init__(self, filename):
		global filesize
		global wTree
		global name

		self.filename = filename
		name = os.path.basename(filename)

		# Set the Glade file
		self.gladefile = "/usr/lib/linuxmint/mintUpload/mintUpload.glade"
		wTree = gtk.glade.XML(self.gladefile,"main_window")

		wTree.get_widget("main_window").connect("destroy", gtk.main_quit)

		# i18n
		wTree.get_widget("txt_name").set_label("<big><b>" + _("Upload a file") + "</b></big>")
		wTree.get_widget("txt_guidance").set_label("<i>" + _("Upload and share a file") + "</i>")
		wTree.get_widget("label2").set_label("<b>" + _("Upload service") + "</b>")
		wTree.get_widget("label3").set_label("<b>" + _("Local file") + "</b>")
		wTree.get_widget("label4").set_label("<b>" + _("Remote file") + "</b>")
		wTree.get_widget("label187").set_label(_("Name:"))
		wTree.get_widget("label188").set_label(_("Free space:"))
		wTree.get_widget("label196").set_label(_("Max file size:"))
		wTree.get_widget("label198").set_label(_("Persistence:"))
		wTree.get_widget("label195").set_label(_("Path:"))
		wTree.get_widget("label193").set_label(_("Size:"))
		wTree.get_widget("label190").set_label(_("Upload progress:"))
		wTree.get_widget("label191").set_label(_("URL:"))

		services = self.read_services()
		for service in services:
			wTree.get_widget("combo").append_text(service['name'])
		wTree.get_widget("combo").connect("changed", self.comboChanged)
		wTree.get_widget("upload_button").connect("clicked", self.upload)
		wTree.get_widget("copy_button").connect("clicked", self.copy)
		wTree.get_widget("cancel_button").connect("clicked", gtk.main_quit)

		# Print the name of the file in the GUI
		wTree.get_widget("txt_file").set_label(self.filename)

		# Calculate the size of the file
		filesize = os.path.getsize(self.filename)
		wTree.get_widget("txt_size").set_label(sizeStr(filesize))

	def comboChanged(self, widget):
		'''Change the selected service'''

		global progressbar
		global statusbar
		global wTree
		global context_id
		global selected_service

		progressbar = wTree.get_widget("progressbar")
		statusbar = wTree.get_widget("statusbar")
		context_id = statusbar.get_context_id("mintUpload")

		# Get the selected service
		model = wTree.get_widget("combo").get_model()
		active = wTree.get_widget("combo").get_active()
		if active < 0:
			return
		selectedService = model[active][0]

		services = self.read_services()
		for service in services:
			if service['name'] == selectedService:
				selected_service = service
				spacecheck = spaceChecker()
				spacecheck.start()
				return True

	def read_services(self):
		'''Get all defined services'''

		services = []
		config_paths = ["/etc/linuxmint/mintUpload/services/", "~/.linuxmint/mintUpload/services/"]
		for path in config_paths:
			path = os.path.expanduser(path)
			os.system("mkdir -p " + path)
			for file in os.listdir(path):
				if file[0] != "." and file[-1:] != "~" and file[-4:] != ".bak":
					# Ignore config files causing errors
					try:	services.append(self.read_service(path + file))
					except:	pass
		return services

	def read_service(self, path):
		'''Get the details of an individual service'''

		from configobj import ConfigObj

		config = ConfigObj(path)
		service = {}

		# Specify sensible defaults here for configs assumed to exist later
		try:	service["type"] = config['type'].upper()
		except:	service["type"] = "MINT"

		try:	service["host"] = config['host']
		except:	service["mint-space.com"]

		try:	service["name"] = config['name']
		except:	service["name"] = os.path.basename(path)

		try:	service["user"] = config['user']
		except:	service["user"] = os.environ['LOGNAME']

		try:	service["format"] = config['format']
		except:	service["format"] = "%Y%m%d%H%M%S"
		finally: timestamp = datetime.datetime.utcnow().strftime(service["format"])
		try:
			service["path"] = config['path']
			service["path"] = service["path"].replace('<TIMESTAMP>', timestamp)
		except:
			service["path"] = None

		# Specify default as None to require test later
		try:	service["pass"] = config['pass']
		except:	service["pass"] = None

		try:	service["port"] = int(config['port'])
		except:	service["port"] = None

		try:	service["maxsize"] = config['maxsize']
		except:	service["maxsize"] = None

		try:	service["persistence"] = config['persistence']
		except:	service["persistence"] = None

		try:	service["space"] = config['space']
		except:	service["space"] = None

		try:
			url = config['url']
			if type(url) is list:
				url = ",".join(url)
			url = url.replace('<TIMESTAMP>', timestamp)
			url = url.replace('<FILE>', name)
			if service["path"]:
				url = url.replace('<PATH>', service["path"])
			service["url"] = url
		except:
			service["url"] = None

		# Ensure trailing '/', after url <PATH> replace
		if service["path"]:
			service["path"] = os.path.normpath(service["path"])
			service["path"] += os.sep
		else:
			service["path"] = os.curdir + os.sep

		return service

	def upload(self, widget):
		'''Start the upload process'''

		global wTree

		wTree.get_widget("upload_button").set_sensitive(False)
		wTree.get_widget("combo").set_sensitive(False)
		uploader = mintUploader()
		uploader.start()
		return True

	def copy(self, widget):
		'''Copy the url to the clipboard'''

		clipboard = gtk.clipboard_get()
		clipboard.set_text(wTree.get_widget("txt_url").get_text())
		clipboard.store()

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

if __name__ == "__main__":
	filename = sys.argv[1]
	mainwin = mintUploadWindow(filename)
	gtk.main()
