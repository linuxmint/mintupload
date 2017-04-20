#!/usr/bin/python2

import os
import sys
import gettext
import time
import threading
import urllib

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import Gtk, Gdk, GLib
from gi.repository import AppIndicator3 as AppIndicator
from mintupload_core import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

# Name of the icon used by the indicator
SYSTRAY_ICON = "mintupload-tray"

class MainClass:

    def __init__(self):
        self.drop_zones = {}
        self.status_icon = AppIndicator.Indicator.new("mintupload", _("Upload services"), AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.status_icon.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.status_icon.set_icon(SYSTRAY_ICON)
        self.status_icon.set_title(_("Upload services"))

        try:
            if os.environ["XDG_CURRENT_DESKTOP"].lower() == "mate":
                self.status_icon.set_icon("up")
        except Exception, detail:
            print detail

        self.services = None

        self.build_services_menu()
        # Refresh list of services in the menu every 2 seconds
        GLib.timeout_add_seconds(2, self.reload_services)

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
        title.set_text("<b><span foreground=\"grey\">" + _("Services:") + "</span></b>")
        title.set_justify(Gtk.Justification.LEFT)
        title.set_alignment(0, 0.5)
        title.set_use_markup(True)
        services_menuitem.add(title)
        self.menu.append(services_menuitem)

        for service in self.services:
            service_menuitem = Gtk.MenuItem(label="   " + service['name'])
            service_menuitem.connect("activate", self.create_drop_zone, service)
            self.menu.append(service_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        upload_manager_menuitem = Gtk.MenuItem(_("Upload manager..."))
        upload_manager_menuitem.connect('activate', self.launch_manager)
        self.menu.append(upload_manager_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        menu_item = Gtk.MenuItem()
        menu_item = Gtk.ImageMenuItem(Gtk.STOCK_CLOSE)
        menu_item.set_use_stock(True)
        menu_item.set_label(_("Quit"))
        menu_item.connect('activate', self.quit_cb)
        self.menu.append(menu_item)
        self.menu.show_all()
        self.status_icon.set_menu(self.menu)

    def launch_manager(self, widget):
        os.system("/usr/lib/linuxmint/mintupload/upload-manager.py &")

    def create_drop_zone(self, widget, service):
        if service['name'] not in self.drop_zones.keys():
            drop_zone = DropZone(service, self.drop_zones)
            self.drop_zones[service['name']] = drop_zone
        else:
            self.drop_zones[service['name']].show()

    def quit_cb(self, widget):
        Gtk.main_quit()
        sys.exit(0)

class DropZone:

    def __init__(self, service, drop_zones):
        self.service = service
        self.drop_zones = drop_zones
        self.w = Gtk.Window()

        TARGET_TYPE_TEXT = 80

        self.w.drag_dest_set(
            Gtk.DestDefaults.ALL,  # Motion, Highlight, Drop
            [Gtk.TargetEntry.new("text/uri-list", 0, TARGET_TYPE_TEXT)],
            Gdk.DragAction.MOVE | Gdk.DragAction.COPY
        )

        self.w.connect('drag-motion', self.motion_cb)
        self.w.connect('drag-drop', self.drop_cb)
        self.w.connect('drag-data-received', self.drop_data_received_cb)
        self.w.connect('destroy', self.destroy_cb)

        self.w.set_icon_name(SYSTRAY_ICON)
        self.w.set_title(self.service['name'])
        self.w.set_keep_above(True)
        self.w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.w.set_skip_pager_hint(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.stick()

        display = Gdk.Display.get_default()
        (screen, x, y, mods) = display.get_pointer()
        self.w.move(x-50, y-50)

        self.label = Gtk.Label()
        self.label.set_text("<small>" + _("Drag &amp; Drop here to upload to %s") % self.service['name'] + "</small>")
        self.label.set_line_wrap(True)
        self.label.set_use_markup(True)
        self.label.set_width_chars(20)
        self.w.add(self.label)

        self.w.set_default_size(100, 50)

        if self.w.is_composited():
            self.w.set_opacity(0.5)

        self.w.show_all()

    def show(self):
        self.w.show_all()
        self.w.present()

    def motion_cb(self, wid, context, x, y, time):
        Gdk.drag_status(context, Gdk.DragAction.COPY, time)
        return True

    def drop_cb(self, wid, context, x, y, time):
        context.finish(True, False, time)
        return True

    def drop_data_received_cb(self, widget, context, x, y, selection, targetType, time):
        data = selection.get_data()

        filenames = []
        files = data.split('\n')

        for f in files:
            if not f:
                continue
            f = urllib.url2pathname(f)
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
