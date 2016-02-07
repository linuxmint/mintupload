#!/usr/bin/python2

import os
import commands
import gettext
import pygtk
pygtk.require("2.0")
import gtk
import gtk.glade
import string
from mintUploadCore import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")


class ManagerWindow:

    def __init__(self):
        # Set the Glade file
        gladefile = "/usr/lib/linuxmint/mintUpload/mintUpload.glade"
        wTree = gtk.glade.XML(gladefile, "manager_window")
        wTree.get_widget("manager_window").set_title(_("Upload Manager"))
        vbox = wTree.get_widget("vbox_main")
        treeview_services = wTree.get_widget("treeview_services")
        wTree.get_widget("manager_window").set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")

        # the treeview
        column1 = gtk.TreeViewColumn(_("Upload services"), gtk.CellRendererText(), text=0)
        column1.set_sort_column_id(0)
        column1.set_resizable(True)
        treeview_services.append_column(column1)
        treeview_services.set_headers_clickable(True)
        treeview_services.set_reorderable(False)
        treeview_services.show()

        self.reload_services(treeview_services)

        wTree.get_widget("manager_window").connect("delete_event", gtk.main_quit)
        wTree.get_widget("button_close").connect("clicked", gtk.main_quit)
        wTree.get_widget("toolbutton_add").connect("clicked", self.add_service, treeview_services)
        wTree.get_widget("toolbutton_edit").connect("clicked", self.edit_service_from_button, treeview_services)
        wTree.get_widget("toolbutton_remove").connect("clicked", self.remove_service, treeview_services)
        treeview_services.connect("row_activated", self.edit_service_from_tree, treeview_services)

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

        wTree.get_widget("menubar1").append(fileMenu)
        wTree.get_widget("menubar1").append(helpMenu)
        wTree.get_widget("manager_window").show_all()

    def open_about(self, widget):
        dlg = gtk.AboutDialog()
        dlg.set_title(_("About") + " - mintUpload")
        version = commands.getoutput("/usr/lib/linuxmint/common/version.py mintupload")
        dlg.set_version(version)
        dlg.set_program_name("mintUpload")
        dlg.set_comments(_("Upload Manager"))
        try:
            h = open('/usr/share/common-licenses/GPL', 'r')
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
        dlg.set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")
        dlg.set_logo(gtk.gdk.pixbuf_new_from_file("/usr/lib/linuxmint/mintUpload/icon.svg"))

        def close(w, res):
            if res == gtk.RESPONSE_CANCEL:
                w.hide()
        dlg.connect("response", close)
        dlg.show()

    def response_to_dialog(self, entry, dialog, response):
        dialog.response(response)

    def add_service(self, widget, treeview_services):
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, None)
        dialog.set_title(_("Upload Manager"))
        dialog.set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")
        dialog.set_markup(_("<b>Please enter a name for the new upload service:</b>"))
        entry = gtk.Entry()
        entry.connect("changed", self.check_service_name, dialog)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Service name:")), False, 5, 5)
        hbox.pack_end(entry)
        dialog.format_secondary_markup(_("<i>Try to avoid spaces and special characters...</i>"))
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            sname = entry.get_text()
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            service = Service('/usr/lib/linuxmint/mintUpload/sample.service')
            if os.path.exists(config_paths['user'] + sname):
                sname += " 2"
                while os.path.exists(config_paths['user'] + sname):
                    next = int(sname[-1:]) + 1
                    sname = sname[:-1] + str(next)
            service.filename = config_paths['user'] + sname
            service.write()
            self.services.append(service)
            model = treeview_services.get_model()
            iter = model.insert_before(None, None)
            model.set_value(iter, 0, sname)
            self.edit_service(treeview_services, model.get_path(iter))

    def check_service_name(self, entry, dialog):
        text = entry.get_text()
        valid = True
        if text == "":
            valid = False
        if " " in text:
            valid = False
        invalidChars = set(string.punctuation.replace("_", ""))
        if any(char in invalidChars for char in text):
            valid = False
        dialog.get_widget_for_response(gtk.RESPONSE_OK).set_sensitive(valid)

    def remove_service(self, widget, treeview_services):
        (model, iter) = treeview_services.get_selection().get_selected()
        if (iter != None):
            service = model.get_value(iter, 0)
            for s in self.services:
                if s['name'] == service:
                    s.remove()
                    self.services.remove(s)
            model.remove(iter)

    def reload_services(self, treeview_services):
        model = gtk.TreeStore(str)
        model.set_sort_column_id(0, gtk.SORT_ASCENDING)
        treeview_services.set_model(model)

        self.services = read_services()
        for service in self.services:
            iter = model.insert_before(None, None)
            model.set_value(iter, 0, service['name'])
        del model

    def edit_service_from_tree(self, widget, path, column, treeview_services):
        self.edit_service(treeview_services, path)

    def edit_service_from_button(self, widget, treeview_services):
        selection = treeview_services.get_selection()
        (model, iter) = selection.get_selected()
        if iter is not None:
            self.edit_service(treeview_services, model.get_path(iter))

    def edit_service(self, treeview_services, path):
        model = treeview_services.get_model()
        iter = model.get_iter(path)
        sname = model.get_value(iter, 0)
        file = config_paths['user'] + sname

        wTree = gtk.glade.XML("/usr/lib/linuxmint/mintUpload/mintUpload.glade", "dialog_edit_service")
        self.wTree = wTree
        wTree.get_widget("dialog_edit_service").set_title(_("%s Properties") % sname)
        wTree.get_widget("dialog_edit_service").set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")
        wTree.get_widget("dialog_edit_service").show()
        wTree.get_widget("label_advanced").set_text(_("Advanced settings"))
        wTree.get_widget("button_verify").set_label(_("Check connection"))
        wTree.get_widget("button_verify").connect("clicked", self.check_connection, file)
        wTree.get_widget("button_cancel").connect("clicked", self.close_window, wTree.get_widget("dialog_edit_service"))

        #i18n
        wTree.get_widget("lbl_type").set_label(_("Type:"))
        wTree.get_widget("lbl_hostname").set_label(_("Host:"))
        wTree.get_widget("lbl_port").set_label(_("Port:"))
        wTree.get_widget("lbl_username").set_label(_("User:"))
        wTree.get_widget("lbl_password").set_label(_("Password:"))
        wTree.get_widget("lbl_timestamp").set_label(_("Timestamp:"))
        wTree.get_widget("lbl_path").set_label(_("Path:"))

        wTree.get_widget("lbl_hostname").set_tooltip_text(_("Hostname or IP address, default: ") + defaults['host'])
        wTree.get_widget("txt_host").set_tooltip_text(_("Hostname or IP address, default: ") + defaults['host'])
        wTree.get_widget("txt_host").connect("focus-out-event", self.change, file)

        wTree.get_widget("lbl_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))
        wTree.get_widget("txt_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))
        wTree.get_widget("txt_port").connect("focus-out-event", self.change, file)

        wTree.get_widget("lbl_username").set_tooltip_text(_("Username, defaults to your local username"))
        wTree.get_widget("txt_user").set_tooltip_text(_("Username, defaults to your local username"))
        wTree.get_widget("txt_user").connect("focus-out-event", self.change, file)

        wTree.get_widget("lbl_password").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))
        wTree.get_widget("txt_pass").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))
        wTree.get_widget("txt_pass").connect("focus-out-event", self.change, file)

        wTree.get_widget("lbl_timestamp").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])
        wTree.get_widget("txt_format").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])
        wTree.get_widget("txt_format").connect("focus-out-event", self.change, file)

        wTree.get_widget("lbl_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))
        wTree.get_widget("txt_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))
        wTree.get_widget("txt_path").connect("focus-out-event", self.change, file)

        try:
            config = Service(file)
            try:
                model = wTree.get_widget("combo_type").get_model()
                iter = model.get_iter_first()
                while (iter != None and model.get_value(iter, 0).lower() != config['type'].lower()):
                    iter = model.iter_next(iter)
                wTree.get_widget("combo_type").set_active_iter(iter)
                wTree.get_widget("combo_type").connect("changed", self.change, None, file)
            except:
                pass
            try:
                wTree.get_widget("txt_host").set_text(config['host'])
            except:
                wTree.get_widget("txt_host").set_text("")
            try:
                wTree.get_widget("txt_port").set_text(str(config['port']))
            except:
                wTree.get_widget("txt_port").set_text("")
            try:
                wTree.get_widget("txt_user").set_text(config['user'])
            except:
                wTree.get_widget("txt_user").set_text("")
            try:
                wTree.get_widget("txt_pass").set_text(config['pass'])
            except:
                wTree.get_widget("txt_pass").set_text("")
            try:
                wTree.get_widget("txt_format").set_text(config['format'])
            except:
                wTree.get_widget("txt_format").set_text("")
            try:
                wTree.get_widget("txt_path").set_text(config['path'])
            except:
                wTree.get_widget("txt_path").set_text("")
        except Exception, detail:
            print detail

    def check_connection(self, widget, file):
        service = Service(file)
        os.system("mintupload \"" + service['name'] + "\" /usr/lib/linuxmint/mintUpload/mintupload.readme &")

    def get_port_for_service(self, type):
        if type in ("Mint", "FTP"):
            num = "21"
        else:
            num = "22"
        self.wTree.get_widget("txt_port").set_text(num)
        return num

    def change(self, widget, event, file):
        try:
            wname = widget.get_name()
            if wname == "combo_type":
                model = widget.get_model()
                iter = widget.get_active_iter()
                config = {'type': model.get_value(iter, 0).lower(),
                          'port': self.get_port_for_service(model.get_value(iter, 0))}
            else:
                config = {wname[4:]: widget.get_text()}
            s = Service(file)
            s.merge(config)
            s.write()
        except Exception as e:
            try: raise CustomError(_("Could not save configuration change"), e)
            except: pass

    def close_window(self, widget, window):
        window.hide()


window = ManagerWindow()
gtk.main()
