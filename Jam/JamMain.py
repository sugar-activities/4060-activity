import pygtk
pygtk.require('2.0')
import gtk
import pango

import os
import sys
import shutil
import commands
import random

import common.Util.Instruments
import common.Config as Config
from common.Config import scale
from common.Config import imagefile
from   gettext import gettext as _
import sugar.graphics.style as style

from Jam.Desktop import Desktop
import Jam.Picker as Picker
import Jam.Block as Block
from Jam.Toolbars import JamToolbar
from Jam.Toolbars import PlaybackToolbar
from Jam.Toolbars import common_playback_buttons
from Jam.Toolbars import BeatToolbar
from Jam.Toolbars import DesktopToolbar
from Jam.Toolbars import RecordToolbar

from common.Util.CSoundNote import CSoundNote
from common.Util.CSoundClient import new_csound_client
import common.Util.InstrumentDB as InstrumentDB
from common.Util import NoteDB

from Fillin import Fillin
from RythmGenerator import generator

from common.Generation.GenerationConstants import GenerationConstants
from common.Util.NoteDB import Note, Page
from common.Util import ControlStream
from common.Util import OS
from common.Tooltips import Tooltips

import common.Util.Network as Net

import xdrlib
import time
import gobject

from sugar.presence import presenceservice
from sugar.graphics.xocolor import XoColor

from math import sqrt

 # increase the length of heartbeat loop to remove problems with
 # wrapping during sync correction
HEARTBEAT_BUFFER = 100


class JamMain(gtk.EventBox):

    def __init__(self, activity):
        gtk.EventBox.__init__(self)

        self.activity = activity

        self.instrumentDB = InstrumentDB.getRef()
        self.noteDB = NoteDB.NoteDB()

        #-- initial settings ----------------------------------
        self.tempo = Config.PLAYER_TEMPO
        self.beatDuration = 60.0 / self.tempo
        self.ticksPerSecond = Config.TICKS_PER_BEAT * self.tempo / 60.0
        self.volume = 0.5

        self.csnd = new_csound_client()
        for i in range(0, 9):
            self.csnd.setTrackVolume(100, i)
        # csnd expects a range 0-100 for now
        self.csnd.setMasterVolume(self.volume * 100)
        self.csnd.setTempo(self.tempo)

        self.muted = False

        presenceService = presenceservice.get_instance()
        self.xoOwner = presenceService.get_owner()

        #-- Drawing -------------------------------------------
        def darken(colormap, hex):
            hexToDec = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
                        "7": 7, "8": 8, "9": 9, "A": 10, "B": 11, "C": 12,
                        "D": 13, "E": 14, "F": 15, "a": 10, "b": 11, "c": 12,
                        "d": 13, "e": 14, "f": 15}
            r = int(0.7 * (16 * hexToDec[hex[1]] + hexToDec[hex[2]]))
            g = int(0.7 * (16 * hexToDec[hex[3]] + hexToDec[hex[4]]))
            b = int(0.7 * (16 * hexToDec[hex[5]] + hexToDec[hex[6]]))
            return colormap.alloc_color(r * 256, g * 256, b * 256)

        def lighten(colormap, hex):
            hexToDec = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
                        "7": 7, "8": 8, "9": 9, "A": 10, "B": 11, "C": 12,
                        "D": 13, "E": 14, "F": 15, "a": 10, "b": 11, "c": 12,
                        "d": 13, "e": 14, "f": 15}
            r = 255 - int(0.7 * (255 - (
                        16 * hexToDec[hex[1]] + hexToDec[hex[2]])))
            g = 255 - int(0.7 * (255 - (
                        16 * hexToDec[hex[3]] + hexToDec[hex[4]])))
            b = 255 - int(0.7 * (255 - (
                        16 * hexToDec[hex[5]] + hexToDec[hex[6]])))
            return colormap.alloc_color(r * 256, g * 256, b * 256)

        xoColorKey = self.xoOwner.props.color
        if not xoColorKey:
            xoColorKey = ("#8D8D8D,#FFDDEA")
        xoColor = XoColor(xoColorKey)

        win = gtk.gdk.get_default_root_window()
        self.gc = gtk.gdk.GC(win)
        colormap = gtk.gdk.colormap_get_system()
        self.colors = {"bg": colormap.alloc_color(Config.PANEL_BCK_COLOR),
                       "black": colormap.alloc_color(
                style.COLOR_BLACK.get_html()),
                       #"Picker_Bg": colormap.alloc_color("#404040"),
                       #"Picker_Bg_Inactive": colormap.alloc_color("#808080"),
                       "Picker_Bg": colormap.alloc_color(
                style.COLOR_TOOLBAR_GREY.get_html()),
                       "Picker_Bg_Inactive": colormap.alloc_color(
                style.COLOR_BUTTON_GREY.get_html()),
                       "Picker_Fg": colormap.alloc_color(
                style.COLOR_WHITE.get_html()),
                       "Border_Active": colormap.alloc_color(
                #colormap.alloc_color("#590000"),
                xoColor.get_stroke_color()),
                       "Border_Inactive": colormap.alloc_color("#8D8D8D"),
                       "Border_Highlight": colormap.alloc_color("#FFFFFF"),
                       "Bg_Active": colormap.alloc_color(
                #colormap.alloc_color("#FFDDEA"),
                xoColor.get_fill_color()),
                       "Bg_Inactive": colormap.alloc_color("#DBDBDB"),
                       "Preview_Note_Fill": colormap.alloc_color(
                Config.BG_COLOR),
                       "Preview_Note_Border": colormap.alloc_color(
                Config.FG_COLOR),
                       "Preview_Note_Selected": colormap.alloc_color(
                style.COLOR_WHITE.get_html()),
                       "Note_Fill_Active": lighten(colormap, "#590000"),
                       # base "Border_Active"
                       "Note_Fill_Inactive": lighten(colormap, "#8D8D8D"),
                       # base "Border_Inactive"
                       "Beat_Line": colormap.alloc_color("#959595")}
        self.colors["Note_Border_Active"] = self.colors["Border_Active"]
        self.colors["Note_Border_Inactive"] = self.colors["Border_Inactive"]

        if True:  # load block clipmask
            pix = gtk.gdk.pixbuf_new_from_file(imagefile('jam-blockMask.png'))
            pixels = pix.get_pixels()
            stride = pix.get_rowstride()
            channels = pix.get_n_channels()
            bitmap = ""
            byte = 0
            shift = 0
            for j in range(pix.get_height()):
                offset = stride * j
                for i in range(pix.get_width()):
                    r = pixels[i * channels + offset]
                    if r != "\0":
                        byte += 1 << shift
                    shift += 1
                    if shift > 7:
                        bitmap += "%c" % byte
                        byte = 0
                        shift = 0
                if shift > 0:
                    bitmap += "%c" % byte
                    byte = 0
                    shift = 0
            self.blockMask = gtk.gdk.bitmap_create_from_data(
                None, bitmap, pix.get_width(), pix.get_height())

        pix = gtk.gdk.pixbuf_new_from_file(imagefile('sampleBG.png'))
        self.sampleBg = gtk.gdk.Pixmap(win, pix.get_width(), pix.get_height())
        self.sampleBg.draw_pixbuf(self.gc, pix, 0, 0, 0, 0, pix.get_width(),
                                  pix.get_height(), gtk.gdk.RGB_DITHER_NONE)
        self.sampleBg.endOffset = pix.get_width() - 5
        self.sampleNoteHeight = 7
        if True:  # load sample note clipmask
            pix = gtk.gdk.pixbuf_new_from_file(imagefile('sampleNoteMask.png'))
            pixels = pix.get_pixels()
            stride = pix.get_rowstride()
            channels = pix.get_n_channels()
            bitmap = ""
            byte = 0
            shift = 0
            for j in range(pix.get_height()):
                offset = stride * j
                for i in range(pix.get_width()):
                    r = pixels[i * channels + offset]
                    if r != "\0":
                        byte += 1 << shift
                    shift += 1
                    if shift > 7:
                        bitmap += "%c" % byte
                        byte = 0
                        shift = 0
                if shift > 0:
                    bitmap += "%c" % byte
                    byte = 0
                    shift = 0
            self.sampleNoteMask = gtk.gdk.bitmap_create_from_data(
                None, bitmap, pix.get_width(), pix.get_height())
            self.sampleNoteMask.endOffset = pix.get_width() - 3

        self.loopPitchOffset = 4
        self.loopTickOffset = 13
        self.pitchPerPixel = float(Config.NUMBER_OF_POSSIBLE_PITCHES - 1) / \
            (Block.Loop.HEIGHT - 2 * self.loopPitchOffset - \
                 self.sampleNoteHeight)
        self.pixelsPerPitch = float(Block.Loop.HEIGHT - \
            2 * self.loopPitchOffset - self.sampleNoteHeight) / \
            (Config.MAXIMUM_PITCH - Config.MINIMUM_PITCH)
        self.pixelsPerTick = Block.Loop.BEAT / float(Config.TICKS_PER_BEAT)
        self.ticksPerPixel = 1.0 / self.pixelsPerTick

        #-- Instruments ---------------------------------------
        self.instrumentImage = {}
        self.instrumentImageActive = {}
        for inst in self.instrumentDB.getSet("All"):
            if not inst.kitStage:
                self.prepareInstrumentImage(inst.instrumentId, inst.img)
            self.csnd.load_instrument(inst.name)

        #-- Loop Images ---------------------------------------
        self.loopImage = {}  # get filled in through updateLoopImage
        self.loopImageActive = {}

        #-- Key Images ----------------------------------------
        self.keyImage = {}
        self.keyImageActive = {}
        # use hardware key codes to work on any keyboard layout (hopefully)
        self.valid_shortcuts = {18: "9", 19: "0", 20: "-", 21: "=",
                                32: "O", 33: "P", 34: "[", 35: "]",
                                47: ";", 48: "'", 51: "\\",
                                60: ".", 61: "/",
                                None: " "}
        for key in self.valid_shortcuts.keys():
            self.prepareKeyImage(key)

        #-- Toolbars ------------------------------------------
        if Config.HAVE_TOOLBOX:
            from sugar.graphics.toolbarbox import ToolbarButton

            self.jamToolbar = JamToolbar(self)
            jam_toolbar_button = ToolbarButton(label=_('Jam'),
                                               page=self.jamToolbar,
                                               icon_name='voltemp')
            self.jamToolbar.show()
            jam_toolbar_button.show()
            self.activity.toolbox.toolbar.insert(jam_toolbar_button, -1)

            self.beatToolbar = BeatToolbar(self)
            beat_toolbar_button = ToolbarButton(label=_('Beat'),
                                                    page=self.beatToolbar,
                                                    icon_name='heart')
            self.beatToolbar.show()
            beat_toolbar_button.show()
            self.activity.toolbox.toolbar.insert(beat_toolbar_button, -1)

            self.desktopToolbar = DesktopToolbar(self)
            desktop_toolbar_button = ToolbarButton(label=_('Desktop'),
                                                  page=self.desktopToolbar,
                                                  icon_name='jam-presets-list')
            self.desktopToolbar.show()
            desktop_toolbar_button.show()
            self.activity.toolbox.toolbar.insert(desktop_toolbar_button, -1)

            if Config.FEATURES_MIC or Config.FEATURES_NEWSOUNDS:
                self.recordToolbar = RecordToolbar(self)
                record_toolbar_button = ToolbarButton(label=_('Record'),
                                                      page=self.recordToolbar,
                                                      icon_name='microphone')
                self.recordToolbar.show()
                record_toolbar_button.show()
                self.activity.toolbox.toolbar.insert(record_toolbar_button, -1)

            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            separator.set_expand(False)
            self.activity.toolbox.toolbar.insert(separator, -1)
            separator.show()

            common_playback_buttons(self.activity.toolbox.toolbar, self)
        else:
            self.jamToolbar = JamToolbar(self)
            self.activity.toolbox.add_toolbar(_("Jam"), self.jamToolbar)

            self.playbackToolbar = PlaybackToolbar(self)
            self.activity.toolbox.add_toolbar(_("Playback"),
                                               self.playbackToolbar)

            self.beatToolbar = BeatToolbar(self)
            self.activity.toolbox.add_toolbar(_("Beat"),
                                               self.beatToolbar)

            self.desktopToolbar = DesktopToolbar(self)
            self.activity.toolbox.add_toolbar(_("Desktop"),
                                              self.desktopToolbar)

            if Config.FEATURES_MIC or Config.FEATURES_NEWSOUNDS:
                self.recordToolbar = RecordToolbar(self)
                self.activity.toolbox.add_toolbar(_("Record"),
                                                  self.recordToolbar)

        #-- GUI -----------------------------------------------
        if True:  # GUI
            self.modify_bg(gtk.STATE_NORMAL, self.colors["bg"])  # window bg

            self.GUI = {}
            self.GUI["mainVBox"] = gtk.VBox()
            self.add(self.GUI["mainVBox"])

            #-- Desktop -------------------------------------------
            self.desktop = self.GUI["desktop"] = Desktop(self)
            self.GUI["mainVBox"].pack_start(self.GUI["desktop"])

            #-- Bank ----------------------------------------------
            separator = gtk.Label(" ")
            separator.set_size_request(-1, style.TOOLBOX_SEPARATOR_HEIGHT)
            self.GUI["mainVBox"].pack_start(separator, False)
            self.GUI["notebook"] = gtk.Notebook()
            self.GUI["notebook"].set_scrollable(True)
            self.GUI["notebook"].modify_bg(gtk.STATE_NORMAL,
                                           self.colors["Picker_Bg"])
            self.GUI["notebook"].modify_bg(gtk.STATE_ACTIVE,
                                           self.colors["Picker_Bg_Inactive"])
            self.GUI["notebook"].props.tab_vborder = style.TOOLBOX_TAB_VBORDER
            self.GUI["notebook"].props.tab_hborder = style.TOOLBOX_TAB_HBORDER
            self.GUI["notebook"].set_size_request(-1, scale(160))
            self.GUI["notebook"].connect("switch-page", self.setPicker)
            self.GUI["mainVBox"].pack_start(self.GUI["notebook"], False, False)
            self.pickers = {}
            self.pickerScroll = {}
            for type in [Picker.Instrument, Picker.Drum, Picker.Loop]:
                self.pickers[type] = type(self)

            def prepareLabel(name):
                label = gtk.Label(Tooltips.categories.get(name) or name)
                label.set_alignment(0.0, 0.5)
                label.modify_fg(gtk.STATE_NORMAL, self.colors["Picker_Fg"])
                label.modify_fg(gtk.STATE_ACTIVE, self.colors["Picker_Fg"])
                return label

            self.GUI["notebook"].append_page(self.pickers[Picker.Drum],
                                             prepareLabel(_("Drum Kits")))
            self.GUI["notebook"].append_page(self.pickers[Picker.Loop],
                                             prepareLabel(_("Loops")))

            sets = self.instrumentDB.getLabels()[:]
            sets.sort()
            for set in sets:
                page = gtk.HBox()
                page.set = set
                self.GUI["notebook"].append_page(page, prepareLabel(set))

            self.show_all()

            self.GUI["notebook"].set_current_page(0)

        #-- Keyboard ------------------------------------------
        self.key_dict = {}
        self.nextTrack = 2
        self.keyboardListener = None
        self.recordingNote = None

        self.keyMap = {}

        # default instrument
        self._updateInstrument(
            self.instrumentDB.instNamed["kalimba"].instrumentId, 0.5)
        self.instrumentStack = []

        # metronome
        page = NoteDB.Page(1, local=False)
        self.metronomePage = self.noteDB.addPage(-1, page)
        self.metronome = False

        #-- Drums ---------------------------------------------
        self.drumLoopId = None
        # use dummy values for now
        self.drumFillin = Fillin(
            2, 100, self.instrumentDB.instNamed["drum1kit"].instrumentId, 0, 1)

        #-- Desktops ------------------------------------------
        self.curDesktop = None
        # copy preset desktops
        path = Config.FILES_DIR + "/Desktops/"
        filelist = os.listdir(path)
        for file in filelist:
            shutil.copyfile(path + file, Config.TMP_DIR + '/' + file)

        #-- Network -------------------------------------------
        self.network = Net.Network()
        self.network.addWatcher(self.networkStatusWatcher)
        self.network.connectMessage(Net.HT_SYNC_REPLY,
                                    self.processHT_SYNC_REPLY)
        self.network.connectMessage(Net.HT_TEMPO_UPDATE,
                                    self.processHT_TEMPO_UPDATE)
        self.network.connectMessage(Net.PR_SYNC_QUERY,
                                    self.processPR_SYNC_QUERY)
        self.network.connectMessage(Net.PR_TEMPO_QUERY,
                                    self.processPR_TEMPO_QUERY)
        self.network.connectMessage(Net.PR_REQUEST_TEMPO_CHANGE,
                                    self.processPR_REQUEST_TEMPO_CHANGE)

        # sync
        self.syncQueryStart = {}
        self.syncTimeout = None
        self.heartbeatLoop = self.csnd.loopCreate()
        self.syncBeats = 4
        self.syncTicks = self.syncBeats * Config.TICKS_PER_BEAT
        self.offsetTicks = 0  # offset from the true heartbeat
        self.csnd.loopSetNumTicks(self.syncTicks * HEARTBEAT_BUFFER,
                                  self.heartbeatLoop)
        self.heartbeatStart = time.time()
        self.csnd.loopStart(self.heartbeatLoop)
        self.curBeat = 0
        self.beatWheelTimeout = gobject.timeout_add(100, self.updateBeatWheel)

        # data packing classes
        self.packer = xdrlib.Packer()
        self.unpacker = xdrlib.Unpacker("")

        # handle forced networking
        if self.network.isHost():
            self.updateSync()
            self.syncTimeout = gobject.timeout_add(1000, self.updateSync)
        elif self.network.isPeer():
            self.sendTempoQuery()
            self.syncTimeout = gobject.timeout_add(1000, self.updateSync)

        self.activity.connect("shared", self.shared)

        if self.activity._shared_activity:  # PEER
            self.activity._shared_activity.connect("buddy-joined",
                                                   self.buddy_joined)
            self.activity._shared_activity.connect("buddy-left",
                                                   self.buddy_left)
            self.activity.connect("joined", self.joined)
            self.network.setMode(Net.MD_WAIT)

        #-- Final Set Up --------------------------------------
        self.setVolume(self.volume)
        self.setTempo(self.tempo)
        if not Config.HAVE_TOOLBOX:
            self.activity.toolbox.set_current_toolbar(1)  # JamToolbar
        self.setDesktop(0, True)

    #==========================================================

    def onActivate(self, arg):
        pass

    def onDeactivate(self):
        pass

    def onDestroy(self):
        self.network.shutdown()

        #clear up scratch folder
        path = Config.TMP_DIR
        filelist = os.listdir(path)
        for file in filelist:
            os.remove(path + '/' + file)

    #==========================================================
    # Playback

    def onKeyPress(self, widget, event):
        key = event.hardware_keycode

        if key in self.keyMap.keys():
            activate = True
            for block in self.keyMap[key]:
                if block.isActive():
                    activate = False
                    break
            if activate:
                for block in self.keyMap[key]:
                    if not block.isActive():
                        if block.type == Block.Drum:
                            self.desktop.activateDrum(block)
                        elif block.type == Block.Loop:
                            self.desktop.activateLoop(block)
            else:
                for block in self.keyMap[key]:
                    if block.isActive():
                        if   block.type == Block.Drum:
                            self.desktop.deactivateDrum(block)
                        elif block.type == Block.Loop:
                            self.desktop.deactivateLoop(block)
            return

        if key in self.key_dict:  # repeated press
            return

        if key in Config.KEY_MAP_PIANO:
            pitch = Config.KEY_MAP_PIANO[key]
            inst = self.instrumentDB.instId[self.instrument["id"]]

            if inst.kit:  # drum kit
                if pitch in GenerationConstants.DRUMPITCH:
                    pitch = GenerationConstants.DRUMPITCH[pitch]
                csnote = self._playNote(
                             # trackVol * noteVol
                    key, 36, self.instrument["amplitude"] * 0.5,
                    self.instrument["pan"], 100,
                    self.instrumentDB.instNamed[inst.kit[pitch]].instrumentId,
                    self.instrument["reverb"])
            else:
                if event.state == gtk.gdk.MOD1_MASK:
                    pitch += 5

                # Percussions resonance
                if inst.csoundInstrumentId == Config.INST_PERC:
                    duration = 60
                else:
                    duration = -1

                csnote = self._playNote(
                                # trackVol * noteVol
                    key, pitch, self.instrument["amplitude"] * 0.5,
                    self.instrument["pan"], duration, self.instrument["id"],
                    self.instrument["reverb"])

            if self.keyboardListener:
                self.keyboardListener.recordNote(csnote.pitch)
                self.recordingNote = True

    def onKeyRelease(self, widget, event):
        key = event.hardware_keycode

        if key in self.key_dict:
            self._stopNote(key)

        if self.recordingNote:
            if self.keyboardListener:
                self.keyboardListener.finishNote()
            self.recordingNote = False

    def _playNote(self, key, pitch, amplitude, pan, duration, instrumentId,
                  reverb):
        self.key_dict[key] = CSoundNote(
            # onset
            0, pitch, amplitude, pan, duration, self.nextTrack, instrumentId,
            reverbSend=reverb, tied=True, mode='mini')
        self.nextTrack += 1
        if self.nextTrack > 8:
            self.nextTrack = 2
        self.csnd.play(self.key_dict[key], 0.3)

        return self.key_dict[key]

    def _stopNote(self, key):
        csnote = self.key_dict[key]
        if self.instrumentDB.instId[csnote.instrumentId].csoundInstrumentId \
                == Config.INST_TIED:
            csnote.duration = .5
            csnote.decay = 0.7
            csnote.tied = False
            self.csnd.play(csnote, 0.3)
        del self.key_dict[key]

    def _updateInstrument(self, id, volume, pan=0, reverb=0):
        self.instrument = {"id": id,
                           "amplitude": volume,
                           "pan": pan,
                           "reverb": reverb}

    def pushInstrument(self, instrument):
        self.instrumentStack.append(self.instrument)
        self.instrument = instrument

    def popInstrument(self):
        self.instrument = self.instrumentStack.pop()

    def _playDrum(self, id, pageId, volume, reverb, beats, regularity,
                  loopId=None, sync=True):

        oldId = loopId
        loopId = self.csnd.loopCreate()

        noteOnsets = []
        notePitchs = []
        for n in self.noteDB.getNotesByTrack(pageId, 0):
            n.pushState()
            noteOnsets.append(n.cs.onset)
            notePitchs.append(n.cs.pitch)
            n.cs.instrumentId = id
            n.cs.amplitude = volume * n.cs.amplitude
            n.cs.reverbSend = reverb
            self.csnd.loopPlay(n, 1, loopId=loopId)  # add as active
            n.popState()

        ticks = self.noteDB.getPage(pageId).ticks

        self.csnd.loopSetNumTicks(ticks, loopId)

        self.drumFillin.setLoopId(loopId)
        self.drumFillin.setProperties(
            self.tempo, self.instrumentDB.instId[id].name, volume, beats,
            reverb)
        self.drumFillin.unavailable(noteOnsets, notePitchs)

        self.drumFillin.play()

        if oldId == None:
            if sync:
                startTick = self.csnd.loopGetTick(self.heartbeatLoop) \
                    % self.syncTicks
            else:
                startTick = 0
        else:
            # TODO is this really safe? could potentially add several
            # milliseconds of delay everytime a loop is updated
            if sync:
                startTick = self.csnd.loopGetTick(oldId)
            else:
                startTick = 0

        while startTick > ticks:
            startTick -= ticks

        self.csnd.loopSetTick(startTick, loopId)
        self.csnd.loopStart(loopId)

        if oldId != None:
            self.csnd.loopDestroy(oldId)

        return loopId

    def _stopDrum(self, loopId):
        self.drumFillin.stop()
        self.csnd.loopDestroy(loopId)

    def _playLoop(self, id, volume, reverb, tune, loopId=None, force=False,
                  sync=True):
        oldId = loopId
        loopId = self.csnd.loopCreate()

        inst = self.instrumentDB.instId[id]

        ticks = 0
        for page in tune:
            for n in self.noteDB.getNotesByTrack(page, 0):
                n.pushState()
                n.cs.instrumentId = id
                n.cs.amplitude = volume * n.cs.amplitude
                n.cs.reverbSend = reverb
                if inst.kit:  # drum kit
                    if n.cs.pitch in GenerationConstants.DRUMPITCH:
                        n.cs.pitch = GenerationConstants.DRUMPITCH[n.cs.pitch]
                n.cs.onset += ticks
                self.csnd.loopPlay(n, 1, loopId=loopId)
                n.popState()
            # metronome track
            for n in self.noteDB.getNotesByTrack(page, 1):
                self.csnd.loopPlay(n, 1, loopId=loopId)
            # record scratch track
            for n in self.noteDB.getNotesByTrack(page, 2):
                self.csnd.loopPlay(n, 1, loopId=loopId)
            ticks += self.noteDB.getPage(page).ticks

        self.csnd.loopSetNumTicks(ticks, loopId)

        if oldId == None:
            if sync:
                startTick = self.csnd.loopGetTick(self.heartbeatLoop) \
                    % self.syncTicks
            else:
                startTick = 0
        else:
            # TODO is this really safe? could potentially add several
            # milliseconds of delay everytime a loop is updated
            if sync:
                startTick = self.csnd.loopGetTick(oldId)
            else:
                startTick = 0

        while startTick > ticks:
            startTick -= ticks

        self.csnd.loopSetTick(startTick, loopId)
        self.csnd.loopStart(loopId)

        if oldId != None:
            self.csnd.loopDestroy(oldId)

        return loopId

    def _stopLoop(self, loopId):
        self.csnd.loopDestroy(loopId)

    def addMetronome(self, page, period):
        self.noteDB.deleteNotesByTrack([page], [1])

        baseCS = CSoundNote(
            0,  # onset
            36,  # pitch
            0.2,  # amplitude
            0.5,  # pan
            100,  # duration
            1,  # track
            self.instrumentDB.instNamed["drum1hatpedal"].instrumentId,
            reverbSend=0.5, tied=True, mode='mini')

        stream = []
        offset = 0

        for b in range(self.noteDB.getPage(page).beats):
            cs = baseCS.clone()
            cs.instrumentId = \
                self.instrumentDB.instNamed["drum1hatshoulder"].instrumentId
            cs.amplitude = 0.5
            cs.onset += offset

            stream.append(cs)

            onset = period
            while onset < Config.TICKS_PER_BEAT:
                cs = baseCS.clone()
                cs.onset = onset + offset
                stream.append(cs)
                onset += period

            offset += Config.TICKS_PER_BEAT

        self.noteDB.addNotes([page, 1, len(stream)] + stream + [-1])

    def removeMetronome(self, page):
        self.noteDB.deleteNotesByTrack([page], [1])

    def handleStopButton(self, widget):
        self.setStopped()

    def handleMuteButton(self, widget):
        if widget.get_active():
            self._setMuted(True)
        else:
            self._setMuted(False)

    def setMuted(self, muted):
        if Config.HAVE_TOOLBOX:
            toolbar = self.activity.toolbox.toolbar
        else:
            toolbar = self.playbackToolbar

        if toolbar.muteButton.get_active() == muted:
            return

        toolbar.muteButton.set_active(muted)
        toolbar.playbackToolbar.setMuted(muted)

    def _setMuted(self, muted):
        if self.muted == muted:
            return False

        if self.muted:  # unmute
            self.muted = False
            self.csnd.setTrackVolume(100, 0)
        else:  # mute
            self.muted = True
            self.csnd.setTrackVolume(0, 0)

        return True

    def setStopped(self):
        for drum in list(self.desktop.drums):
            self.desktop.deactivateDrum(drum)

        # we copy the list using the list() method
        for loop in list(self.desktop.loops):
            self.desktop.deactivateLoop(loop)

    #==========================================================
    # Generate

    def _generateDrumLoop(self, instrumentId, beats, regularity, reverb,
                          pageId=-1):
        def flatten(ll):
            rval = []
            for l in ll:
                rval += l
            return rval

        notes = flatten(generator(
                self.instrumentDB.instId[instrumentId].name, beats, 0.8,
                regularity, reverb))

        if pageId == -1:
            page = Page(beats)
            pageId = self.noteDB.addPage(-1, page)
        else:
            self.noteDB.deleteNotesByTrack([pageId], [0])

        if len(notes):
            self.noteDB.addNotes([pageId, 0, len(notes)] + notes + [-1])

        return pageId

    def _generateTrack(self, instrumentId, page, track, parameters, algorithm):
        dict = {track: {page: self.noteDB.getCSNotesByTrack(page, track)}}
        instruments = {page: [self.instrumentDB.instId[instrumentId].name \
                                  for i in range(Config.NUMBER_OF_TRACKS)]}
        beatsOfPages = {page: self.noteDB.getPage(page).beats}

        algorithm(parameters, [0.5 for i in range(Config.NUMBER_OF_TRACKS)],
                  instruments, self.tempo, beatsOfPages, [track], [page],
                  dict, 4)

        # filter & fix input ...WTF!?
        for track in dict:
            for page in dict[track]:
                for note in dict[track][page]:
                    intdur = int(note.duration)
                    note.duration = intdur
                    note.pageId = page
                    note.trackId = track

        # prepare the new notes
        newnotes = []
        for tid in dict:
            for pid in dict[tid]:
                newnotes += dict[tid][pid]

        # delete the notes and add the new
        self.noteDB.deleteNotesByTrack([page], [track])

        self.noteDB.addNotes([page, track, len(dict[track][page])] \
                                 + dict[track][page] + [-1])

    #==========================================================
    # Mic recording
    def micRec(self, widget, mic):
        self.csnd.inputMessage("i5600 0 4")
        OS.arecord(4, "crop.csd", mic)
        self.csnd.load_mic_instrument(mic)

    #==========================================================
    # Loop Settings
    def loopSettingsChannel(self, channel, value):
        self.csnd.setChannel(channel, value)

    def loopSettingsPlayStop(self, state, loop):
        if not state:
            if loop:
                self.loopSettingsPlaying = True
                self.csnd.inputMessage(Config.CSOUND_PLAY_LS_NOTE % 5022)
            else:
                self.csnd.inputMessage(Config.CSOUND_PLAY_LS_NOTE % 5023)
        else:
            if loop:
                self.loopSettingsPlaying = False
                self.csnd.inputMessage(Config.CSOUND_STOP_LS_NOTE)

    def load_ls_instrument(self, soundName):
        self.csnd.load_ls_instrument(soundName)

    #==========================================================
    # Get/Set

    def getVolume(self):
        return self.volume

    def setVolume(self, volume):
        self.jamToolbar.volumeSlider.set_value(volume)

    def _setVolume(self, volume):
        if self.muted:
            self.setMuted(False)
        self.volume = volume
        # csnd expects a range 0-100 for now
        self.csnd.setMasterVolume(self.volume * 100)

    def getTempo(self):
        return self.tempo

    def setTempo(self, tempo, quiet=False):
        self.jamToolbar.setTempo(tempo, quiet)

    def _setTempo(self, tempo, propagate=True):
        if self.network.isHost() or self.network.isOffline():
            t = time.time()
            elapsedTicks = (t - self.heartbeatStart) * self.ticksPerSecond

        self.tempo = tempo
        self.beatDuration = 60.0 / self.tempo
        self.ticksPerSecond = Config.TICKS_PER_BEAT * self.tempo / 60.0
        self.csnd.setTempo(self.tempo)

        if self.network.isHost() or self.network.isOffline():
            self.heatbeatStart = t - elapsedTicks * self.beatDuration
            self.updateSync()
            self.sendTempoUpdate()

    def getInstrument(self):
        return self.instrument

    def getDesktop(self):
        return self.desktop

    def _clearDesktop(self, save=True):
        if self.curDesktop == None:
            return

        if save:
            self._saveDesktop()

        self.desktop._clearDesktop()

        self.curDesktop = None

    def setDesktop(self, desktop, force=False):
        radiobtn = self.desktopToolbar.getDesktopButton(desktop)
        if force and radiobtn.get_active():
            self._setDesktop(desktop)
        else:
            radiobtn.set_active(True)

    def _setDesktop(self, desktop):
        self._clearDesktop()

        self.curDesktop = desktop

        TTTable = ControlStream.TamTamTable(self.noteDB, jam=self)

        filename = self.getDesktopScratchFile(self.curDesktop)
        try:
            stream = open(filename, "r")
            TTTable.parseFile(stream)
            stream.close()
        except IOError, (errno, strerror):
            if Config.DEBUG > 3:
                print "IOError:: _setDesktop:", errno, strerror

    def getInstrumentImage(self, id, active=False):
        if active:
            return self.instrumentImageActive[id]
        else:
            return self.instrumentImage[id]

    def getKeyImage(self, key, active=False):
        if active:
            return self.keyImageActive[key]
        else:
            return self.keyImage[key]

    def getLoopImage(self, id, active=False):
        if active:
            return self.loopImageActive[id]
        else:
            return self.loopImage[id]

    def setPicker(self, widget, pagePointer, page_num):
        page = self.GUI["notebook"].get_nth_page(page_num)
        if page == self.pickers[Picker.Drum]:
            pass
        elif page == self.pickers[Picker.Loop]:
            pass
        else:
            self.pickers[Picker.Instrument].setFilter((page.set))
            parent = self.pickers[Picker.Instrument].get_parent()
            if parent != page:
                if parent != None:
                    parent.remove(self.pickers[Picker.Instrument])
                page.add(self.pickers[Picker.Instrument])

    def setKeyboardListener(self, listener):
        self.keyboardListener = listener

    def mapKey(self, key, block, oldKey=None):
        if oldKey != None and block in self.keyMap[oldKey]:
            self.keyMap[oldKey].remove(block)

        if key == None:
            return

        if key not in self.keyMap.keys():
            self.keyMap[key] = []

        if block not in self.keyMap[key]:
            self.keyMap[key].append(block)

    #==========================================================
    # Pixmaps

    def prepareInstrumentImage(self, id, img_path):
        win = gtk.gdk.get_default_root_window()
        try:
            pix = gtk.gdk.pixbuf_new_from_file(img_path)
        except:
            if Config.DEBUG >= 5:
                print "JamMain:: file does not exist: " + img_path
            pix = gtk.gdk.pixbuf_new_from_file(imagefile('generic.png'))
        x = (Block.Block.WIDTH - pix.get_width()) // 2
        y = (Block.Block.HEIGHT - pix.get_height()) // 2
        img = gtk.gdk.Pixmap(win, Block.Block.WIDTH, Block.Block.HEIGHT)
        self.gc.foreground = self.colors["Bg_Inactive"]
        img.draw_rectangle(self.gc, True, 0, 0, Block.Block.WIDTH,
                           Block.Block.HEIGHT)
        img.draw_pixbuf(self.gc, pix, 0, 0, x, y, pix.get_width(),
                        pix.get_height(), gtk.gdk.RGB_DITHER_NONE)
        self.instrumentImage[id] = img
        img = gtk.gdk.Pixmap(win, Block.Block.WIDTH, Block.Block.HEIGHT)
        self.gc.foreground = self.colors["Bg_Active"]
        img.draw_rectangle(self.gc, True, 0, 0, Block.Block.WIDTH,
                           Block.Block.HEIGHT)
        img.draw_pixbuf(self.gc, pix, 0, 0, x, y, pix.get_width(),
                        pix.get_height(), gtk.gdk.RGB_DITHER_NONE)
        self.instrumentImageActive[id] = img

    def _drawNotes(self, pixmap, beats, notes, active):
        self.gc.set_clip_mask(self.sampleNoteMask)
        for note in notes:  # draw N notes
            x = self.ticksToPixels(note.cs.onset)
            # include end cap offset
            endX = self.ticksToPixels(note.cs.onset + note.cs.duration) - 3
            width = endX - x
            if width < 5:
                width = 5
                endX = x + width
            y = self.pitchToPixels(note.cs.pitch)
            # draw fill
            if active:
                self.gc.foreground = self.colors["Note_Fill_Active"]
            else:
                self.gc.foreground = self.colors["Note_Fill_Inactive"]
            self.gc.set_clip_origin(x, y - self.sampleNoteHeight)
            pixmap.draw_rectangle(self.gc, True, x + 1, y + 1, width + 1,
                                  self.sampleNoteHeight - 2)
            # draw border
            if active:
                self.gc.foreground = self.colors["Note_Border_Active"]
            else:
                self.gc.foreground = self.colors["Note_Border_Inactive"]
            self.gc.set_clip_origin(x, y)
            pixmap.draw_rectangle(self.gc, True, x, y, width,
                                  self.sampleNoteHeight)
            self.gc.set_clip_origin(endX - self.sampleNoteMask.endOffset, y)
            pixmap.draw_rectangle(self.gc, True, endX, y, 3,
                                  self.sampleNoteHeight)

    def prepareKeyImage(self, key):
        win = gtk.gdk.get_default_root_window()
        pangolayout = self.create_pango_layout(_(self.valid_shortcuts[key]))
        fontDesc = pango.FontDescription("bold")
        pangolayout.set_font_description(fontDesc)
        extents = pangolayout.get_pixel_extents()
        x = (Block.Block.KEYSIZE - extents[1][2]) // 2
        y = (Block.Block.KEYSIZE - extents[1][3]) // 2

        pixmap = gtk.gdk.Pixmap(win, Block.Block.KEYSIZE, Block.Block.KEYSIZE)
        self.gc.foreground = self.colors["Border_Inactive"]
        pixmap.draw_rectangle(self.gc, True, 0, 0, Block.Block.KEYSIZE,
                              Block.Block.KEYSIZE)
        self.gc.foreground = self.colors["Bg_Inactive"]
        pixmap.draw_layout(self.gc, x, y, pangolayout)
        self.keyImage[key] = pixmap

        pixmap = gtk.gdk.Pixmap(win, Block.Block.KEYSIZE, Block.Block.KEYSIZE)
        self.gc.foreground = self.colors["Border_Active"]
        pixmap.draw_rectangle(self.gc, True, 0, 0, Block.Block.KEYSIZE,
                              Block.Block.KEYSIZE)
        self.gc.foreground = self.colors["Bg_Active"]
        pixmap.draw_layout(self.gc, x, y, pangolayout)
        self.keyImageActive[key] = pixmap

    def updateLoopImage(self, id):
        page = self.noteDB.getPage(id)

        win = gtk.gdk.get_default_root_window()
        width = Block.Loop.WIDTH[page.beats]
        height = Block.Loop.HEIGHT

        self.gc.set_clip_rectangle(gtk.gdk.Rectangle(0, 0, width, height))

        pixmap = gtk.gdk.Pixmap(win, width, height)
        self.gc.foreground = self.colors["Bg_Inactive"]
        pixmap.draw_rectangle(self.gc, True, 0, 0, width, height)
        self._drawNotes(pixmap, page.beats, self.noteDB.getNotesByTrack(id, 0),
                        False)
        self.loopImage[id] = pixmap

        self.gc.set_clip_rectangle(gtk.gdk.Rectangle(0, 0, width, height))

        pixmap = gtk.gdk.Pixmap(win, width, height)
        self.gc.foreground = self.colors["Bg_Active"]
        pixmap.draw_rectangle(self.gc, True, 0, 0, width, height)
        self._drawNotes(pixmap, page.beats, self.noteDB.getNotesByTrack(id, 0),
                        True)
        self.loopImageActive[id] = pixmap

    def ticksToPixels(self, ticks):
        return self.loopTickOffset + int(round(ticks * self.pixelsPerTick))

    def pitchToPixels(self, pitch):
        return self.loopPitchOffset + \
            int(round((Config.MAXIMUM_PITCH - pitch) * self.pixelsPerPitch))

    #==========================================================
    # Load/Save

    def _saveDesktop(self):
        if self.curDesktop == None:
            return

        filename = self.getDesktopScratchFile(self.curDesktop)
        if os.path.isfile(filename):
            os.remove(filename)

        try:
            scratch = open(filename, "w")
            stream = ControlStream.TamTamOStream(scratch)

            self.noteDB.dumpToStream(stream, True)
            self.desktop.dumpToStream(stream)
            stream.sync_beats(self.syncBeats)

            scratch.close()
        except IOError, (errno, strerror):
            if Config.DEBUG > 3:
                print "IOError:: _saveDesktop:", errno, strerror

    def getDesktopScratchFile(self, i):
        return Config.TMP_DIR + "/desktop%d" % i

    def handleJournalLoad(self, filepath):

        self._clearDesktop(False)

        TTTable = ControlStream.TamTamTable(self.noteDB, jam=self)

        try:
            stream = open(filepath, "r")
            TTTable.parseFile(stream)
            stream.close()

            self.setVolume(TTTable.masterVolume)
            self.setTempo(TTTable.tempo)

        except IOError, (errno, strerror):
            if Config.DEBUG > 3:
                print "IOError:: handleJournalLoad:", errno, strerror

    def handleJournalSave(self, filepath):

        self._saveDesktop()

        try:
            streamF = open(filepath, "w")
            stream = ControlStream.TamTamOStream(streamF)

            for i in range(10):
                desktop_file = self.getDesktopScratchFile(i)
                stream.desktop_store(desktop_file, i)

            stream.desktop_set(self.curDesktop)

            stream.master_vol(self.volume)
            stream.tempo(self.tempo)

            streamF.close()

        except IOError, (errno, strerror):
            if Config.DEBUG > 3:
                print "IOError:: handleJournalSave:", errno, strerror

    #==========================================================
    # Network

    #-- Activity ----------------------------------------------

    def shared(self, activity):
        if Config.DEBUG:
            print "TamTamJam:: successfully shared, start host mode"
        self.activity._shared_activity.connect("buddy-joined",
                                               self.buddy_joined)
        self.activity._shared_activity.connect("buddy-left", self.buddy_left)
        self.network.setMode(Net.MD_HOST)
        self.updateSync()
        self.syncTimeout = gobject.timeout_add(1000, self.updateSync)

    def joined(self, activity):
        if Config.DEBUG:
            print "TamTamJam:: joined activity!!"
            for buddy in self.activity._shared_activity.get_joined_buddies():
                print buddy.props.ip4_address

    def buddy_joined(self, activity, buddy):
        if Config.DEBUG:
            print "buddy joined " + str(buddy)
            try:
                print buddy.props.ip4_address
            except:
                print "bad ip4_address"
        if self.network.isHost():
            if buddy == self.xoOwner:
                return
            if buddy.props.ip4_address:
                self.network.introducePeer(buddy.props.ip4_address)
            else:
                print "TamTamJam:: new buddy does not have an ip4_address!!"

    def buddy_left(self, activity, buddy):
        if Config.DEBUG:
            print "buddy left"

    #def joined(self, activity):
    #    if Config.DEBUG:
    #        print "miniTamTam:: successfully joined, wait for host"
    #    self.net.waitForHost()

    #-- Senders -----------------------------------------------

    def sendSyncQuery(self):
        self.packer.pack_float(random.random())
        hash = self.packer.get_buffer()
        self.packer.reset()
        self.syncQueryStart[hash] = time.time()
        self.network.send(Net.PR_SYNC_QUERY, hash)

    def sendTempoUpdate(self):
        self.packer.pack_int(self.tempo)
        self.network.sendAll(Net.HT_TEMPO_UPDATE, self.packer.get_buffer())
        self.packer.reset()

    def sendTempoQuery(self):
        self.network.send(Net.PR_TEMPO_QUERY)

    def requestTempoChange(self, val):
        self.packer.pack_int(val)
        self.network.send(Net.PR_REQUEST_TEMPO_CHANGE,
                          self.packer.get_buffer())
        self.packer.reset()

    #-- Handlers ----------------------------------------------

    def networkStatusWatcher(self, mode):
        if mode == Net.MD_OFFLINE:
            if self.syncTimeout:
                gobject.source_remove(self.syncTimeout)
                self.syncTimeout = None
        if mode == Net.MD_PEER:
            self.updateSync()
            if not self.syncTimeout:
                self.syncTimeout = gobject.timeout_add(1000, self.updateSync)
            self.sendTempoQuery()

    def processHT_SYNC_REPLY(self, sock, message, data):
        t = time.time()
        hash = data[0: 4]
        latency = t - self.syncQueryStart[hash]
        self.unpacker.reset(data[4: 8])
        elapsed = self.unpacker.unpack_float()
        #print "mini:: got sync: next beat in %f, latency %d" \
        #    % (nextBeat, latency*1000)
        self.heartbeatStart = t - elapsed - latency / 2
        self.correctSync()
        self.syncQueryStart.pop(hash)

    def processHT_TEMPO_UPDATE(self, sock, message, data):
        self.unpacker.reset(data)
        val = self.unpacker.unpack_int()
        self.setTempo(val, True)
        self.sendSyncQuery()

    def processPR_SYNC_QUERY(self, sock, message, data):
        self.packer.pack_float(time.time() - self.heartbeatStart)
        self.network.send(Net.HT_SYNC_REPLY, data + self.packer.get_buffer(),
                          sock)
        self.packer.reset()

    def processPR_TEMPO_QUERY(self, sock, message, data):
        self.packer.pack_int(self.tempo)
        self.network.send(Net.HT_TEMPO_UPDATE, self.packer.get_buffer(),
                          to=sock)
        self.packer.reset()

    def processPR_REQUEST_TEMPO_CHANGE(self, sock, message, data):
        if self.jamToolbar.tempoSliderActive:
            return
        self.unpacker.reset(data)
        val = self.unpacker.unpack_int()
        self.setTempo(val)

    #==========================================================
    # Sync

    def setSyncBeats(self, beats):
        self.beatToolbar.setSyncBeats(beats)

    def _setSyncBeats(self, beats):
        if beats == self.syncBeats:
            return

        elapsedTicks = (time.time() - self.heartbeatStart) \
            * self.ticksPerSecond + self.offsetTicks
        elapsedBeats = int(elapsedTicks) // Config.TICKS_PER_BEAT

        targBeat = (elapsedBeats % self.syncBeats) % beats
        curBeat = elapsedBeats % beats
        offset = (targBeat - curBeat) * Config.TICKS_PER_BEAT

        self.syncBeats = beats
        self.syncTicks = beats * Config.TICKS_PER_BEAT

        self.offsetTicks = (offset + self.offsetTicks) \
            % (self.syncTicks * HEARTBEAT_BUFFER)
        elapsedTicks += offset

        newTick = elapsedTicks % (self.syncTicks * HEARTBEAT_BUFFER)

        self.csnd.loopSetTick(newTick, self.heartbeatLoop)
        self.csnd.loopSetNumTicks(self.syncTicks * HEARTBEAT_BUFFER,
                                  self.heartbeatLoop)

        self.updateSync()

    def _setBeat(self, beat):
        curTick = self.csnd.loopGetTick(self.heartbeatLoop) % self.syncTicks
        curBeat = int(curTick) // Config.TICKS_PER_BEAT
        offset = (beat - curBeat) * Config.TICKS_PER_BEAT
        if offset > self.syncTicks // 2:
            offset -= self.syncTicks
        elif offset < -self.syncTicks // 2:
            offset += self.syncTicks

        self.offsetTicks = (offset + self.offsetTicks) \
            % (self.syncTicks * HEARTBEAT_BUFFER)

        for id in self.desktop.getLoopIds() + [self.heartbeatLoop]:
            tick = self.csnd.loopGetTick(id)
            maxTick = self.csnd.loopGetNumTicks(id)
            newTick = (tick + offset) % maxTick
            self.csnd.loopSetTick(newTick, id)

    def updateBeatWheel(self):
        curTick = self.csnd.loopGetTick(self.heartbeatLoop) % self.syncTicks
        self.curBeat = int(curTick) // Config.TICKS_PER_BEAT
        self.beatToolbar.updateBeatWheel(self.curBeat)
        return True

    def correctedHeartbeat(self):
        elapsedTicks = (time.time() - self.heartbeatStart) \
            * self.ticksPerSecond
        return (elapsedTicks + self.offsetTicks) \
            % (self.syncTicks * HEARTBEAT_BUFFER)

    def updateSync(self):
        if Config.DEBUG:
            # help the log print out on time
            sys.stdout.flush()

        if self.network.isOffline():
            return False
        elif self.network.isWaiting():
            return True
        elif self.network.isHost():
            self.correctSync()
        else:
            self.sendSyncQuery()
        return True

    def correctSync(self):
        curTick = self.csnd.loopGetTick(self.heartbeatLoop)
        corTick = self.correctedHeartbeat()
        err = corTick - curTick
        maxTick = self.syncTicks * HEARTBEAT_BUFFER
        # these should never happen becasue of HEARTBEAT_BUFFER, but hey
        if err < -maxTick // 2:
            err += maxTick
        elif err > maxTick // 2:
            err -= maxTick

        #print "correctSync", curTick, corTick, err, maxTick, self.offsetTicks

        if abs(err) > 4 * Config.TICKS_PER_BEAT:  # we're way off
            for id in self.desktop.getLoopIds() + [self.heartbeatLoop]:
                tick = self.csnd.loopGetTick(id)
                maxTick = self.csnd.loopGetNumTicks(id)
                newTick = (tick + err) % maxTick
                self.csnd.loopSetTick(newTick, id)
        elif abs(err) > 0.25:  # soft correction
            self.csnd.adjustTick(err / 3)
