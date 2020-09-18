#!/usr/bin/python3

import os
import sys
import gettext
import time
import threading
import urllib.request, urllib.parse, urllib.error

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("XApp", "1.0")
from gi.repository import Gtk, Gdk, GLib, XApp
from mintupload_core import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

# Name of the icon used by the indicator
SYSTRAY_ICON = "mintupload-tray-symbolic"

class MainClass:

    def __init__(self):
        self.drop_zones = {}
        self.services = None

        self.build_services_menu()
        # Refresh list of services in the menu every 2 seconds
        GLib.timeout_add_seconds(2, self.reload_services)

        self.status_icon = XApp.StatusIcon()
        self.status_icon.set_name("mintupload")
        self.status_icon.set_icon_name(SYSTRAY_ICON)
        self.status_icon.set_tooltip_text(_("Upload services"))
        self.status_icon.set_primary_menu(self.menu)
        self.status_icon.set_secondary_menu(self.menu)

    def reload_services(self):
        has_changed = read_services() != self.services

        if has_changed and not self.menu.is_visible():
            self.build_services_menu()

        return True

    def build_services_menu(self):
        self.services = read_services()
        self.menu = Gtk.Menu()
        services_menuitem = Gtk.MenuItem()
        title = Gtk.Label()
        title.set_text("<b>" + _("Services:") + "</b>")
        title.set_xalign(0)
        title.set_use_markup(True)
        services_menuitem.add(title)
        services_menuitem.set_sensitive(False)
        self.menu.append(services_menuitem)

        for service in self.services:
            service_menuitem = Gtk.MenuItem(label="   " + service['name'])
            service_menuitem.connect("activate", self.create_drop_zone, service)
            self.menu.append(service_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        upload_manager_menuitem = Gtk.MenuItem(label=_("Upload manager..."))
        upload_manager_menuitem.connect('activate', self.launch_manager)
        self.menu.append(upload_manager_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        menu_item = Gtk.MenuItem(label=_("Quit"))
        menu_item.connect('activate', self.quit_cb)
        self.menu.append(menu_item)
        self.menu.show_all()

    def launch_manager(self, widget):
        os.system("/usr/lib/linuxmint/mintupload/upload-manager.py &")

    def create_drop_zone(self, widget, service):
        if service['name'] not in list(self.drop_zones.keys()):
            drop_zone = DropZone(service, self.drop_zones)
            self.drop_zones[service['name']] = drop_zone
        else:
            self.drop_zones[service['name']].show()

    def quit_cb(self, widget):
        Gtk.main_quit()
        sys.exit(0)

class DropZone:

    DROPZONE_CSS = b'''
    .dropzone {
        border-width: 3px;
        border-style: dashed;
        border-radius: 1em;
    }
    .dropzone:drop(active) {
        border-style: solid;
    }
    '''

    def __init__(self, service, drop_zones):
        self.service = service
        self.drop_zones = drop_zones
        self.w = Gtk.Window()

        TARGET_TYPE_TEXT = 80

        self.w.set_icon_name(SYSTRAY_ICON)
        self.w.set_title(self.service['name'])
        self.w.set_keep_above(True)
        self.w.set_skip_pager_hint(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.stick()

        self.label = Gtk.Label(margin=10)
        self.label.set_text(_("Drag &amp; Drop here to upload to %s") % self.service['name'])
        self.label.set_line_wrap(True)
        self.label.set_use_markup(True)
        self.label.set_width_chars(20)

        # add dashed border around label
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(self.DROPZONE_CSS)
        self.box = Gtk.Box(margin=10)
        style_ctx = self.box.get_style_context()
        style_ctx.add_class("dropzone")
        style_ctx.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.box.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("text/uri-list", 0, TARGET_TYPE_TEXT)],
            Gdk.DragAction.MOVE | Gdk.DragAction.COPY
        )

        self.box.connect('drag-drop', self.drop_cb)
        self.box.connect('drag-data-received', self.drop_data_received_cb)
        self.box.connect('destroy', self.destroy_cb)

        self.box.set_center_widget(self.label)
        self.w.add(self.box)

        self.w.set_default_size(300, 100)
        self.w.show_all()

        if Gdk.Screen.get_default().is_composited():
            self.w.set_opacity(0.7)

    def show(self):
        self.w.show_all()
        self.w.present()

    def drop_cb(self, wid, context, x, y, time):
        context.finish(True, False, time)
        return True

    def drop_data_received_cb(self, widget, context, x, y, selection, targetType, time):
        data = selection.get_data().decode()
        filenames = []
        files = data.split('\n')

        for f in files:
            if not f:
                continue
            f = urllib.request.url2pathname(f)
            f = f.strip('\r')
            f = f.replace("file://", "")
            f = f.replace("'", r"'\''")
            f = "'" + f + "'"
            filenames.append(f)

        os.system("mintupload \"" + self.service['name'] + "\" " + " ".join(filenames) + " &")

    def destroy_cb(self, wid):
        del self.drop_zones[self.service['name']]

MainClass()
Gtk.main()
