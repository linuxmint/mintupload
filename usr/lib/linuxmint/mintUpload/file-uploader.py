#!/usr/bin/env python

import os, sys, commands
import gtk
import gtk.glade
import pygtk
pygtk.require("2.0")
import gettext
import time
from mintUploadCore import *
#import pyinotify
#from pyinotify import WatchManager, Notifier, ThreadedNotifier, ProcessEvent
import threading
import urllib

# i18n
gettext.install("mintupload", "/usr/share/linuxmint/locale")

global shutdown_flag
shutdown_flag = False

class NotifyThread(threading.Thread):
    def __init__(self, mainClass):
        threading.Thread.__init__(self)
        self.mainClass = mainClass

    def run(self):
        #wm = WatchManager()
        #mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MODIFY
        #notifier = Notifier(wm, PTmp(self.mainClass))
        #for loc, path in config_paths.iteritems():
        #       wdd = wm.add_watch(path, mask, rec=True)
        global shutdown_flag
        while not shutdown_flag:
            try:
                time.sleep(1)
                self.mainClass.reload_services()
                # process the queue of events as explained above
                #notifier.process_events()
                #if notifier.check_events():
                #       # read notified events and enqeue them
                #       notifier.read_events()
            except:
                # destroy the inotify's instance on this interrupt (stop monitoring)
                #notifier.stop()
                #break
                pass
        #print "out of the loop"

#class PTmp(ProcessEvent):
#       def __init__(self, mainClass):
#               self.mainClass = mainClass
#
#       def process_IN_CREATE(self, event):
#               #print "Create: %s" %  os.path.join(event.path, event.name)
#               self.mainClass.reload_services()
#
#       def process_IN_DELETE(self, event):
#               #print "Remove: %s" %  os.path.join(event.path, event.name)
#               self.mainClass.reload_services()
#
#       def process_IN_MODIFY(self, event):
#               #print "Modify: %s" %  os.path.join(event.path, event.name)
#               self.mainClass.reload_services()
#
#       def process_default(self, event):
#               #print "Default event on: %s" %  os.path.join(event.path, event.name)
#               self.mainClass.reload_services()

class MainClass:

    def __init__(self):
        self.dropZones = {}

        self.statusIcon = gtk.StatusIcon()
        self.statusIcon.set_from_file("/usr/lib/linuxmint/mintUpload/systray.svg")
        try:
            desktop = os.environ["DESKTOP_SESSION"].lower()  
            if desktop == "mate":
	       self.statusIcon.set_from_icon_name("up")
        except Exception, detail:
            print detail
        self.statusIcon.set_tooltip(_("Upload services"))
        self.statusIcon.set_visible(True)

        self.statusIcon.connect('popup-menu', self.popup_menu_cb)
        self.statusIcon.connect('activate', self.show_menu_cb)

        self.reload_services()
        notifyT = NotifyThread(self)
        notifyT.start()

    def reload_services(self):
        self.services = read_services()
        self.menu = gtk.Menu()
        servicesMenuItem = gtk.ImageMenuItem()
        title = gtk.Label()
        title.set_text("<b><span foreground=\"grey\">" + _("Services:") + "</span></b>")
        title.set_justify(gtk.JUSTIFY_LEFT)
        title.set_alignment(0, 0.5)
        title.set_use_markup(True)
        servicesMenuItem.add(title)
        self.menu.append(servicesMenuItem)
        for service in self.services:
            serviceMenuItem = gtk.MenuItem(label="   " + service['name'])
            serviceMenuItem.connect("activate", self.createDropZone, service)
            self.menu.append(serviceMenuItem)

        self.menu.append(gtk.SeparatorMenuItem())

        uploadManagerMenuItem = gtk.MenuItem(_("Upload manager..."))
        uploadManagerMenuItem.connect('activate', self.launch_manager)
        self.menu.append(uploadManagerMenuItem)

        self.menu.append(gtk.SeparatorMenuItem())

        menuItem = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        menuItem.connect('activate', self.quit_cb)
        self.menu.append(menuItem)
        self.menu.show_all()

    def launch_manager(self, widget):
        os.system("/usr/lib/linuxmint/mintUpload/upload-manager.py &")

    def createDropZone(self, widget, service):
        if service['name'] not in self.dropZones.keys():
            dropZone = DropZone(self.statusIcon, self.menu, service, self.dropZones)
            self.dropZones[service['name']] = dropZone
        else:
            self.dropZones[service['name']].show()

    def quit_cb(self, widget):
        self.statusIcon.set_visible(False)
        global shutdown_flag
        shutdown_flag = True
        gtk.main_quit()
        sys.exit(0)

    def show_menu_cb(self, widget):
        self.menu.popup(None, None, self.menu_pos, 0, gtk.get_current_event_time())

    def popup_menu_cb(self, widget, button, activate_time):
        self.menu.popup(None, None, self.menu_pos, button, activate_time)

    def menu_pos(self, menu):
        return gtk.status_icon_position_menu(self.menu, self.statusIcon)


class DropZone():

    def __init__(self, statusIcon, menu, service, dropZones):
        self.service = service
        self.statusIcon = statusIcon
        self.dropZones = dropZones
        self.menu = menu
        self.w = gtk.Window()

        TARGET_TYPE_TEXT = 80
        self.w.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP, [ ( "text/uri-list", 0, TARGET_TYPE_TEXT ) ], gtk.gdk.ACTION_MOVE|gtk.gdk.ACTION_COPY)
        self.w.connect('drag_motion', self.motion_cb)
        self.w.connect('drag_drop', self.drop_cb)
        self.w.connect('drag_data_received', self.drop_data_received_cb)
        self.w.connect('destroy', self.destroy_cb)  
        self.w.set_icon_from_file("/usr/lib/linuxmint/mintUpload/icon.svg")
        self.w.set_title(self.service['name'])
        self.w.set_keep_above(True)
        self.w.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
        self.w.set_skip_pager_hint(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.stick()

        pos = gtk.status_icon_position_menu(self.menu, self.statusIcon)
        posY = len(self.dropZones) * 80
        self.w.move(pos[0], pos[1] + 50 - posY)

        self.label = gtk.Label()
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
        context.drag_status(gtk.gdk.ACTION_COPY, time)
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

gtk.gdk.threads_init()
MainClass()
gtk.main()
