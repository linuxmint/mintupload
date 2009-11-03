#!/usr/bin/env python

# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 3
# of the License.



import sys

try:
	import pygtk
	pygtk.require("2.0")
except:
	pass

try:
	import gtk
	import gtk.glade
	import os
	import gettext
	import commands
	from mintUploadCore import *
except:
	print "You do not have all the dependencies!"
	sys.exit(1)



gtk.gdk.threads_init()
__version__ = VERSION
# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

def notify(message, timeout=3000):
	os.system("notify-send \"" + _("File Uploader") + "\" \"" + message + "\" -i /usr/lib/linuxmint/mintUpload/icon.svg -t " + str(timeout))

class gtkUploader(mintUploader):
	'''Wrapper for the gtk management of mintUploader'''

	def __init__(self, service, files, wTree):
		mintUploader.__init__(self, service, files)
		self.progressbar = wTree.get_widget("progressbar")
		self.progressbar2 = wTree.get_widget("progressbar2")
		self.wTree = wTree

	def run(self):
		if len(self.files) > 1:
			self.progressbar2.show()
		done = 0
		pct = mintUploader.pct(self, done, len(self.files))			
		for f in self.files:
			self.progressbar.show()			
			try:
				filename = os.path.split(f)[1]
				wTree.get_widget("upload_label").set_text(_("Uploading %(file)s to %(service)s") % {'file':filename, 'service':service['name']})
				#notify(_("Upload to %s started") % service['name'], 1000)
				self.upload(f)
			except Exception, e:
				notify((_("Upload to %s failed: ") % service['name']) + str(e))
				gtk.main_quit()
				sys.exit(0)
			done = done + 1
			pct = mintUploader.pct(self, done, len(self.files))
			self.progressbar2.set_fraction(float(pct)/100)
			self.progressbar2.set_text(str(pct) + "%")	
		notify(_("Upload to %s successful") % service['name'])
		gtk.main_quit()
		sys.exit(0)			

	def progress(self, message, color=None):		
		mintUploader.progress(self, message)

	def pct(self, so_far, total=None):
		pct = mintUploader.pct(self, so_far, total)
		self.progressbar.set_fraction(float(pct)/100)
		self.progressbar.set_text(str(pct) + "%")
		pass

	def success(self):
		mintUploader.success(self)
		#If necessary, show the URL
		#if self.service.has_key('url'):
		#	self.wTree.get_widget("txt_url").set_text(self.url)
		#	self.wTree.get_widget("txt_url").show()
		#	self.wTree.get_widget("lbl_url").show()			

		# Report success
		#self.progress(_("File uploaded successfully."), "green")
		#notify(_("Upload to %s successful") % service['name'])
		#gtk.main_quit()
		#sys.exit(0)		
		
if __name__ == "__main__":	
	if len(sys.argv) < 3:
		print """Usage: mintupload service file [more files]"""
		exit(0)

	service_name = sys.argv[1]
	service = None
	known_services = read_services()
	for known_service in known_services:
		if known_service['name'] == service_name:
			service = known_service

	if service is None:
		print "Unknown service: " + service_name
		os.system("notify-send \"" + _("Unknown service: %s") % service_name + "\"")
	else:
		filenames = sys.argv[2:]
		gladefile = "/usr/lib/linuxmint/mintUpload/mintUpload.glade"
		wTree = gtk.glade.XML(gladefile,"main_window")
		wTree.get_widget("main_window").connect("destroy", gtk.main_quit)
		wTree.get_widget("main_window").set_icon_from_file(ICONFILE)
		wTree.get_widget("main_window").set_title("")
		wTree.get_widget("upload_label").set_text(_("Uploading to %s") % service_name)
		uploader = gtkUploader(service, filenames, wTree)
		uploader.start()
		gtk.main()
