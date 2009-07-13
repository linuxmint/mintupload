#!/usr/bin/env python

# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2
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

# i18n
gettext.install("messages", "/usr/lib/linuxmint/mintUpload/locale")

def gtkCustomError(self, detail, statusbar):
	message = "<span color='red'>" + detail + "</span>"
	statusbar.push(statusbar.get_context_id("mintUpload"), message)
	statusbar.get_children()[0].get_children()[0].set_use_markup(True)
	CustomError.error(self, detail)

CustomError.__init__ = gtkCustomError

class gtkSpaceChecker(mintSpaceChecker):
	'''Checks for available space on the service'''

	def __init__(self, service, filesize, statusbar, wTree):
		mintSpaceChecker.__init__(self, service, filesize)
		self.statusbar = statusbar
		self.wTree = wTree

	def run(self):
		context_id = self.statusbar.get_context_id("mintUpload")

		# Get the file's persistence on the service
		if self.service.has_key('persistence'):
			self.wTree.get_widget("txt_persistence").set_label(str(self.service['persistence']) + " " + _("days"))
			self.wTree.get_widget("txt_persistence").show()
			self.wTree.get_widget("lbl_persistence").show()
		else:
			self.wTree.get_widget("txt_persistence").set_label(_("N/A"))
			self.wTree.get_widget("txt_persistence").hide()
			self.wTree.get_widget("lbl_persistence").hide()

		# Get the maximum allowed filesize on the service
		if self.service.has_key('maxsize'):
			maxsizeStr = sizeStr(self.service['maxsize'])
			self.wTree.get_widget("txt_maxsize").set_label(maxsizeStr)
			self.wTree.get_widget("txt_maxsize").show()
			self.wTree.get_widget("lbl_maxsize").show()
		else:
			self.wTree.get_widget("txt_maxsize").set_label(_("N/A"))
			self.wTree.get_widget("txt_maxsize").hide()
			self.wTree.get_widget("lbl_maxsize").hide()

		needsCheck = True
		if not self.service.has_key('space'):
			self.wTree.get_widget("txt_space").set_label(_("N/A"))
			self.wTree.get_widget("txt_space").hide()
			self.wTree.get_widget("lbl_space").hide()
			if not self.service.has_key('maxsize'):
				needsCheck=False
				# Activate upload button
				self.statusbar.push(context_id, "<span color='green'>" + _("Service ready. Space available.") + "</span>")
				label = self.statusbar.get_children()[0].get_children()[0]
				label.set_use_markup(True)
				self.wTree.get_widget("upload_button").set_sensitive(True)

		if needsCheck:
			self.wTree.get_widget("main_window").window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
			self.wTree.get_widget("combo").set_sensitive(False)
			self.wTree.get_widget("upload_button").set_sensitive(False)
			self.statusbar.push(context_id, _("Checking space on the service..."))

			self.wTree.get_widget("frame_progress").hide()

			# Check the filesize
			try:
				self.check()

			except ConnectionError:
				self.statusbar.push(context_id, "<span color='red'>" + _("Could not connect to the service.") + "</span>")

			except FilesizeError:
				self.statusbar.push(context_id, "<span color='red'>" + _("File too big or not enough space on the service.") + "</span>")

			else:
				# Display the available space left on the service
				if self.service.has_key('space'):
					pctSpace = float(self.available) / float(self.total) * 100
					pctSpaceStr = sizeStr(self.available) + " (" + str(int(pctSpace)) + "%)"
					self.wTree.get_widget("txt_space").set_label(pctSpaceStr)
					self.wTree.get_widget("txt_space").show()
					self.wTree.get_widget("lbl_space").show()

				# Activate upload button
				self.statusbar.push(context_id, "<span color='green'>" + _("Service ready. Space available.") + "</span>")
				self.wTree.get_widget("upload_button").set_sensitive(True)

			finally:
				label = self.statusbar.get_children()[0].get_children()[0]
				label.set_use_markup(True)
				self.wTree.get_widget("combo").set_sensitive(True)
				self.wTree.get_widget("main_window").window.set_cursor(None)
				self.wTree.get_widget("main_window").resize(*self.wTree.get_widget("main_window").size_request())

class gtkUploader(mintUploader):
	'''Wrapper for the gtk management of mintUploader'''

	def __init__(self, service, file, progressbar, statusbar, wTree):
		mintUploader.__init__(self, service, file)
		self.progressbar = progressbar
		self.statusbar = statusbar
		self.wTree = wTree

	def run(self):
		self.wTree.get_widget("upload_button").set_sensitive(False)
		self.wTree.get_widget("combo").set_sensitive(False)
		self.wTree.get_widget("main_window").window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
		self.wTree.get_widget("frame_progress").show()
		self.pct(0)

		try:
			self.upload()
		except:
			try:    raise CustomError(_("Upload failed."), self.statusbar)
			except: pass

		else:
			# Report success
			self.pct(1)
			self.progress(_("File uploaded successfully."), "green")

			#If service is Mint then show the URL
			if self.service.has_key('url'):
				self.wTree.get_widget("txt_url").set_text(self.service['url'])
				self.wTree.get_widget("txt_url").show()
				self.wTree.get_widget("lbl_url").show()

		finally:
			self.wTree.get_widget("main_window").window.set_cursor(None)

	def progress(self, message, color=None):
		context_id = self.statusbar.get_context_id("mintUpload")
		mintUploader.progress(self, message)
		if color:
			color_message = "<span color='%s'>%s</span>" % (color, message)
			statusbar.push(context_id, color_message)
			statusbar.get_children()[0].get_children()[0].set_use_markup(True)
		else:
			self.statusbar.push(context_id, message)

	def pct(self, pct):
		mintUploader.pct(self, pct)
		pctStr = str(int(pct * 100))
		self.progressbar.set_fraction(pct)
		self.progressbar.set_text(pctStr + "%")

class mintUploadWindow:
	"""This is the main class for the application"""

	def __init__(self, filename):
		self.filename = filename
		self.iconfile = "/usr/lib/linuxmint/mintSystem/icon.png"

		# Set the Glade file
		self.gladefile = "/usr/lib/linuxmint/mintUpload/mintUpload.glade"
		self.wTree = gtk.glade.XML(self.gladefile,"main_window")

		self.wTree.get_widget("main_window").connect("destroy", gtk.main_quit)
		self.wTree.get_widget("main_window").set_icon_from_file(self.iconfile)

		# i18n
		self.wTree.get_widget("label2").set_label("<b>" + _("Upload service") + "</b>")
		self.wTree.get_widget("label3").set_label("<b>" + _("Local file") + "</b>")
		self.wTree.get_widget("label4").set_label("<b>" + _("Remote file") + "</b>")
		self.wTree.get_widget("label187").set_label(_("Name:"))
		self.wTree.get_widget("lbl_space").set_label(_("Free space:"))
		self.wTree.get_widget("lbl_maxsize").set_label(_("Max file size:"))
		self.wTree.get_widget("lbl_persistence").set_label(_("Persistence:"))
		self.wTree.get_widget("label195").set_label(_("Path:"))
		self.wTree.get_widget("label193").set_label(_("Size:"))
		self.wTree.get_widget("label190").set_label(_("Upload progress:"))
		self.wTree.get_widget("lbl_url").set_label(_("URL:"))

		fileMenu = gtk.MenuItem(_("_File"))
		fileSubmenu = gtk.Menu()
		fileMenu.set_submenu(fileSubmenu)
		closeMenuItem = gtk.ImageMenuItem(gtk.STOCK_CLOSE)
		closeMenuItem.get_child().set_text(_("Close"))
		closeMenuItem.connect("activate", gtk.main_quit)
		fileSubmenu.append(closeMenuItem)

		helpMenu = gtk.MenuItem(_("_Help"))
		helpSubmenu = gtk.Menu()
		helpMenu.set_submenu(helpSubmenu)
		aboutMenuItem = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
		aboutMenuItem.get_child().set_text(_("About"))
		aboutMenuItem.connect("activate", self.open_about)
		helpSubmenu.append(aboutMenuItem)

		editMenu = gtk.MenuItem(_("_Edit"))
		editSubmenu = gtk.Menu()
		editMenu.set_submenu(editSubmenu)
		prefsMenuItem = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES)
		prefsMenuItem.get_child().set_text(_("Services"))
		prefsMenuItem.connect("activate", self.open_services, self.wTree.get_widget("combo"))
		editSubmenu.append(prefsMenuItem)

		self.wTree.get_widget("menubar1").append(fileMenu)
		self.wTree.get_widget("menubar1").append(editMenu)
		self.wTree.get_widget("menubar1").append(helpMenu)
		self.wTree.get_widget("menubar1").show_all()

		self.reload_services(self.wTree.get_widget("combo"))

		cell = gtk.CellRendererText()
		self.wTree.get_widget("combo").pack_start(cell)
		self.wTree.get_widget("combo").add_attribute(cell,'text',0)

		self.wTree.get_widget("combo").connect("changed", self.comboChanged)
		self.wTree.get_widget("upload_button").connect("clicked", self.upload)
		self.wTree.get_widget("cancel_button").connect("clicked", gtk.main_quit)

		# Print the name of the file in the GUI
		self.wTree.get_widget("txt_file").set_label(self.filename)

		# Calculate the size of the file
		self.filesize = os.path.getsize(self.filename)
		self.wTree.get_widget("txt_size").set_label(sizeStr(self.filesize))

		if len(self.services) == 1:
			self.wTree.get_widget("combo").set_active(0)
			self.comboChanged(None)

		self.statusbar = self.wTree.get_widget("statusbar")
		self.progressbar = self.wTree.get_widget("progressbar")

	def reload_services(self, combo):
		model = gtk.TreeStore(str)
		combo.set_model(model)
		self.services = read_services()
		for service in self.services:
			iter = model.insert_before(None, None)
			model.set_value(iter, 0, service['name'])
		del model

	def open_about(self, widget):
		dlg = gtk.AboutDialog()
		dlg.set_title(_("About") + " - mintUpload")
		version = commands.getoutput("mint-apt-version mintupload 2> /dev/null")
		dlg.set_version(version)
		dlg.set_program_name("mintUpload")
		dlg.set_comments(_("File uploader for Linux Mint"))
		try:
		    h = open('/usr/lib/linuxmint/mintSystem/GPL.txt','r')
		    s = h.readlines()
		    gpl = ""
		    for line in s:
		    	gpl += line
		    h.close()
		    dlg.set_license(gpl)
		except Exception, detail:
		    print detail

		dlg.set_authors([
			"Clement Lefebvre <root@linuxmint.com>",
			"Philip Morrell <mintupload.emorrp1@mamber.net>",
			"Manuel Sandoval <manuel@slashvar.com>",
			"Dennis Schwertel <s@digitalkultur.net>"
		])
		dlg.set_icon_from_file(self.iconfile)
		dlg.set_logo(gtk.gdk.pixbuf_new_from_file(self.iconfile))
		def close(w, res):
		    if res == gtk.RESPONSE_CANCEL:
		        w.hide()
		dlg.connect("response", close)
		dlg.show()

	def open_services(self, widget, combo):
		self.wTree = gtk.glade.XML(self.gladefile, "services_window")
		treeview_services = self.wTree.get_widget("treeview_services")
		treeview_services_system = self.wTree.get_widget("treeview_services_system")

		self.wTree.get_widget("services_window").set_title(_("Services") + " - mintUpload")
		self.wTree.get_widget("services_window").set_icon_from_file(self.iconfile)
		self.wTree.get_widget("services_window").show()

		self.wTree.get_widget("button_close").connect("clicked", self.close_window, self.wTree.get_widget("services_window"), combo)
		self.wTree.get_widget("services_window").connect("destroy", self.close_window, self.wTree.get_widget("services_window"), combo)
		self.wTree.get_widget("toolbutton_add").connect("clicked", self.add_service, treeview_services)
		self.wTree.get_widget("toolbutton_edit").connect("clicked", self.edit_service_toolbutton, treeview_services)
		self.wTree.get_widget("toolbutton_remove").connect("clicked", self.remove_service, treeview_services)

		column1 = gtk.TreeViewColumn(_("Services"), gtk.CellRendererText(), text=0)
		column1.set_sort_column_id(0)
		column1.set_resizable(True)
		treeview_services.append_column(column1)
		treeview_services.set_headers_clickable(True)
		treeview_services.set_reorderable(False)
		treeview_services.show()
		column1 = gtk.TreeViewColumn(_("System-wide services"), gtk.CellRendererText(), text=0)
		treeview_services_system.append_column(column1)
		treeview_services_system.show()
		self.load_services(treeview_services, treeview_services_system)
		treeview_services.connect("row-activated", self.edit_service);

	def load_services(self, treeview_services, treeview_services_system):
		usermodel = gtk.TreeStore(str)
		usermodel.set_sort_column_id( 0, gtk.SORT_ASCENDING )
		sysmodel = gtk.TreeStore(str)
		sysmodel.set_sort_column_id( 0, gtk.SORT_ASCENDING )
		models = {
			'user':usermodel,
			'system':sysmodel
		}
		treeview_services.set_model(models['user'])
		treeview_services_system.set_model(models['system'])

		self.services = read_services()
		for service in self.services:
			iter = models[service['loc']].insert_before(None, None)
			models[service['loc']].set_value(iter, 0, service['name'])

		del usermodel
		del sysmodel

	def close_window(self, widget, window, combo=None):
		window.hide()
		if (combo != None):
			self.reload_services(combo)

	def add_service(self, widget, treeview_services):
		self.wTree = gtk.glade.XML(self.gladefile, "dialog_add_service")
		self.wTree.get_widget("dialog_add_service").set_title(_("New service"))
		self.wTree.get_widget("dialog_add_service").set_icon_from_file(self.iconfile)
		self.wTree.get_widget("dialog_add_service").show()
		self.wTree.get_widget("lbl_name").set_label(_("Name:"))
		self.wTree.get_widget("button_ok").connect("clicked", self.new_service, self.wTree.get_widget("dialog_add_service"), self.wTree.get_widget("txt_name"), treeview_services)
		self.wTree.get_widget("button_cancel").connect("clicked", self.close_window, self.wTree.get_widget("dialog_add_service"))

	def new_service(self, widget, window, entry, treeview_services):
		service = Service('/usr/lib/linuxmint/mintUpload/sample.service')
		sname = entry.get_text()
		if sname:
			model = treeview_services.get_model()
			iter = model.insert_before(None, None)
			model.set_value(iter, 0, sname)
			service.filename = config_paths['user'] + sname
			service.write()
		self.close_window(None, window)
		self.edit_service(treeview_services, model.get_path(iter), 0)

	def edit_service_toolbutton(self, widget, treeview_services):
		selection = treeview_services.get_selection()
		(model, iter) = selection.get_selected()
		self.edit_service(treeview_services, model.get_path(iter), 0)

	def edit_service(self,widget, path, column):
		model=widget.get_model()
		iter = model.get_iter(path)
		sname = model.get_value(iter, 0)
		file = config_paths['user'] + sname

		self.wTree = gtk.glade.XML(self.gladefile, "dialog_edit_service")
		self.wTree.get_widget("dialog_edit_service").set_title(_("Edit service"))
		self.wTree.get_widget("dialog_edit_service").set_icon_from_file(self.iconfile)
		self.wTree.get_widget("dialog_edit_service").show()
		self.wTree.get_widget("button_ok").connect("clicked", self.modify_service, self.wTree.get_widget("dialog_edit_service"), file)
		self.wTree.get_widget("button_cancel").connect("clicked", self.close_window, self.wTree.get_widget("dialog_edit_service"))

		#i18n
		self.wTree.get_widget("lbl_type").set_label(_("Type:"))
		self.wTree.get_widget("lbl_hostname").set_label(_("Hostname:"))
		self.wTree.get_widget("lbl_port").set_label(_("Port:"))
		self.wTree.get_widget("lbl_username").set_label(_("Username:"))
		self.wTree.get_widget("lbl_password").set_label(_("Password:"))
		self.wTree.get_widget("lbl_timestamp").set_label(_("Timestamp:"))
		self.wTree.get_widget("lbl_path").set_label(_("Path:"))

		self.wTree.get_widget("lbl_hostname").set_tooltip_text(_("Hostname or IP address, default: mint-space.com"))
		self.wTree.get_widget("txt_hostname").set_tooltip_text(_("Hostname or IP address, default: mint-space.com"))

		self.wTree.get_widget("lbl_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))
		self.wTree.get_widget("txt_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))

		self.wTree.get_widget("lbl_username").set_tooltip_text(_("Username, defaults to your local username"))
		self.wTree.get_widget("txt_username").set_tooltip_text(_("Username, defaults to your local username"))

		self.wTree.get_widget("lbl_password").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))
		self.wTree.get_widget("txt_password").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))

		self.wTree.get_widget("lbl_timestamp").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])
		self.wTree.get_widget("txt_timestamp").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])

		self.wTree.get_widget("lbl_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))
		self.wTree.get_widget("txt_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))

		try:
			config = Service(file)
			try:
				model = self.wTree.get_widget("combo_type").get_model()
				iter = model.get_iter_first()
				while (iter != None and model.get_value(iter, 0) != config['type'].lower()):
					iter = model.iter_next(iter)
				self.wTree.get_widget("combo_type").set_active_iter(iter)
			except:
				pass
			try:
				self.wTree.get_widget("txt_hostname").set_text(config['host'])
			except:
				self.wTree.get_widget("txt_hostname").set_text("")
			try:
				self.wTree.get_widget("txt_port").set_text(config['port'])
			except:
				self.wTree.get_widget("txt_port").set_text("")
			try:
				self.wTree.get_widget("txt_username").set_text(config['user'])
			except:
				self.wTree.get_widget("txt_username").set_text("")
			try:
				self.wTree.get_widget("txt_password").set_text(config['pass'])
			except:
				self.wTree.get_widget("txt_password").set_text("")
			try:
				self.wTree.get_widget("txt_timestamp").set_text(config['format'])
			except:
				self.wTree.get_widget("txt_timestamp").set_text("")
			try:
				self.wTree.get_widget("txt_path").set_text(config['path'])
			except:
				self.wTree.get_widget("txt_path").set_text("")
		except Exception, detail:
			print detail

	def modify_service(self, widget, window, file):
		try:
			model = self.wTree.get_widget("combo_type").get_model()
			iter = 	self.wTree.get_widget("combo_type").get_active_iter()

			# Get configuration
			config = {}
			config['type'] = model.get_value(iter, 0)
			config['host'] = self.wTree.get_widget("txt_hostname").get_text()
			config['port'] = self.wTree.get_widget("txt_port").get_text()
			config['user'] = self.wTree.get_widget("txt_username").get_text()
			config['pass'] = self.wTree.get_widget("txt_password").get_text()
			config['format'] = self.wTree.get_widget("txt_timestamp").get_text()
			config['path'] = self.wTree.get_widget("txt_path").get_text()

			# Write to service's config file
			s = Service(file)
			s.merge(config)
			s.write()
		except Exception, detail:
			print detail
		window.hide()

	def remove_service(self, widget, treeview_services):
		(model, iter) = treeview_services.get_selection().get_selected()
		if (iter != None):
			service = model.get_value(iter, 0)
			for s in self.services:
				if s['name'] == service:
					s.remove()
					self.services.remove(s)
			model.remove(iter)

	def comboChanged(self, widget):
		'''Change the selected service'''

		# Get the selected service
		model = self.wTree.get_widget("combo").get_model()
		active = self.wTree.get_widget("combo").get_active()
		if active < 0:
			return
		selectedService = model[active][0]

		self.services = read_services()
		for service in self.services:
			if service['name'] == selectedService:
				self.selected_service = service
				checker = gtkSpaceChecker(self.selected_service, self.filesize, self.statusbar, wTree)
				checker.start()
				return True

	def upload(self, widget):
		'''Start the upload process'''

		uploader = gtkUploader(self.selected_service, self.filename, self.progressbar, self.statusbar, self.wTree)
		uploader.start()
		return True

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "need a file to upload!"
		exit(1)
	if len(sys.argv) > 2:
		print "too many files! using only the first!"
	if sys.argv[1] == "--version":
		print "mintupload: %s" % commands.getoutput("mint-apt-version mintupload 2> /dev/null")
		exit(0)
	if sys.argv[1] in ["-h","--help"]:
		print """Usage: mintupload.py path/to/filename"""
		exit(0)

	filename = sys.argv[1]
	mainwin = mintUploadWindow(filename)
	gtk.main()
