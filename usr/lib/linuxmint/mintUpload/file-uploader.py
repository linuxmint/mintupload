#!/usr/bin/python2

import os
import sys
import gettext
import time
import threading
import urllib

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from mintUploadCore import *

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

global shutdown_flag
shutdown_flag = False


class NotifyThread(threading.Thread):

    def __init__(self, mainClass):
        threading.Thread.__init__(self)
        self.mainClass = mainClass

    def run(self):
        global shutdown_flag
        while not shutdown_flag:
            try:
                time.sleep(1)
                self.mainClass.reload_services()
            except:
                pass


class MainClass:

    def __init__(self):
        self.dropZones = {}

        self.statusIcon = Gtk.StatusIcon()
        self.statusIcon.set_from_file("/usr/lib/linuxmint/mintUpload/systray.svg")

        try:
            desktop = os.environ["DESKTOP_SESSION"].lower()
            if desktop == "mate":
                self.statusIcon.set_from_icon_name("up")
        except Exception, detail:
            print detail

        self.statusIcon.set_tooltip_text(_("Upload services"))
        self.statusIcon.set_visible(True)

        self.statusIcon.connect('popup-menu', self.popup_menu_cb)
        self.statusIcon.connect('activate', self.show_menu_cb)

        self.reload_services()
        notifyT = NotifyThread(self)
        notifyT.start()

    def reload_services(self):
        self.services = read_services()
        self.menu = Gtk.Menu()
        servicesMenuItem = Gtk.ImageMenuItem()
        title = Gtk.Label()
        title.set_text("<b><span foreground=\"grey\">" + _("Services:") + "</span></b>")
        title.set_justify(Gtk.Justification.LEFT)
        title.set_alignment(0, 0.5)
        title.set_use_markup(True)
        servicesMenuItem.add(title)
        self.menu.append(servicesMenuItem)

        for service in self.services:
            serviceMenuItem = Gtk.MenuItem(label="   " + service['name'])
            serviceMenuItem.connect("activate", self.create_drop_zone, service)
            self.menu.append(serviceMenuItem)

        self.menu.append(Gtk.SeparatorMenuItem())

        uploadManagerMenuItem = Gtk.MenuItem(_("Upload manager..."))
        uploadManagerMenuItem.connect('activate', self.launch_manager)
        self.menu.append(uploadManagerMenuItem)

        self.menu.append(Gtk.SeparatorMenuItem())

        menuItem = Gtk.ImageMenuItem(Gtk.STOCK_QUIT)
        menuItem.connect('activate', self.quit_cb)
        self.menu.append(menuItem)
        self.menu.show_all()

    def launch_manager(self, widget):
        os.system("/usr/lib/linuxmint/mintUpload/upload-manager.py &")

    def create_drop_zone(self, widget, service):
        if service['name'] not in self.dropZones.keys():
            dropZone = DropZone(self.statusIcon, self.menu, service, self.dropZones)
            self.dropZones[service['name']] = dropZone
        else:
            self.dropZones[service['name']].show()

    def quit_cb(self, widget):
        self.statusIcon.set_visible(False)
        global shutdown_flag
        shutdown_flag = True
        Gtk.main_quit()
        sys.exit(0)

    def show_menu_cb(self, widget):
        self.menu.popup(None, None, self.menu_pos, None, 0, Gtk.get_current_event_time())

    def popup_menu_cb(self, widget, button, activate_time):
        self.menu.popup(None, None, self.menu_pos, None, button, activate_time)

    def menu_pos(self, menu, fake):
        return self.statusIcon.position_menu(self.menu, self.statusIcon)


class DropZone:

    def __init__(self, statusIcon, menu, service, dropZones):
        self.service = service
        self.statusIcon = statusIcon
        self.dropZones = dropZones
        self.menu = menu
        self.w = Gtk.Window()

        TARGET_TYPE_TEXT = 80
        self.w.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP, [("text/uri-list", 0, TARGET_TYPE_TEXT)], Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        self.w.connect('drag_motion', self.motion_cb)
        self.w.connect('drag_drop', self.drop_cb)
        self.w.connect('drag_data_received', self.drop_data_received_cb)
        self.w.connect('destroy', self.destroy_cb)
        self.w.set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")
        self.w.set_title(self.service['name'])
        self.w.set_keep_above(True)
        self.w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.w.set_skip_pager_hint(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.stick()

        pos = Gtk.status_icon_position_menu(self.menu, self.statusIcon)
        posY = len(self.dropZones) * 80
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
        del self.dropZones[self.service['name']]

Gdk.threads_init()
Gdk.threads_enter()
MainClass()
Gtk.main()
Gdk.threads_leave()
