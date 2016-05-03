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
from gi.repository import Gtk, Gdk, GLib

from mintupload_core import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

# Location of the systray icon file
SYSTRAY_ICON = "/usr/share/pixmaps/mintupload/systray.svg"


class MainClass:

    def __init__(self):
        self.drop_zones = {}

        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_from_file(SYSTRAY_ICON)

        try:
            desktop = os.environ["DESKTOP_SESSION"].lower()
            if desktop == "mate":
                self.status_icon.set_from_icon_name("up")
        except Exception, detail:
            print detail

        self.status_icon.set_tooltip_text(_("Upload services"))
        self.status_icon.set_visible(True)

        self.status_icon.connect('popup-menu', self.popup_menu_cb)
        self.status_icon.connect('activate', self.show_menu_cb)

        self.menu = Gtk.Menu()
        # Refresh list of services in the menu every 3 seconds
        GLib.timeout_add_seconds(3, self.reload_services)

    def reload_services(self):
        if self.menu.is_visible():
            return True

        self.services = read_services()
        self.menu = Gtk.Menu()
        services_menuitem = Gtk.ImageMenuItem()
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

        menu_item = Gtk.ImageMenuItem(Gtk.STOCK_QUIT)
        menu_item.connect('activate', self.quit_cb)
        self.menu.append(menu_item)
        self.menu.show_all()

        return True

    def launch_manager(self, widget):
        os.system("/usr/lib/linuxmint/mintupload/upload-manager.py &")

    def create_drop_zone(self, widget, service):
        if service['name'] not in self.drop_zones.keys():
            drop_zone = DropZone(self.status_icon, self.menu, service, self.drop_zones)
            self.drop_zones[service['name']] = drop_zone
        else:
            self.drop_zones[service['name']].show()

    def quit_cb(self, widget):
        self.status_icon.set_visible(False)
        Gtk.main_quit()
        sys.exit(0)

    def show_menu_cb(self, widget):
        self.menu.popup(None, None, self.menu_pos, None, 0, Gtk.get_current_event_time())

    def popup_menu_cb(self, widget, button, activate_time):
        self.menu.popup(None, None, self.menu_pos, None, button, activate_time)

    def menu_pos(self, menu, x, y, *args):
        return self.status_icon.position_menu(self.menu, x, y, self.status_icon)


class DropZone:

    def __init__(self, status_icon, menu, service, drop_zones):
        self.service = service
        self.status_icon = status_icon
        self.drop_zones = drop_zones
        self.menu = menu
        self.w = Gtk.Window()

        TARGET_TYPE_TEXT = 80
        self.w.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP, [("text/uri-list", 0, TARGET_TYPE_TEXT)], Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        self.w.connect('drag_motion', self.motion_cb)
        self.w.connect('drag_drop', self.drop_cb)
        self.w.connect('drag_data_received', self.drop_data_received_cb)
        self.w.connect('destroy', self.destroy_cb)
        self.w.set_icon_from_file(SYSTRAY_ICON)
        self.w.set_title(self.service['name'])
        self.w.set_keep_above(True)
        self.w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.w.set_skip_pager_hint(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.stick()

        pos = Gtk.status_icon_position_menu(self.menu, self.status_icon)
        posY = len(self.drop_zones) * 80
        self.w.move(pos[0], pos[1] + 50 - posY)

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
        context.drag_status(Gdk.DragAction.COPY, time)
        return True

    def drop_cb(self, wid, context, x, y, time):
        context.finish(True, False, time)
        return True

    def drop_data_received_cb(self, widget, context, x, y, selection, targetType, time):
        filenames = []
        files = selection.data.split('\n')
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
