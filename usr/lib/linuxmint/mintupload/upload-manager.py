#!/usr/bin/python3

import os
import gettext
import string
import shlex

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from mintupload_core import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

# Location of the ui file
UI_FILE = "/usr/share/linuxmint/mintupload/manager_window.ui"

class MyApplication(Gtk.Application):
    # Main initialization routine
    def __init__(self, application_id, flags):
        Gtk.Application.__init__(self, application_id=application_id, flags=flags)
        self.connect("activate", self.activate)

    def activate(self, application):
        windows = self.get_windows()
        if (len(windows) > 0):
            window = windows[0]
            window.present()
            window.show()
        else:
            window = ManagerWindow(self)
            self.add_window(window.window)
            window.window.show()

class ManagerWindow:

    def __init__(self, application):
        self.application = application
        self.builder = Gtk.Builder()
        self.builder.add_from_file(UI_FILE)

        self.window = self.builder.get_object("manager_window")
        self.window.set_title(_("Upload Manager"))
        self.window.set_icon_name(ICON)

        treeview_services = self.builder.get_object("treeview_services")

        # the treeview
        column1 = Gtk.TreeViewColumn(_("Upload services"), Gtk.CellRendererText(), text=0)
        column1.set_sort_column_id(0)
        column1.set_resizable(True)

        treeview_services.append_column(column1)
        treeview_services.set_headers_clickable(True)
        treeview_services.set_reorderable(False)
        treeview_services.show()

        self.reload_services(treeview_services)

        self.builder.get_object("toolbutton_add").connect("clicked", self.add_service, treeview_services)
        self.builder.get_object("toolbutton_edit").connect("clicked", self.edit_service_from_button, treeview_services)
        self.builder.get_object("toolbutton_remove").connect("clicked", self.remove_service, treeview_services)

        treeview_services.connect("row_activated", self.edit_service_from_tree, treeview_services)

        fileMenu = Gtk.MenuItem.new_with_mnemonic(_("_File"))
        fileSubmenu = Gtk.Menu()
        fileMenu.set_submenu(fileSubmenu)
        closeMenuItem = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_CLOSE)
        closeMenuItem.set_label(_("Close"))
        closeMenuItem.connect("activate", Gtk.main_quit)
        fileSubmenu.append(closeMenuItem)

        helpMenu = Gtk.MenuItem.new_with_mnemonic(_("_Help"))
        helpSubmenu = Gtk.Menu()
        helpMenu.set_submenu(helpSubmenu)
        aboutMenuItem = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ABOUT)
        aboutMenuItem.set_label(_("About"))
        aboutMenuItem.connect("activate", self.open_about)
        helpSubmenu.append(aboutMenuItem)

        self.builder.get_object("menubar1").append(fileMenu)
        self.builder.get_object("menubar1").append(helpMenu)
        self.builder.get_object("manager_window").show_all()

    def open_about(self, widget):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(self.window)
        dlg.set_title(_("About") + " - mintupload")
        dlg.set_version("__DEB_VERSION__")
        dlg.set_program_name("mintupload")
        dlg.set_comments(_("Upload Manager"))

        try:
            h = open('/usr/share/common-licenses/GPL', 'r')
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            dlg.set_license(gpl)
        except Exception as detail:
            print(detail)

        dlg.set_authors([
                        "Clement Lefebvre <root@linuxmint.com>",
                        "Philip Morrell <mintupload.emorrp1@mamber.net>",
                        "Manuel Sandoval <manuel@slashvar.com>",
                        "Dennis Schwertel <s@digitalkultur.net>"
                        ])
        dlg.set_icon_name(ICON)
        dlg.set_logo_icon_name(ICON)

        def close(w, res):
            if res == Gtk.ResponseType.DELETE_EVENT:
                w.destroy()

        dlg.connect("response", close)
        dlg.show()

    def response_to_dialog(self, entry, dialog, response):
        dialog.response(response)

    def add_service(self, widget, treeview_services):
        dialog = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, None)
        dialog.set_transient_for(self.window)
        dialog.set_title(_("Upload Manager"))
        dialog.set_icon_name(ICON)
        dialog.set_border_width(6)
        dialog.set_markup(_("<b>Please enter a name for the new upload service:</b>"))
        entry = Gtk.Entry()
        entry.connect("changed", self.check_service_name, dialog)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(_("Service name:"))
        hbox.pack_start(label, False, 5, 5)
        hbox.pack_end(entry, True, True, 0)
        dialog.format_secondary_markup(_("<i>Try to avoid spaces and special characters...</i>"))
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            sname = entry.get_text()

        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            service = Service('/usr/share/linuxmint/mintupload/sample.service')
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
        dialog.get_widget_for_response(Gtk.ResponseType.OK).set_sensitive(valid)

    def remove_service(self, widget, treeview_services):
        (model, iter) = treeview_services.get_selection().get_selected()
        self.services = read_services()

        if iter != None:
            service = model.get_value(iter, 0)
            for s in self.services:
                if s['name'] == service:
                    s.remove()
                    self.services.remove(s)
            model.remove(iter)

    def reload_services(self, treeview_services):
        model = Gtk.TreeStore(str)
        model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
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

        dialog_edit_service = self.builder.get_object("dialog_edit_service")
        dialog_edit_service.set_transient_for(self.window)
        dialog_edit_service.set_title(_("%s Properties") % sname)
        dialog_edit_service.set_icon_name(ICON)

        self.builder.get_object("button_verify").set_label(_("Check connection"))
        self.builder.get_object("button_verify").connect("clicked", self.check_connection, file)
        self.builder.get_object("button_cancel").connect("clicked", self.close_window, self.builder.get_object("dialog_edit_service"))

        #i18n
        self.builder.get_object("lbl_type").set_label(_("Type:"))
        self.builder.get_object("lbl_hostname").set_label(_("Host:"))
        self.builder.get_object("lbl_port").set_label(_("Port:"))
        self.builder.get_object("lbl_username").set_label(_("User:"))
        self.builder.get_object("lbl_password").set_label(_("Password:"))
        self.builder.get_object("lbl_timestamp").set_label(_("Timestamp:"))
        self.builder.get_object("lbl_path").set_label(_("Path:"))

        self.builder.get_object("lbl_hostname").set_tooltip_text(_("Hostname or IP address, default: ") + defaults['host'])
        self.builder.get_object("txt_host").set_tooltip_text(_("Hostname or IP address, default: ") + defaults['host'])
        self.builder.get_object("txt_host").connect("focus-out-event", self.change, file)

        self.builder.get_object("lbl_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))
        self.builder.get_object("txt_port").set_tooltip_text(_("Remote port, default is 21 for FTP, 22 for SFTP and SCP"))
        self.builder.get_object("txt_port").connect("focus-out-event", self.change, file)

        self.builder.get_object("lbl_username").set_tooltip_text(_("Username, defaults to your local username"))
        self.builder.get_object("txt_user").set_tooltip_text(_("Username, defaults to your local username"))
        self.builder.get_object("txt_user").connect("focus-out-event", self.change, file)

        self.builder.get_object("lbl_password").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))
        self.builder.get_object("txt_pass").set_tooltip_text(_("Password, by default: password-less SCP connection, null-string FTP connection, ~/.ssh keys used for SFTP connections"))
        self.builder.get_object("txt_pass").connect("focus-out-event", self.change, file)

        self.builder.get_object("lbl_timestamp").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])
        self.builder.get_object("txt_format").set_tooltip_text(_("Timestamp format (strftime). By default:") + defaults['format'])
        self.builder.get_object("txt_format").connect("focus-out-event", self.change, file)

        self.builder.get_object("lbl_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))
        self.builder.get_object("txt_path").set_tooltip_text(_("Directory to upload to. <TIMESTAMP> is replaced with the current timestamp, following the timestamp format given. By default: ."))
        self.builder.get_object("txt_path").connect("focus-out-event", self.change, file)

        try:
            config = Service(file)
            try:
                model = self.builder.get_object("combo_type").get_model()
                iter = model.get_iter_first()

                while (iter != None and model.get_value(iter, 0).lower() != config['type'].lower()):
                    iter = model.iter_next(iter)

                self.builder.get_object("combo_type").set_active_iter(iter)
                self.builder.get_object("combo_type").connect("changed", self.change, None, file)
            except:
                pass
            try:
                self.builder.get_object("txt_host").set_text(config['host'])
            except:
                self.builder.get_object("txt_host").set_text("")
            try:
                self.builder.get_object("txt_port").set_text(str(config['port']))
            except:
                self.builder.get_object("txt_port").set_text("")
            try:
                self.builder.get_object("txt_user").set_text(config['user'])
            except:
                self.builder.get_object("txt_user").set_text("")
            try:
                self.builder.get_object("txt_pass").set_text(config['pass'])
            except:
                self.builder.get_object("txt_pass").set_text("")
            try:
                self.builder.get_object("txt_format").set_text(config['format'])
            except:
                self.builder.get_object("txt_format").set_text("")
            try:
                self.builder.get_object("txt_path").set_text(config['path'])
            except:
                self.builder.get_object("txt_path").set_text("")
        except Exception as detail:
            print(detail)

        dialog_edit_service.run()
        dialog_edit_service.hide()

    def check_connection(self, widget, file):
        service = Service(file)
        os.system(f"mintupload {shlex.quote(service['name'])} /usr/share/linuxmint/mintupload/mintupload.readme &")

    def get_port_for_service(self, type):
        num = "21" if type in ("Mint", "FTP") else "22"

        self.builder.get_object("txt_port").set_text(num)
        return num

    def change(self, widget, event, file):
        try:
            wname = Gtk.Buildable.get_name(widget)

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
            try:
                raise CustomError(_("Could not save configuration change"), e)
            except:
                pass

    def close_window(self, widget, window):
        window.hide()

if __name__ == "__main__":
    application = MyApplication("com.linuxmint.mintupload", Gio.ApplicationFlags.FLAGS_NONE)
    application.run()
