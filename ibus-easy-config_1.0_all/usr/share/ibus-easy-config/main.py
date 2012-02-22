#!/usr/bin/python
# coding=utf-8

import sys, os, subprocess
import ibus
try:
 	import pygtk
  	pygtk.require("2.0")
except:
  	pass
try:
    import gobject
    import pango
    import gtk
    import gtk.glade
    from gtk import gdk
    from gtk import keysyms
except:
	sys.exit(1)

sys.path.append("/usr/share/ibus/setup")
from icon import load_icon


class IBus:
    bus = None
    def __init__(self):
        try:
            self.bus = ibus.Bus()
        except:
            while self.bus == None:
                pid = os.spawnlp(os.P_NOWAIT, "ibus-daemon", "ibus-daemon", "--xim")
                os.time.sleep(1)
                try: self.bus = ibus.Bus()
                except: continue

        
        self.config = self.bus.get_config()
        self.engines = self.bus.list_engines()
        self.engineDict = {}
        self.langWiseList = {}
        for e in self.engines:
            self.engineDict[e.name] = e
            l = ibus.get_language_name(e.language)
            if l not in self.langWiseList: self.langWiseList[l] = []
            self.langWiseList[l].append(e)
        
    def getLangWiseLayout(self):
        return self.langWiseList
        
    def getShortcuts(self):
        shortcuts = self.config.get_value("general/hotkey", "trigger",
                                     ibus.CONFIG_GENERAL_SHORTCUT_TRIGGER_DEFAULT)
        return list(set(map(self.ibusToEasyShortcut, shortcuts)))

    def getPrimaryLayout(self):
        ims = self.config.get_value("general", "preload_engines", [])
        if ims: return self.engineDict[ims[0]]
        else: return None
        #engines = [self.engineDict[name] for name in ims if name in self.engineDict]
        #return engines
        
    def saveShortcuts(self, shortcuts):
        ibusShortcuts = []
        for i in shortcuts:
            ibusShortcuts.append(self.easyToIBusShortcut(i))
        self.config.set_list("general/hotkey", "trigger", ibusShortcuts, "s")
        pass
        
    def setPrimaryLayout(self, layout):
        imNames = self.config.get_value("general", "preload_engines", [])
        if layout.name in imNames: imNames.remove(layout.name)
        imNames.insert(0, layout.name)
        self.config.set_list("general", "preload_engines", imNames, "s")
        
    def ibusToEasyShortcut(self, shortcut):
        """
        shortcut str => ibus formatted shortcut
        Returns str => easy formatted shortcut
        """
        if shortcut.startswith("Release"): return shortcut[8:]
        
        for lr in ["_L", "_R"]:
            if shortcut.endswith(lr):
                lrToFull = {"_L" : "Left", "_R" : "Right"}
                parts = shortcut.rsplit("+", 1)
                return parts[0]+'+'+lrToFull[lr]+' '+parts[1][:-2]
                
        return shortcut
        
    def easyToIBusShortcut(self, shortcut):
        """
        shortcut str => easy formatted shortcut
        Returns str => ibus formatted shortcut
        """
        if '+' not in shortcut: return "Release+" + shortcut

        parts = shortcut.rsplit("+", 1)
        for lr in ["Left", "Right"]:
            if parts[1].startswith(lr):
                return parts[0]+'+'+parts[1][len(lr)+1:]+'_'+lr[0]
                                
        return shortcut
#end of my IBus Class



class EasyConfigGTK:
    """This is an Easy Config GTK application"""
    ibus = IBus()
    builder = None
    window = None
    shortcutsTreeview = None
    shortcutsListStore = None
    imTreeview = None
    imListStore = None
    
    def __init__(self):
        self.ibus = IBus()
        #Set the Glade file
        gtk_builder_file = os.path.join(os.path.dirname(__file__), "./app.glade")
        self.builder = gtk.Builder()
        self.builder.add_from_file(gtk_builder_file)
    
        #Get the Main Window, and connect the "destroy" event
        self.window = self.builder.get_object("mainDialog")
        if (self.window):
            self.window.connect("destroy", gtk.main_quit)
            self.window.show_all()

        #init shortcut list
        self.shortcutsTreeview = self.builder.get_object("shortcutsTreeview")
        self.shortcutsListStore = self.shortcutsTreeview.get_model()
        column = self.shortcutsTreeview.get_column(0)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.add_attribute(renderer, 'text', 0)

        self.populateShortcuts()
        
        #set input method/layout list
        self.layoutComboBox = self.builder.get_object("layoutComboBox")
        self.layoutTreeStore = gtk.TreeStore(gobject.TYPE_PYOBJECT)

        renderer = gtk.CellRendererPixbuf()
        #renderer.set_property("xalign", 0)
        #renderer.set_property("xpad", 2)
        self.layoutComboBox.pack_start(renderer, False)
        self.layoutComboBox.set_cell_data_func(renderer, self.renderLayoutIcon)

        renderer = gtk.CellRendererText()
        #renderer.set_property("xalign", 0)
        #renderer.set_property("xpad", 2)
        self.layoutComboBox.pack_start(renderer, True)
        self.layoutComboBox.set_cell_data_func(renderer, self.renderLayoutText)
        
        curLayout = self.ibus.getPrimaryLayout()
        curLayoutIter = None

        if curLayout == None:
            curLayoutIter = self.layoutTreeStore.append(None)
            self.layoutTreeStore.set(curLayoutIter, 0, 1)
        
        layouts = self.ibus.getLangWiseLayout()
        languages = layouts.keys()
        languages.sort()
        for lang in languages:
            langIter = self.layoutTreeStore.append(None)
            self.layoutTreeStore.set(langIter, 0, lang)
            def cmp_engine(a, b):
                if a.rank == b.rank:
                    return a.longname < b.longname
                return int(b.rank - a.rank)
            layouts[lang].sort(cmp_engine)
            for e in layouts[lang]:
                layoutIter = self.layoutTreeStore.append(langIter)
                self.layoutTreeStore.set(layoutIter, 0, e)
                if curLayout == e: curLayoutIter = layoutIter
                
        self.layoutComboBox.set_model(self.layoutTreeStore)
        self.layoutComboBox.set_active_iter(curLayoutIter)

        
        #connect signals
        self.builder.get_object("closeButton").connect("clicked", gtk.main_quit)
        self.builder.get_object("advancedSettingsButton").connect("clicked", self.on_advancedSettingsButton_clicked)
        
        self.builder.get_object("addShortcutsButton").connect("clicked", self.on_addShortcutsButton_clicked)
        self.builder.get_object("removeShortcutsButton").connect("clicked", self.on_removeShortcutsButton_clicked)
        
        self.layoutComboBox.connect("notify::active", self.onLayoutChanged)
        #TODO: add more signals and handlers
        #self.builder.get_object("AddShortcutButton").connect("clicked", self.on_addShortcutButton_clicked)
        
    
    def renderLayoutIcon(self, celllayout, renderer, model, iter):
        engine = model.get_value(iter, 0)

        if isinstance(engine, str) or isinstance (engine, unicode):
            renderer.set_property("visible", False)
            renderer.set_property("sensitive", False)
        elif isinstance(engine, int):
            renderer.set_property("visible", False)
            renderer.set_property("sensitive", False)
        else:
            renderer.set_property("visible", True)
            renderer.set_property("sensitive", True)
            pixbuf = load_icon(engine.icon, gtk.ICON_SIZE_LARGE_TOOLBAR)

            if pixbuf == None:
                pixbuf = load_icon("ibus-engine", gtk.ICON_SIZE_LARGE_TOOLBAR)
            if pixbuf == None:
                pixbuf = load_icon("gtk-missing-image", gtk.ICON_SIZE_LARGE_TOOLBAR)

            renderer.set_property("pixbuf", pixbuf)


    def renderLayoutText(self, celllayout, renderer, model, iter):
        engine = model.get_value(iter, 0)
        if isinstance (engine, str) or isinstance (engine, unicode):
            renderer.set_property("sensitive", False)
            renderer.set_property("text", engine)
            renderer.set_property("weight", pango.WEIGHT_NORMAL)
        elif isinstance(engine, int):
            renderer.set_property("sensitive", True)
            renderer.set_property("text", "Please select a layout")
            renderer.set_property("weight", pango.WEIGHT_NORMAL)
        else:
            renderer.set_property("sensitive", True)
            renderer.set_property("text", engine.longname)

    def populateShortcuts(self):
        self.shortcutsListStore.clear()
        for i in self.ibus.getShortcuts():
            self.shortcutsListStore.set(self.shortcutsListStore.append(), 0, i)
        
    def onLayoutChanged(self, comboBox, property):
        layout = self.layoutTreeStore.get_value(comboBox.get_active_iter(), 0)
        self.ibus.setPrimaryLayout(layout)
            
    def on_advancedSettingsButton_clicked(self, button):
        self.window.hide()
        while gtk.events_pending(): gtk.main_iteration()
        subprocess.call("ibus-setup")
        self.window.show()
            
    def on_addShortcutsButton_clicked(self, button):
        out = []
        dlg = gtk.MessageDialog(parent = self.window, buttons = gtk.BUTTONS_CLOSE)
        dlg.set_markup("Please press a key (or a key combination).\nThe dialog will be closed when the key is released.")
        dlg.set_title("Please press a key (or a key combination)")

        def __key_press_event(d, k, out):
            out.append(k.copy())

        def __key_release_event(d, k, out):
            d.response(gtk.RESPONSE_OK)

        dlg.connect("key-press-event", __key_press_event, out)
        dlg.connect("key-release-event", __key_release_event, None)
        id = dlg.run()
        dlg.destroy()
        if id != gtk.RESPONSE_OK or not out:
            return
        keyevent = out[len(out) - 1]
                
        masks = {
                gdk.CONTROL_MASK : "Control",
                gdk.SHIFT_MASK : "Shift",
                gdk.MOD1_MASK : "Alt",
                gdk.META_MASK : "Meta",
                gdk.SUPER_MASK : "Super",
                gdk.HYPER_MASK : "Hyper",
                }
        
        keyNames = [maskName for maskId, maskName in masks.iteritems() if keyevent.state & maskId]
        keyNames.append(gdk.keyval_name(keyevent.keyval))
        
        newShortcut = self.ibus.ibusToEasyShortcut('+'.join(keyNames))
        self.shortcutsListStore.set(self.shortcutsListStore.append(), 0, newShortcut)
        self.saveCurrentShortcuts()
        pass
        
    def on_removeShortcutsButton_clicked(self, button):
        (model, iter) = self.shortcutsTreeview.get_selection().get_selected()
        if iter == None:
            md = gtk.MessageDialog(self.window, 
            gtk.DIALOG_DESTROY_WITH_PARENT,  gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, "Please select a shortcut first to remove it")
            md.set_title("No Shortcut Selected")
            md.run()
            md.destroy()
            return
        self.shortcutsListStore.remove(iter)
        self.saveCurrentShortcuts()

    def saveCurrentShortcuts(self):
        shortcuts = [i[0] for i in self.shortcutsListStore]
        self.ibus.saveShortcuts(shortcuts)
        self.populateShortcuts()

#end of class EasyConfigGTK

hwg = EasyConfigGTK()

gtk.main()
