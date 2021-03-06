
import pygtk
pygtk.require( '2.0' )
import gtk

import random

import common.Util.InstrumentDB as InstrumentDB
import common.Config as Config
from common.Config import scale

from common.Util.NoteDB import PARAMETER

#::: NOTE:
# All the graphics resources are loaded in Desktop and referenced here as necessary
#:::

class Block:

    WIDTH = scale(100)
    HEIGHT = scale(100)

    SNAP = scale(15)

    PAD = scale(4)

    KEYSIZE = scale(26)
    KEYMASK_START = scale(309)

    def __init__( self, owner, data ):
        self.owner = owner
        self.gc = owner.gc

        self.data = {}
        for key in data.keys():
            self.data[key] = data[key]

        self.type = Block

        self.width = Block.WIDTH
        self.height = Block.HEIGHT

        self.parent = None
        self.canChild = False
        self.child = None
        self.canParent = False

        self.canSubstitute = False

        self.parentOffest = 0

        self.dragging = False # is currently dragging
        self.placed = False   # has been placed on the desktop at least once

        self.firstLoc = True
        self.x = -1
        self.y = -1

        self.active = False

    def dumpToStream( self, ostream, child = False ):
        ostream.block_add( ClassToStr[ self.type ], self.active, self.x + self.width//2, self.y + self.height//2, child, self.data )
        if self.child:
            self.child.dumpToStream( ostream, True )

    def destroy( self ):
        if self.child:
            self.child.destroy()
            self.child = None
        self.invalidate_rect( not self.dragging )

    def isPlaced( self ):
        return self.placed

    def setPlaced( self, placed ):
        self.placed = placed

    def getLoc( self ):
        return ( self.x, self.y )

    def setLoc( self, x, y ):
        if x == self.x and y == self.y: return

        if self.firstLoc:
            self.firstLoc = False
        else:
            self.invalidate_rect( not self.dragging )

        self.x = int(x)
        self.y = int(y)
        self.endX = self.x + self.width
        self.endY = self.y + self.height

        self.invalidate_rect( not self.dragging )

        if self.child:
            self.child.snapToParentLoc( self.getChildAnchor() )

    def resetLoc( self ):
        if self.oldParent != None:
            self.oldParent.addChild( self )
            return False
        else:
            self.setLoc( self.oldLoc[0], self.oldLoc[1] )
            return True

    def getParentAnchor( self ):
        return ( self.x + self.parentOffset, self.y )

    def getChildAnchor( self ):
        return ( self.endX, self.y )

    def snapToParentLoc( self, loc ):
        self.setLoc( loc[0] - self.parentOffset, loc[1] )

    def substitute( self, block ):
        pass # override in subclasses

    def testSubstitute( self, block ):
        if self.child:
            return self.child.testSubstitute( block )

    def testChild( self, loc ):

        if not self.canParent:
            return False

        if self.child:
            return self.child.testChild( loc )
        elif abs( self.endX - loc[0] ) < Block.SNAP and abs( self.y - loc[1] ) < Block.SNAP:
            return self

        return False

    def addChild( self, child ):
        c = self.child
        if self.child:
            self.removeChild()

        self.child = child
        child._addParent( self )
        child.snapToParentLoc( self.getChildAnchor() )

        if c:
            child.addChild( c )

    def removeChild( self ):
        self.child._removeParent()
        self.child = None

    def _addParent( self, parent ):
        self.parent = parent

    def _removeParent( self ):
        self.parent = None

    def getRoot( self ):
        if self.parent: return self.parent.getRoot()
        return self

    def isActive( self ):
        return self.active

    def setActive( self, state ):
        self.active = state
        self.invalidate_rect( not self.dragging )

    def getData( self, key ):
        return self.data[ key ]

    def setData( self, key, value ):
        self.data[ key ] = value

    def testMouseOver( self, event ):
        if self.child:
            ret = self.child.testMouseOver( event )
            if ret: return ret

        x = event.x - self.x
        y = event.y - self.y

        if 0 <= x <= self.width and 0 <= y <= self.height:
            return -1

        return False

    def button_press( self, event ):

        if event.y < self.y or event.y > self.endY:
            return False

        return self._button_pressB( event )

    def _button_pressB( self, event ):

        if event.x < self.x:
            return False

        if event.x > self.endX:
            if self.child:
                return self.child._button_pressB( event )
            else:
                return False

        self.oldParent = self.parent
        self.oldLoc = ( self.x, self.y )
        self.dragOffset = ( event.x - self.x, event.y - self.y )

        self._doButtonPress( event )

        return self

    def _doButtonPress( self, event ):
        pass # override in subclasses

    def button_release( self, event ):
        if self.dragging:
            self.dragging = False
            self.placed = True
            self.invalidateBranch()

    def motion_notify( self, event ):

        removeFromBlocks = not self.dragging and not self.parent

        if not self.dragging:
            self.dragging = True
            self.invalidate_rect()

        if self.parent:
            self.parent.removeChild()

        self.setLoc( event.x - self.dragOffset[0], event.y - self.dragOffset[1] )

        return removeFromBlocks

    def _beginDrag( self ):
        self.dragging = True
        self.dragOffset = ( self.width//2, self.height//2 )

    def invalidateBranch( self, base = True ):
        self.invalidate_rect( base )
        if self.child:
            self.child.invalidateBranch( base )

    def invalidate_rect( self, base = True ):
        self.owner.invalidate_rect( self.x, self.y, self.width, self.height, base )

    def draw( self, startX, startY, stopX, stopY, pixmap ):
        if stopY <= self.y or startY >= self.endY:
            return False

        self._drawB( startX, startY, stopX, stopY, pixmap )

    def _drawB( self, startX, startY, stopX, stopY, pixmap ):

        if stopX <= self.x:
            return False

        if self.child:
            self.child._drawB( startX, startY, stopX, stopY, pixmap )

        if startX >= self.endX:
            return False

        self._doDraw( startX, startY, stopX, stopY, pixmap )

        return True

    def _doDraw( self, startX, startY, stopX, stopY, pixmap ):
        pass # override in subclasses

    def drawHighlight( self, startX, startY, stopX, stopY, pixmap ):
        pass # override in subclasses

class Instrument(Block):

    MASK_START = 0

    #::: data format:
    # { "name": name, "id": instrumentId [, "volume": 0-1, "pan": 0-1, "reverb": 0-1 ] }
    #:::
    def __init__( self, owner, data ):
        Block.__init__( self, owner, data )

        self.type = Instrument

        self.canParent = True
        self.canSubstitute = True

        if not "volume" in self.data.keys():
            self.data["volume"] = 0.5
        if not "pan" in self.data.keys():
            self.data["pan"] = 0.5
        if not "reverb" in self.data.keys():
            self.data["reverb"] = 0

        self.img = [ self.owner.getInstrumentImage( self.data["id"], False ),
                     self.owner.getInstrumentImage( self.data["id"], True ) ]

    def setData( self, key, value ):
        self.data[ key ] = value
        if self.active:
            self.owner.updateInstrument( self )
        if self.child and self.child.active:
            self.owner.updateLoop( self.child )

    def substitute( self, block ):
        self.data["id"] = block.data["id"]
        self.img = [ self.owner.getInstrumentImage( self.data["id"], False ),
                     self.owner.getInstrumentImage( self.data["id"], True ) ]
        self.invalidate_rect( True )

        if self.child and self.child.active:
            self.owner.updateLoop( self.child )

    def testSubstitute( self, block ):
        ret = Block.testSubstitute( self, block )
        if ret:
            return ret

        if block.type == Loop:
            return False

        if abs( self.x - block.x ) < Block.SNAP and abs( self.y - block.y ) < Block.SNAP:
            return self

        return False

    def _doButtonPress( self, event ): # we were hit with a button press
        pass

    def button_release( self, event ):
        if not self.dragging:
            self.owner.activateInstrument( self )
        Block.button_release( self, event )

    def _doDraw( self, startX, startY, stopX, stopY, pixmap ):
        x = max( startX, self.x )
        y = max( startY, self.y )
        endX = min( stopX, self.endX )
        endY = min( stopY, self.endY )
        width = endX - x
        height = endY - y

        # draw border
        if self.active: self.gc.foreground = self.owner.colors["Border_Active"]
        else:           self.gc.foreground = self.owner.colors["Border_Inactive"]
        self.gc.set_clip_origin( self.x-Instrument.MASK_START, self.y )
        pixmap.draw_rectangle( self.gc, True, x, y, width, height )

        # draw block
        self.gc.set_clip_origin( self.x-Instrument.MASK_START, self.y-self.height )
        pixmap.draw_drawable( self.gc, self.img[self.active], x-self.x, y-self.y, x, y, width, height )

    def drawHighlight( self, startX, startY, stopX, stopY, pixmap ):
        self.gc.foreground = self.owner.colors["Border_Highlight"]
        self.gc.set_clip_origin( self.x-Instrument.MASK_START, self.y )
        pixmap.draw_rectangle( self.gc, True, self.x, self.y, self.width, self.height )

class Drum(Block):

    MASK_START = scale(100)

    KEYRECT = [ Block.PAD - 1, Block.HEIGHT + 1 - Block.PAD - Block.KEYSIZE, Block.KEYSIZE, Block.KEYSIZE ]
    KEYRECT += [ KEYRECT[0]+KEYRECT[2], KEYRECT[1]+KEYRECT[3] ]

    #::: data format:
    # { "name": name, "id": instrumentId [ , "page": pageId, "volume": 0-1, "reverb": 0-1, "beats": 2-12, "regularity": 0-1, "key": shortcut ] }
    #:::
    def __init__( self, owner, data ):
        Block.__init__( self, owner, data )
        self.instrumentDB = InstrumentDB.getRef()
        self.type = Drum

        self.canSubstitute = True

        if not "page" in self.data.keys():
            self.data["page"] = -1
        if not "volume" in self.data.keys():
            self.data["volume"] = 0.5
        if not "reverb" in self.data.keys():
            self.data["reverb"] = 0.0
        if not "beats" in self.data.keys():
            self.data["beats"] = 4 #random.randint(2, 12)
        if not "regularity" in self.data.keys():
            self.data["regularity"] = 0.8 #random.random()
        if "key" not in self.data.keys():
            self.data["key"] = None

        self.owner.mapKey( self.data["key"], self )
        self.keyImage = [ self.owner.getKeyImage( self.data["key"], False ),
                          self.owner.getKeyImage( self.data["key"], True ) ]


        self.img = [ self.owner.getInstrumentImage( self.data["id"], False ),
                     self.owner.getInstrumentImage( self.data["id"], True ) ]

        if self.data["page"] == -1:
            self.regenerate()

    def destroy( self ):
        self.owner.mapKey( None, self, self.data["key"] )
        self.owner.noteDB.deletePages( [ self.data["page"] ] )
        Block.destroy( self )

    def setData( self, key, value ):
        if key == "beats":
            self.data["beats"] = value
            self.owner.noteDB.updatePage( self.data["page"], PARAMETER.PAGE_BEATS, value )

        elif key == "key":
            oldKey = self.data["key"]
            self.data["key"] = value
            self.keyImage = [ self.owner.getKeyImage( value, False ),
                              self.owner.getKeyImage( value, True ) ]
            self.invalidate_rect()
            self.owner.mapKey( value, self, oldKey )

        else:
            self.data[key] = value

        if self.active:
            self.owner.updateDrum( self )

    def substitute( self, block ):
        self.setData( "name", block.data["name"] )
        self.setData( "id", block.data["id"] )

        self.img = [ self.owner.getInstrumentImage( self.data["id"], False ),
                     self.owner.getInstrumentImage( self.data["id"], True ) ]

        self.invalidate_rect( True )

        if self.active:
            self.owner.updateDrum( self )

    def testSubstitute( self, block ):
        ret = Block.testSubstitute( self, block )
        if ret:
            return ret

        if block.type == Loop:
            return False

        if self.instrumentDB.instId[block.data["id"]].kit == None:
            return False

        if abs( self.x - block.x ) < Block.SNAP and abs( self.y - block.y ) < Block.SNAP:
            return self

        return False

    def testMouseOver( self, event ):
        ret = self.testWithinKey( event )
        if ret: return ret

        x = event.x - self.x
        y = event.y - self.y

        if 0 <= x <= self.width and 0 <= y <= self.height:
            return -1

        return False

    def testWithinKey( self, event ):
        x = event.x - self.x
        y = event.y - self.y

        if Drum.KEYRECT[0] <= x <= Drum.KEYRECT[4] and Drum.KEYRECT[1] <= y <= Drum.KEYRECT[5]:
            return self

        return False

    def _doButtonPress( self, event ): # we were hit with a button press
        pass

    def button_release( self, event ):
        if not self.dragging:
            if self.active:
                self.owner.deactivateDrum( self )
            else:
                self.owner.activateDrum( self )
        Block.button_release( self, event )

    def _doDraw( self, startX, startY, stopX, stopY, pixmap ):
        x = max( startX, self.x )
        y = max( startY, self.y )
        endX = min( stopX, self.endX )
        endY = min( stopY, self.endY )
        width = endX - x
        height = endY - y

        # draw border
        if self.active: self.gc.foreground = self.owner.colors["Border_Active"]
        else:           self.gc.foreground = self.owner.colors["Border_Inactive"]
        self.gc.set_clip_origin( self.x-Drum.MASK_START, self.y )
        pixmap.draw_rectangle( self.gc, True, x, y, width, height )

        # draw block
        self.gc.set_clip_origin( self.x-Drum.MASK_START, self.y-self.height )
        pixmap.draw_drawable( self.gc, self.img[self.active], x-self.x, y-self.y, x, y, width, height )

        # draw key
        self.gc.set_clip_origin( self.x+Drum.KEYRECT[0]-Block.KEYMASK_START, self.y+Drum.KEYRECT[1] )
        pixmap.draw_drawable( self.gc, self.keyImage[ self.active ], 0, 0, self.x+Drum.KEYRECT[0], self.y+Drum.KEYRECT[1], Block.KEYSIZE, Block.KEYSIZE )


    def drawHighlight( self, startX, startY, stopX, stopY, pixmap ):
        self.gc.foreground = self.owner.colors["Border_Highlight"]
        self.gc.set_clip_origin( self.x-Drum.MASK_START, self.y )
        pixmap.draw_rectangle( self.gc, True, self.x, self.y, self.width, self.height )

    def drawKeyHighlight( self, pixmap ):
        self.gc.foreground = self.owner.colors["Border_Highlight"]
        self.gc.set_clip_origin( self.x+Drum.KEYRECT[0]-Block.KEYMASK_START, self.y+Drum.KEYRECT[1]-Block.KEYSIZE )
        pixmap.draw_rectangle( self.gc, True, self.x+Drum.KEYRECT[0], self.y+Drum.KEYRECT[1], Block.KEYSIZE, Block.KEYSIZE )

    def regenerate( self ):
        self.data["page"] = self.owner.owner._generateDrumLoop( self.data["id"], self.data["beats"], self.data["regularity"], self.data["reverb"], self.data["page"] )
        if self.active:
            self.owner.updateDrum( self )

    def clear( self ):
        self.owner.noteDB.deleteNotesByTrack( [ self.data["page"] ], [ 0 ] )

class Loop(Block):

    HEAD = scale(13)
    BEAT = scale(23)
    TAIL = BEAT + Block.PAD

    WIDTH = [ HEAD + BEAT*(n-1) + TAIL for n in range(Config.MAXIMUM_BEATS+1) ]

    BEAT_MUL3 = BEAT*3

    MASK_START = scale(200)
    MASK_BEAT  = MASK_START + HEAD
    MASK_TAIL  = MASK_START + HEAD + BEAT*3

    KEYRECT = [ HEAD + Block.PAD, Block.HEIGHT - 2*Block.PAD - Block.KEYSIZE, Block.KEYSIZE, Block.KEYSIZE ]
    KEYRECT += [ KEYRECT[0]+KEYRECT[2], KEYRECT[1]+KEYRECT[3] ]

    #::: data format:
    # { "name": name, "id": pageId [, "beats": 2-12, "regularity": 0-1, "key": shortcut ] }
    #:::
    def __init__( self, owner, data ):
        Block.__init__( self, owner, data )

        self.type = Loop

        self.canParent = True
        self.canChild = True
        self.canSubstitute = True

        self.parentOffset = Loop.HEAD - 4

        self.data["beats"] = self.owner.noteDB.getPage(self.data["id"]).beats
        self.width = Loop.WIDTH[ self.data["beats"] ]

        if "regularity" not in self.data.keys():
            self.data["regularity"] = 0.8 #random.random()
        if "key" not in self.data.keys():
            self.data["key"] = None

        self.keyActive = False
        self.keyImage = [ self.owner.getKeyImage( self.data["key"], False ),
                          self.owner.getKeyImage( self.data["key"], True ) ]

        self.img = [ self.owner.getLoopImage( self.data["id"], False ),
                     self.owner.getLoopImage( self.data["id"], True ) ]

    def destroy( self ):
        if self.active:
            self.owner.deactivateLoop( self )
        if self.keyActive:
            self.owner.mapKey( None, self, self.data["key"] )
        self.owner.noteDB.deletePages( [ self.data["id"] ] )
        Block.destroy( self )

    def _updateWidth( self ):
        self.invalidateBranch( True )

        oldWidth = self.width

        self.width = Loop.WIDTH[self.data["beats"]]
        self.endX = self.x + self.width

        if self.child:
            self.child.snapToParentLoc( self.getChildAnchor() )

        if oldWidth < self.width: # or block.child:
            self.invalidateBranch( True )

    def updateLoop( self ):
        self.updateImage()
        self.invalidate_rect()

        if self.active:
            self.owner.updateLoop( self.getRoot().child )

    def updateImage( self ):
        self.owner.updateLoopImage( self.data["id"] )
        self.img = [ self.owner.getLoopImage( self.data["id"], False ),
                     self.owner.getLoopImage( self.data["id"], True ) ]

    def setData( self, key, value ):

        if key == "beats":
            self.data["beats"] = value
            self.owner.noteDB.updatePage( self.data["id"], PARAMETER.PAGE_BEATS, value )
            self._updateWidth()
            self.updateLoop()

        elif key == "key":
            oldKey = self.data["key"]
            self.data["key"] = value
            self.keyImage = [ self.owner.getKeyImage( value, False ),
                              self.owner.getKeyImage( value, True ) ]
            self.invalidate_rect()
            if self.keyActive:
                self.owner.mapKey( value, self, oldKey )

        else:
            self.data[key] = value

    def substitute( self, block ):
        self.invalidateBranch( True )

        oldWidth = self.width

        newid = self.owner.noteDB.duplicatePages( [ block.data["id"] ] )[block.data["id"]]
        self.data["id"] = newid
        self.data["beats"] = self.owner.noteDB.getPage(self.data["id"]).beats

        self.updateImage()
        self._updateWidth()

        if False: # don't substitute children
            if block.child:
                c = block.child
                after = self
                while c:
                    data = {}
                    for key in c.data.keys():
                        data[key] = c.data[key]

                    newid = self.owner.noteDB.duplicatePages( [ data["id"] ] )[data["id"]]
                    self.owner.updateLoopImage( newid )
                    data["id"] = newid

                    copy = Loop( self.owner, self.gc, data )
                    after.addChild( copy )
                    after = copy
                    c = c.child
            elif self.child:
                self.child.snapToParentLoc( self.getChildAnchor() )

        if self.active:
            self.owner.updateLoop( self.getRoot().child )

    def testSubstitute( self, block ):
        ret = Block.testSubstitute( self, block )
        if ret:
            return ret

        if block.type != Loop:
            return False

        if abs( self.x - block.x ) < Block.SNAP and abs( self.y - block.y ) < Block.SNAP:
            return self

        return False

    def setActive( self, state ):
        Block.setActive( self, state )

        if self.child:
            self.child.setActive( state )

    def addChild( self, child ):
        Block.addChild( self, child )
        if self.active:
            child.setActive( True )
            self.owner.updateLoop( self.getRoot().child )

    def _addParent( self, parent ):
        Block._addParent( self, parent )

        if self.parent.type == Instrument:
            self.keyActive = True
            self.owner.mapKey( self.data["key"], self )
        else:
            root = self.getRoot()
            if root.type == Instrument:
                root = root.child
            if root.getData("key") == None:
                root.setData( "key", self.data["key"] )
            self.setData( "key", None )

    def _removeParent( self ):
        if self.active:
            loopRoot = self.getRoot().child
            parent = self.parent
        else:
            loopRoot = None

        self.keyActive = False
        self.owner.mapKey( None, self, self.data["key"] )

        Block._removeParent( self )

        if loopRoot == self:
            self.owner.deactivateLoop( loopRoot )
        elif loopRoot != None:
            self.setActive( False )
            parent.child = None # disconnect us before updating
            self.owner.updateLoop( loopRoot )

    def testMouseOver( self, event ):
        ret = self.testWithinKey( event )
        if ret: return ret

        x = event.x - self.x
        y = event.y - self.y

        if 0 <= x <= self.width and 0 <= y <= self.height:
            return -1

        return False

    def testWithinKey( self, event ):
        if not self.keyActive:
            return False

        x = event.x - self.x
        y = event.y - self.y

        if Loop.KEYRECT[0] <= x <= Loop.KEYRECT[4] and Loop.KEYRECT[1] <= y <= Loop.KEYRECT[5]:
            return self

        return False

    def _doButtonPress( self, event ): # we were hit with a button press
        pass

    def button_release( self, event ):
        if not self.dragging:
            if self.active:
                root = self.getRoot()
                self.owner.deactivateLoop( root.child )
            else:
                root = self.getRoot()
                if root.type == Instrument: # must be attached to an instrument
                    self.owner.activateLoop( root.child )
        Block.button_release( self, event )

    def _doDraw( self, startX, startY, stopX, stopY, pixmap ):
        y = max( startY, self.y )
        endY = min( stopY, self.endY )
        height = endY - y

        loop = self.img[ self.active ]
        if self.active: self.gc.foreground = self.owner.colors["Border_Active"]
        else:           self.gc.foreground = self.owner.colors["Border_Inactive"]

        #-- draw head -----------------------------------------

        if self.x + Loop.HEAD > startX:
            x = max( startX, self.x )
            endX = min( stopX, self.x + Loop.HEAD )
            width = endX - x

            # draw border
            self.gc.set_clip_origin( self.x-Loop.MASK_START, self.y )
            pixmap.draw_rectangle( self.gc, True, x, y, width, height )

            # draw block
            self.gc.set_clip_origin( self.x-Loop.MASK_START, self.y-self.height )
            pixmap.draw_drawable( self.gc, loop, x-self.x, y-self.y, x, y, width, height )

        #-- draw beats ----------------------------------------

        beats = self.owner.noteDB.getPage(self.data["id"]).beats - 1 # last beat is drawn with the tail
        curx = self.x + Loop.HEAD
        while beats > 3:
            if curx >= stopX:
                break
            elif curx + Loop.BEAT_MUL3 > startX:
                x = max( startX, curx )
                endX = min( stopX, curx + Loop.BEAT_MUL3 )
                width = endX - x

                # draw border
                self.gc.set_clip_origin( curx-Loop.MASK_BEAT, self.y )
                pixmap.draw_rectangle( self.gc, True, x, y, width, height )

                # draw block
                self.gc.set_clip_origin( curx-Loop.MASK_BEAT, self.y-self.height )
                pixmap.draw_drawable( self.gc, loop, x-self.x, y-self.y, x, y, width, height )

            curx += Loop.BEAT_MUL3
            beats -= 3
        if beats and curx < stopX:
            endX = curx + Loop.BEAT*beats
            if endX > startX:
                x = max( startX, curx )
                endX = min( stopX, endX )
                width = endX - x

                # draw border
                self.gc.set_clip_origin( curx-Loop.MASK_BEAT, self.y )
                pixmap.draw_rectangle( self.gc, True, x, y, width, height )

                # draw block
                self.gc.set_clip_origin( curx-Loop.MASK_BEAT, self.y-self.height )
                pixmap.draw_drawable( self.gc, loop, x-self.x, y-self.y, x, y, width, height )

            curx += Loop.BEAT*beats


        #-- draw tail -----------------------------------------

        if curx < stopX:
            x = max( startX, curx )
            endX = min( stopX, self.endX )
            width = endX - x

            # draw border
            self.gc.set_clip_origin( curx-Loop.MASK_TAIL, self.y )
            pixmap.draw_rectangle( self.gc, True, x, y, width, height )

            # draw block
            self.gc.set_clip_origin( curx-Loop.MASK_TAIL, self.y-self.height )
            pixmap.draw_drawable( self.gc, loop, x-self.x, y-self.y, x, y, width, height )

        #-- draw key ------------------------------------------
        if self.keyActive:
            self.gc.set_clip_origin( self.x+Loop.KEYRECT[0]-Block.KEYMASK_START, self.y+Loop.KEYRECT[1] )
            pixmap.draw_drawable( self.gc, self.keyImage[ self.active ], 0, 0, self.x+Loop.KEYRECT[0], self.y+Loop.KEYRECT[1], Block.KEYSIZE, Block.KEYSIZE )

    def drawHighlight( self, startX, startY, stopX, stopY, pixmap ):
        self.gc.foreground = self.owner.colors["Border_Highlight"]

        #-- draw head -----------------------------------------

        self.gc.set_clip_origin( self.x-Loop.MASK_START, self.y )
        pixmap.draw_rectangle( self.gc, True, self.x, self.y, Loop.HEAD, self.height )

        #-- draw beats ----------------------------------------

        beats = self.owner.noteDB.getPage(self.data["id"]).beats - 1 # last beat is drawn with the tail
        x = self.x + Loop.HEAD
        while beats > 3:
            self.gc.set_clip_origin( x-Loop.MASK_BEAT, self.y )
            pixmap.draw_rectangle( self.gc, True, x, self.y, Loop.BEAT_MUL3, self.height )

            x += Loop.BEAT_MUL3
            beats -= 3
        if beats:
            width = Loop.BEAT*beats

            self.gc.set_clip_origin( x-Loop.MASK_BEAT, self.y )
            pixmap.draw_rectangle( self.gc, True, x, self.y, width, self.height )

            x += width

        #-- draw tail -----------------------------------------

        self.gc.set_clip_origin( x-Loop.MASK_TAIL, self.y )
        pixmap.draw_rectangle( self.gc, True, x, self.y, Loop.TAIL, self.height )

    def drawKeyHighlight( self, pixmap ):
        self.gc.foreground = self.owner.colors["Border_Highlight"]
        self.gc.set_clip_origin( self.x+Loop.KEYRECT[0]-Block.KEYMASK_START, self.y+Loop.KEYRECT[1]-Block.KEYSIZE )
        pixmap.draw_rectangle( self.gc, True, self.x+Loop.KEYRECT[0], self.y+Loop.KEYRECT[1], Block.KEYSIZE, Block.KEYSIZE )

    def clear( self ):
        self.owner.noteDB.deleteNotesByTrack( [ self.data["id"] ], [ 0 ] )

        self.updateImage()

        self.invalidate_rect()

        if self.active:
            self.owner.updateLoop( self.getRoot().child )


StrToClass = {
    "Instrument": Instrument,
    "Drum":       Drum,
    "Loop":       Loop
    }

ClassToStr = {
    Instrument: "Instrument",
    Drum:       "Drum",
    Loop:       "Loop"
    }
