# -*- coding: utf-8 -*-
'''
Created on Mar 14, 2012

@author: Zephyre
'''

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
import E7XX as es
import AVTCamera as avt
import BioscopeRc
import Queue
import cProfile
import collections
import colorsys
import copy
import json
import logging
import numpy
import numpy as np
import pstats
import sys
import time
import os
import calendar
import math

FORMAT = '%(asctime)s, %(name)s, %(levelname)s, Pid: %(process)d, Tid: %(thread)d/%(threadName)s, %(filename)s/%(funcName)s/%(lineno)d, %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)

__version__ = '1.0.0'
gSim = False

class BioScopeRoiItem(QGraphicsRectItem):
    '''
    This class has context menu support
    
    Signals: sigSetRoi, fullRoi
    '''
    
    sigSetRoi = pyqtSignal()
    fullRoi = pyqtSignal()
    
    def __init__(self, rect, roiType, parent=None):
        '''
        Type: there are two types of ROIs: 'Temp', which is the temporary
        Roi drawn by mouse-drags, and 'Analysis', which is the Roi for analysis.
        '''
        super(BioScopeRoiItem, self).__init__(rect, parent)
        self.roiType = roiType
        self.__createActions()
        # Red for 'Temp', green for 'Analysis' 
        self.setPen(QPen(Qt.green if roiType == 'Analysis' else Qt.red))
        self.roiId = None
        
    def __createActions(self):
        '''
        Available actions: SetRoi, FullRoi, Remove, AddToAnalysis
        '''
        if self.roiType == 'Temp':
            self.actions = dict((('SetRoi', QAction('Set ROI', None)),
                                 ('Remove', QAction('Remove', None)),
                                 ('AddToAnalysis', QAction('Add to Analysis', None))))
        elif self.roiType == 'Analysis':
            self.actions = {'Remove':QAction('Remove', None)}

    def contextMenuEvent(self, event):
        menu = QMenu()
        if self.roiType == 'Temp':
            menu.addActions(list(self.actions[key] for key in ('SetRoi', 'AddToAnalysis', 'Remove')))
        elif self.roiType == 'Analysis':            
            menu.addAction(self.actions['Remove'])
        menu.exec_(event.screenPos())
        
#    def itemChange(self, change, value):
#        if change == QGraphicsItem.ItemSelectedChange and self.roiId is not None \
#            and self.isSelected() != value.toBool():
#            self.scene().views()[0].sig_BioScopeView_RoiSelectionChanged.emit((self.roiId, value.toBool()))
#        return super(BioScopeRoiItem, self).itemChange(change, value)
            
class BioScopePixmapItem(QGraphicsPixmapItem):
    '''
    Support mouse events
    '''
    
    def __init__(self, pixmap=None, parent=None, scene=None):
        if pixmap is None:
            super(BioScopePixmapItem, self).__init__(parent, scene)
        else:
            super(BioScopePixmapItem, self).__init__(pixmap, parent, scene)
        self.__roiItem = None
        
        self.__tmpRoi = None
        self.__roiItemList = []
        self.setAcceptHoverEvents(True)
        self.lastHoverMoveEvent = time.clock()
        
    @property
    def roi(self):
        return self.__roiItem.boundingRect() \
            if self.__roiItem is not None else None
            
    def getRoi(self):
        return self.__tmpRoi
    
    def clearRoi(self):
        if self.__tmpRoi is not None:
            self.scene().removeItem(self.__tmpRoi)
            self.__tmpRoi = None
        
    def hoverMoveEvent(self, event):
        t = time.clock()
        if t - self.lastHoverMoveEvent < 0.1:
            return
        self.lastHoverMoveEvent = t
        pos = list(map(lambda v:int(v), (event.pos().x(), event.pos().y())))
        value = self.qimage.pixelIndex(pos[0], pos[1])
        roi = self.scene().camRoi
        pos[0] += roi[0]
        pos[1] += roi[1]
        self.scene().views()[0].broadcastInfo(pos, value)
        
    def hoverLeaveEvent(self, event):
        self.scene().views()[0].broadcastInfo(None, None)
        
    def mousePressEvent(self, event):
        if self.__tmpRoi is not None:
            self.scene().removeItem(self.__tmpRoi)
            self.__tmpRoi = None
        pos = event.pos()
        pos.setX(int(pos.x()))
        pos.setY(int(pos.y()))
        self.__startPoint = pos
        
    def mouseMoveEvent(self, event):        
        pos = event.pos()
        width, height = self.scene().camRoi[2], self.scene().camRoi[3]
        x, y = int(pos.x()), int(pos.y())
        x = x if x >= 0 else 0
        x = x if x <= width else width
        y = y if y >= 0 else 0
        y = y if y <= height else height
        pos.setX(x)
        pos.setY(y)
        
        left = min(self.__startPoint.x(), pos.x())
        top = min(self.__startPoint.y(), pos.y())
        right = max(self.__startPoint.x(), pos.x())
        bottom = max(self.__startPoint.y(), pos.y())
        rc = QRectF(left, top, right - left, bottom - top)
        
        pen = QPen(Qt.SolidLine)
        pen.setColor(Qt.red)
        
        # Draw the roi
        if self.scene().tmpRoi is None:
            self.scene().tmpRoi = BioScopeRoiItem(rc, 'Temp', self)
            self.scene().tmpRoi.setFlags(QGraphicsItem.ItemIsSelectable | \
                                         QGraphicsItem.ItemIsMovable)
            def func1(key, op):
                self.scene().connect(self.scene().tmpRoi.actions[key], SIGNAL('triggered()'), op)
            map(func1, ('SetRoi', 'AddToAnalysis', 'Remove'),
                (self.scene().setRoi, self.scene().addToAnalysis, self.scene().removeTmpRoi))
        else:
            self.scene().tmpRoi.setRect(rc)
            
class StageCtrlDockWidget(QWidget):
    '''
    The dock widget for PI stage controls.
    '''
    
    def __init__(self, parent=None):
        super(StageCtrlDockWidget, self).__init__(parent)
        self.__initLayout()
        
    @pyqtSlot(object)
    def updateStage(self, stageInfo):
        '''
        Update the stage information such as positions, etc.
        '''
        pos = stageInfo['Positions']
        ov = stageInfo['OpenLoopValues']
        svo = stageInfo['ServoStatuses']
        
        def updateItem(row, col, value, fmt='%.4f'):
            self.__stageTable.item(row, col).setText(fmt % value)
        map(updateItem, xrange(3), (1,) * 3, pos)
        map(updateItem, xrange(3), (2,) * 3, ov)
        
        def updateSvo(i, value):
            item = self.__stageTable.item(i, 0)
            checked = (item.checkState() == Qt.Checked)
            if checked != value:
                item.setCheckState(Qt.Checked if value else Qt.Unchecked)
        map(updateSvo, xrange(3), svo)
        
    def __initLayout(self):
        '''
        Initialize the layouts
        '''
        layout = QVBoxLayout()
        self.__stageTable = QTableWidget(3, 3)
        self.__stageTable.setHorizontalHeaderLabels(('Axis', 'Position(um)', 'Open-loop'))
        
        def addAxisNames(row, axis):
            item = QTableWidgetItem(axis)
            item.setCheckState(Qt.Checked)
            item.setFlags((item.flags() | Qt.ItemIsEditable) ^ Qt.ItemIsEditable)
            self.__stageTable.setItem(row, 0, item)
        
        def addValues(indx, text):
            row, col = indx
            self.__stageTable.setItem(row, col, QTableWidgetItem(text))
            
        map(addAxisNames, xrange(3), ('X  ', 'Y  ', 'Z  '))
        map(addValues, tuple((i, j) for i in xrange(3) for j in xrange(1, 3)), ('N/A  ',) * 3 * 2)
        self.__stageTable.resizeColumnsToContents()
        self.__stageTable.resizeRowsToContents()
        self.__stageTable.itemChanged.connect(self.__onItemChenged)
        layout.addWidget(self.__stageTable)        
        
        ctrlPanel = QGridLayout()
        def setButtons(rcName, toolTip, cell, func):
            widget = QToolButton()
            pixmap = QPixmap(':/images/%s.png' % rcName)
            widget.setIcon(QIcon(pixmap))
            if rcName == 'stage':
                widget.setIconSize(QSize(pixmap.width(), pixmap.height()))
            else:
                widget.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
            widget.setToolTip(toolTip)
            widget.clicked.connect(func)
            ctrlPanel.addWidget(widget, cell[0], cell[1], Qt.AlignCenter)
            
        map(setButtons, ('stage', 'left', 'right', 'up', 'down', 'inward', 'outward'),
            ('Move to the center', 'Move left (-x)', 'Move right (+x)',
             'Move up (+y)', 'Move down (-y)', 'Move inward (-z)', 'Move outward (+z)'),
            ((1, 1), (1, 0), (1, 2), (0, 1), (2, 1), (2, 2), (0, 0)),
            (lambda:BioScopeCore.getInstance().moveToCenter(),
             lambda:self.__moveStage('Left'),
             lambda:self.__moveStage('Right'),
             lambda:self.__moveStage('Up'),
             lambda:self.__moveStage('Down'),
             lambda:self.__moveStage('In'),
             lambda:self.__moveStage('Out')))
        ctrlPanel.setSpacing(0)
            
#        self.__btnStage = QToolButton()
#        pixmap = QPixmap(':/images/Stage.png')
#        self.__btnStage.setIcon(QIcon(pixmap))
#        self.__btnStage.setIconSize(QSize(pixmap.width(), pixmap.height()))
#        ctrlPanel.addWidget(self.__btnStage, 1, 1)
#        self.__btnStage.clicked.connect(lambda : BioScopeCore.getInstance().moveToCenter())
#        # right
#        self.__btnRight = QToolButton()
#        pixmap = QPixmap(':/images/right.png')
#        self.__btnRight.setIcon(QIcon(pixmap))
#        self.__btnRight.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        ctrlPanel.addWidget(self.__btnRight, 1, 2, Qt.AlignCenter)
#        self.__btnRight.clicked.connect(lambda : self.__moveStage('Right'))
#        # down
#        self.__btnDown = QToolButton()
#        pixmap = QPixmap(':/images/down.png')
#        self.__btnDown.setIcon(QIcon(pixmap))
#        self.__btnDown.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        ctrlPanel.addWidget(self.__btnDown, 2, 1, Qt.AlignCenter)
#        self.__btnDown.clicked.connect(lambda : self.__moveStage('Down'))
#        # left
#        self.__btnLeft = QToolButton()
#        pixmap = QPixmap(':/images/left.png')
#        self.__btnLeft.setIcon(QIcon(pixmap))
#        self.__btnLeft.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        ctrlPanel.addWidget(self.__btnLeft, 1, 0, Qt.AlignCenter)
#        self.__btnLeft.clicked.connect(lambda : self.__moveStage('Left'))
#        # up
#        self.__btnUp = QToolButton()
#        pixmap = QPixmap(':/images/up.png')
#        self.__btnUp.setIcon(QIcon(pixmap))
#        self.__btnUp.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        ctrlPanel.addWidget(self.__btnUp, 0, 1, Qt.AlignCenter)
#        self.__btnUp.clicked.connect(lambda : self.__moveStage('Up'))
#        ctrlPanel.setSpacing(0)
#        # outward
#        self.__btnOut = QToolButton()
#        pixmap = QPixmap(':/images/outward.png')
#        self.__btnOut.setIcon(QIcon(pixmap))
#        self.__btnOut.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        ctrlPanel.addWidget(self.__btnOut, 0, 0, Qt.AlignCenter)
#        self.__btnOut.clicked.connect(lambda : self.__moveStage('Out'))
#        ctrlPanel.setSpacing(0)
#        # inward
#        self.__btnIn = QToolButton()
#        pixmap = QPixmap(':/images/inward.png')
#        self.__btnIn.setIcon(QIcon(pixmap))
#        self.__btnIn.setIconSize(QSize(pixmap.width() / 2, pixmap.height() / 2))
#        self.__btnIn.setToolTip('Move inward (-z)')
#        ctrlPanel.addWidget(self.__btnIn, 2, 2, Qt.AlignCenter)
#        self.__btnIn.clicked.connect(lambda : self.__moveStage('In'))
#        ctrlPanel.setSpacing(0)
        
        stepSizeGroup = QGroupBox('Step size')
        stepSizeRadioLayout = QVBoxLayout()
        self.__stepSizeButtons = []
        def addRadioButtons(title, stepSize):
            button = QRadioButton(title)
            button.stepSize = stepSize
            stepSizeRadioLayout.addWidget(button)
            self.__stepSizeButtons.append(button)
        map(addRadioButtons, ('10nm', '100nm', '1um', '10um'), (0.01, 0.1, 1, 10))
        self.__stepSizeButtons[0].setChecked(True)
        stepSizeGroup.setLayout(stepSizeRadioLayout)
        
        ctrlLayout = QHBoxLayout()
        ctrlLayout.addLayout(ctrlPanel)
        ctrlLayout.addWidget(stepSizeGroup)
        ctrlLayout.addStretch(1)
        layout.addLayout(ctrlLayout)
        self.setLayout(layout)
        
        # The updating signal
        core = BioScopeCore.getInstance()
        if core.hasStage():
            core.sig_Core_UpdateStage.connect(self.updateStage)
            core.startStageMonitor()
        
    def __moveStage(self, direction):
        # Step size
        for item in self.__stepSizeButtons:
            if item.isChecked():
                stepSize = item.stepSize
                break
        core = BioScopeCore.getInstance()
        svo = core.svoStatus()
        if direction == 'Right' and svo[0]:
            core.moveRelative({1:stepSize})
        elif direction == 'Left' and svo[0]:
            core.moveRelative({1:-stepSize})
        elif direction == 'Up' and svo[1]:
            core.moveRelative({2:stepSize})
        elif direction == 'Down' and svo[1]:
            core.moveRelative({2:-stepSize})
        elif direction == 'Out' and svo[2]:
            core.moveRelative({3:stepSize})
        elif direction == 'In' and svo[2]:
            core.moveRelative({3:-stepSize})
        
    def __onItemChenged(self, item):
        if item.column() == 0:
            self.__onSvoChanged(item)
            
    def __onSvoChanged(self, item):
        BioScopeCore.getInstance().setSvoStatus({item.row() + 1:(item.checkState() == Qt.Checked)})
        edtItem = self.__stageTable.item(item.row(), 1)
        if item.checkState() == Qt.Checked:
            edtItem.setFlags(edtItem.flags() | Qt.ItemIsEditable)
        else:
            edtItem.setFlags((edtItem.flags() | Qt.ItemIsEditable) ^ Qt.ItemIsEditable)
    
class RoiListDockWidget(QWidget):
    '''
    This dock widget is a list of all ROIs, providing ROI information on-the-fly
    
    Signal: sig_RoiListDockWidget_selectionChanged(changedRoiIdList)
    '''
    sig_RoiListDockWidget_selectionChanged = pyqtSignal(tuple)
    
    def __init__(self, parent=None):
        super(RoiListDockWidget, self).__init__(parent)
        layout = QVBoxLayout()
        # Full columns of ROI tabel:
        # index, roi rc, pixel position, physical position, forces, PID term
        self.tabelHeader = ('ROI', 'Tracking (px)', 'Tracking (um)', 'Force')
        self.__roiTable = QTableWidget(0, len(self.tabelHeader))
        self.__roiTable.setHorizontalHeaderLabels(self.tabelHeader)
#        self.__roiTable.horizontalHeader().setStretchLastSection(True)
#        self.__roiTable.setColumnHidden(0, True)
        self.__roiTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.__roiTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.__roiTable.setSelectionMode(QAbstractItemView.MultiSelection)
        self.__roiTable.resizeColumnsToContents()
        self.__roiTable.resizeRowsToContents()
        self.__roiTable.itemSelectionChanged.connect(self.__onSelChanged)
        layout.addWidget(self.__roiTable)
        
        btnLayout = QHBoxLayout()
        self.btnCalibrate = QPushButton('Calibrate')
        self.btnClamp = QPushButton('Start Clamp')
        map(btnLayout.addWidget, (self.btnCalibrate, self.btnClamp))    
        self.btnCalibrate.clicked.connect(lambda:BioScopeMainWindow.getInstance().calibrate())  
        self.btnClamp.clicked.connect(self.onClamp)
        btnLayout.addStretch()
        layout.addLayout(btnLayout)
        self.setLayout(layout)
        self.__roiMap = {}
        
        core = BioScopeCore.getInstance()
        if not core.hasStage():
            map(lambda w:w.setEnabled(False), (self.btnCalibrate, self.btnClamp))                    
        
        self.lastUpdate = time.clock()
        
    def setClampBtnText(self, title):
        self.btnClamp.setText(title)
        
    @pyqtSlot()
    def onClamp(self):
        '''
        Toggle the clamp
        '''
        if len(self.__roiMap) == 0:
            return
        # Get the roiId (the last one of all selected items)
        items = self.__roiTable.selectedItems()
        if items == None:
            roiId = None
        if len(items) == 0:
            roiId = self.__roiTable.item(0, 0).roiId
        else:
            roiId = self.__roiTable.item(items[len(items) - 1].row(), 0).roiId
        BioScopeMainWindow.getInstance().onClamp(roiId)
    
    @pyqtSlot()
    def __onSelChanged(self):
        '''
        Selection changed. Update the scene.
        '''
        items = self.__roiTable.selectedItems()
        # Get the selected roi id
        def func(item):
            return self.__roiTable.item(item.row(), 0).roiId
        self.sig_RoiListDockWidget_selectionChanged.emit(tuple(map(func, items)))
        
    @pyqtSlot(object)
    def onAddToAnalysis(self, roi):
        roiId, roiRc = roi
        indx = self.__roiTable.rowCount()
        self.__roiTable.insertRow(indx)

        # Init items. First column is the rect info, the others are set to be ''
        map(lambda col, msg:self.__roiTable.setItem(indx, col, QTableWidgetItem(msg)),
            xrange(len(self.tabelHeader)), ('(%d, %d, %d, %d)' % roiRc,) + \
             ('',) * (len(self.tabelHeader) - 1))
        
        idItem = self.__roiTable.item(indx, 0)
        idItem.roiId = roiId
        idItem.rc = roiRc
        self.__roiMap[roiId] = idItem
        
        self.__roiTable.resizeColumnsToContents()
        
    @pyqtSlot(object)
    def updateRoi(self, data):
        roiId, delta = data
        idItem = self.__roiMap[roiId]
        roiRc = list(idItem.rc)
        roiRc[0] += delta[0]
        roiRc[1] += delta[1]
        roiRc = tuple(roiRc)
        idItem.rc = roiRc 
        self.__roiTable.item(idItem.row(), 0).setText('(%d, %d, %d, %d)' % roiRc)
        
    @pyqtSlot(object)
    def onRemoveFromAnalysis(self, roiId):
        idItem = self.__roiMap[roiId]
        self.__roiTable.removeRow(idItem.row()) 
        del self.__roiMap[roiId]
        
    @pyqtSlot(object, float)
    def onFrameReady(self, imageData, level):
        '''
        Update the table
        '''
        # Format of imageData:
        # [(roiId,(x,y,z),(0,0,0),(fx,fy)]
        t = time.clock()
        if t - self.lastUpdate < 0.5:
            return
        self.lastUpdate = t
        try:
            result = imageData['GosseResult']
            camRoi = imageData['ROI']
            if result is None:
                return
            def func(updateData):
                if updateData is None:
                    return
                roiId = updateData[0]
#                tableItem = self.__roiMap[roiId]
#                logging.debug(str(tableItem))
#                row = tableItem.row()
                row = self.__roiMap[roiId].row()
                center = list(updateData[1])
                center[0] += camRoi[0]
                center[1] += camRoi[1]
                # tracking (px) info
                self.__roiTable.item(row, 1).setText('(%.2f, %.2f, %.2f)' % tuple(center))
                if len(updateData) < 3:
                    return
                
                # tracking (um) info
                physPos = updateData[2]
                self.__roiTable.item(row, 2).setText('(%.3f,%.3f,%.3f)' % physPos)
                # force
                force = updateData[3]
                self.__roiTable.item(row, 3).setText('Fx=%.1f, Fy=%.1f' % force)
#                map(lambda col, msg:self.__roiTable.item(row, col).setText(msg),
#                    xrange(1, 4), ('%.2f' % center[0], '%.2f' % center[1], '%.2f' % center[2]))
            map(func, result)
            self.__roiTable.resizeColumnsToContents()
        except KeyError:
            pass
        
    @pyqtSlot(tuple)
    def setSelectedRoi(self, data):
        '''
        Set corresponding rows to be selected/unselected
        '''
        roiId, state = data
        row = self.__roiMap[roiId][0].row()
        self.__roiTable.setRangeSelected(QTableWidgetSelectionRange(row, 0,
                                                                    row, self.__roiTable.columnCount() - 1), state)
        
class CamCtrlDockWidget(QWidget):
    '''
    The dock widget for camera control
    
    Data format: Keys: ('RawData', 'Width', 'Height', 'BytesPerPixel',
                        'PixelFormat', 'ROI', 'ScanLine', 'TimeStamp', 'FrameId')
    
    Signals:    acqStarted(), newImage(int), acqAborted(int), acqFinished()
                camOpened(), camClosed()
                sigSetRoi(), fullRoi(), acqStarted(), acqAborted()
    '''       
    
    sigSetRoi = pyqtSignal()
    sigFullRoi = pyqtSignal()
    sigAcqStarted = pyqtSignal(int)
    sigAcqAborted = pyqtSignal()
    
    def __initLayouts(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        cam = BioScopeCore.getInstance().getCam()
        
        # Functional buttons
        layoutBtns = QGridLayout()
        self.btnSnapshot, self.btnLive, self.btnSetRoi, self.btnFullRoi = \
            (QPushButton(name) for name in ('Snapshot', 'Live View', 'Set ROI', 'Full ROI'))
        camLabel = QLabel()
        camLabel.setPixmap(QPixmap(':/images/avt.png'))
        layoutBtns.addWidget(camLabel, 0, 0, 2, 2)
        map(lambda w, row, col:layoutBtns.addWidget(w, row, col),
            (self.btnSnapshot, self.btnLive, self.btnSetRoi, self.btnFullRoi),
            (0, 0, 1, 1), (1, 2, 1, 2))
        mainWnd = BioScopeMainWindow.getInstance()
        map(lambda w, slot: w.clicked.connect(slot),
            (self.btnSnapshot, self.btnLive, self.btnSetRoi, self.btnFullRoi),
            (lambda:mainWnd.snapshot(), lambda:mainWnd.toggleLive(), lambda:mainWnd.setRoi(),
             lambda:mainWnd.fullFrame()))
        self.loFuncBtns = layoutBtns
        layout.addLayout(self.loFuncBtns)
        
        # Controls
                
        loGrid = QGridLayout()

        def addGroup(sldr, edt, label, action, pinfo):
            def edt2sldr(edt, sldr, fmt):
                try:
                    sldr.setValue(float(edt.text()))
                except:
                    edt.setText(fmt % sldr.value())
                    edt.setFocus()
                    edt.selectAll()
            
            sldr.setMaximum(pinfo['Max'])
            sldr.setMinimum(pinfo['Min'])
            sldr.setValue(pinfo['Value'])
            edt.setText('%d' % pinfo['Value'])
            sldr.valueChanged.connect(lambda v : edt.setText('%d' % v))
            sldr.valueChanged.connect(action)
            edt.editingFinished.connect(lambda : edt2sldr(edt, sldr, '%d'))
            edt.setMaximumWidth(40)

            row = loGrid.rowCount()                        
            loGrid.addWidget(QLabel(label), row, 0)
            loGrid.addWidget(edt, row, 1)
            loGrid.addWidget(sldr, row, 2)            

        # Shutter
        self.shutterSldr = QSlider(Qt.Horizontal)
        self.shutterEdt = QLineEdit()
        # Gain
        self.gainSldr = QSlider(Qt.Horizontal)
        self.gainEdt = QLineEdit()
        # Brightness
        self.brightnessSldr = QSlider(Qt.Horizontal)
        self.brightnessEdt = QLineEdit()
        
        map(addGroup, (self.shutterSldr, self.gainSldr, self.brightnessSldr),
            (self.shutterEdt, self.gainEdt, self.brightnessEdt),
            ('Shutter:', 'Gain:', 'Brightness:'),
            (self.onShutter, self.onGain, self.onBrightness),
            (cam.shutter, cam.gain, cam.brightness))
        
        self.loGrid = loGrid
        ctrlGroup = QGroupBox('Camera Control')
        ctrlGroup.setLayout(loGrid)
        layout.addWidget(ctrlGroup)
        
        # Misc
        self.loMisc = QHBoxLayout()
        self.deInterlace = QCheckBox('De-Interlace')
        self.deInterlace.setChecked(cam.deinterlace != 0)
        self.deInterlace.stateChanged.connect(self.onDeInterlace)
        self.mode = QComboBox()
        self.mode.addItems(['%d' % i for i in xrange(4)])
        self.mode.setCurrentIndex(cam.imageMode)
        self.mode.currentIndexChanged.connect(self.onImageMode)
        map(lambda w : self.loMisc.addWidget(w),
            (self.deInterlace, QLabel('Image mode:'), self.mode))
        self.loMisc.addStretch(1)        
        layout.addLayout(self.loMisc)
        
        # Buffer level
        self.bufferLevel = QProgressBar()
        self.bufferLevel.setMinimum(0)
        self.bufferLevel.setMaximum(100)
        bufLayout = QHBoxLayout()
        bufLayout.addWidget(QLabel('Buffer level:'))
        bufLayout.addWidget(self.bufferLevel)
        layout.addLayout(bufLayout)
        
        layout.addStretch(1)
        self.setLayout(layout)
        return
    
    @pyqtSlot(object)
    def showBufferLevel(self, v):
        self.bufferLevel.setValue(int(v))
   
    def onDeInterlace(self, value):
        if value != 0:
            value = 1
        BioScopeCore.getInstance().setDeinterlace(value)
        
    def onShutter(self, value):
        core = BioScopeCore.getInstance()
        core.getCam().shutter = value
        core.pref['Camera']['Shutter'] = value
    
    def onGain(self, value):
        core = BioScopeCore.getInstance()
        core.getCam().gain = value
        core.pref['Camera']['Gain'] = value
        
    def onBrightness(self, value):
        core = BioScopeCore.getInstance()
        core.getCam().brightness = value
        core.pref['Camera']['Brightness'] = value
        
    def onImageMode(self, value):
        BioScopeCore.getInstance().getCam().setImageMode(value)
        
    def __init__(self, parent=None):
        super(CamCtrlDockWidget, self).__init__(parent)
        self.__initLayouts()
            
class BioScopeCore(QObject):
    '''
    The core object for BioScope, providing fundamental functions.
    
    Signals: frameReady, acqAborted, acqFinished
    Slots: onFrameReady, onAcqAborted, onAcqFinished
    '''
    
    sig_Core_FrameReady = pyqtSignal(object, float)
    sig_Core_UpdateStage = pyqtSignal(object)
    sig_Core_CalibrInfo = pyqtSignal(object)
    sig_Core_CalibrProgress = pyqtSignal(float)
    sig_Core_CalibrProgressStart = pyqtSignal()
    sig_Core_CalibrProgressEnd = pyqtSignal()
    sig_Core_Message = pyqtSignal(object)
    sig_Core_BufferNotif = pyqtSignal(float)
    sigAcqAborted = pyqtSignal()
    sigAcqFinished = pyqtSignal()
    sig_BioScopeCore_UpdateRoi = pyqtSignal(object)

    core = None
    
    @classmethod
    def getInstance(cls):
        return cls.core if cls.core is not None else BioScopeCore()
    
    def __init__(self, userName):
        '''
        Load the configuration file and initialize the core object
        '''
        super(BioScopeCore, self).__init__()
        self.userName = userName
        self.__loadPref()
        
        self.initCamera()
        self.initStage()
        BioScopeCore.core = self
        
        # The acquisition thread
        self.__acqThread = None
        # The processing pipeline
        self.__pipeline = ImagePipeline()
        self.__pipelineLock = QReadWriteLock()
        
        # Stage monitor lock
        self.__stageLock = QReadWriteLock()
        
        self.__calibrThread = None
        self.isClamp = False
        
    def takeBackground(self):
        '''
        Take a snapshot and set it as the background
        '''
        imageData = self.__cam.snapshot()
        rawData = imageData['RawData']
        depth = imageData['Depth']
        rc = imageData['ROI']
        bkg = numpy.fromstring(rawData[:rc[2] * rc[3] * depth / 8], dtype=numpy.uint8 if depth == 8 else numpy.float64)
        bkg.shape = rc[3], rc[2]
        if bkg.dtype != numpy.float64:
            bkg = numpy.array(bkg, dtype=numpy.float64)
        self.__pipeline.background = bkg 
        
    def removeBackground(self):
        '''
        Remove the background
        '''
        self.__pipeline.background = None

    def setRoiCalCoeff(self, roiId, coeff):
        '''
        Set the calibrated coefficients for a specified Roi
        '''
        self.__pipeline.roiList[roiId].calCoeff = coeff
        
    def initXYQueue(self, roiId):
        '''
        Initialize the roiId-related xy queues.
        The queues are used to calculate forces.
        '''
        pref = BioScopeCore.getInstance().pref['Analyzer']
        maxQueueLen = pref['MaxQueueLength']
        self.__pipeline.roiList[roiId].xyQueue = \
            tuple(map(lambda i:collections.deque([], maxQueueLen), xrange(2)))        
        
    def setRoiPid(self, roiId, pTerm=None, iTerm=None, dTerm=None):
        '''
        The the PID parameters to the Roi specified by roiId
        '''
        with QWriteLocker(self.__pipelineLock):
            roi = self.__pipeline.roiList[roiId]
            if pTerm is not None:
                roi.PID['P-Term'] = pTerm
                self.pref['Calibration']['P-Term'] = pTerm
            if iTerm is not None:
                roi.PID['I-Term'] = iTerm
            if dTerm is not None:
                roi.PID['D-Term'] = dTerm
            
    def getRoiPid(self, roiId):
        with QReadLocker(self.__pipelineLock):
            return self.__pipeline.roiList[roiId].PID
        
    def getRoiCalCoeff(self, roiId):
        if not self.__pipeline.roiList.has_key(roiId):
            return None
        return self.__pipeline.roiList[roiId].calCoeff
        
    def startDataRecorder(self):
        with QWriteLocker(self.__pipelineLock):
            self.__pipeline.startDataRecorder()
            
    def stopDataRecorder(self):
        with QWriteLocker(self.__pipelineLock):
            self.__pipeline.stopDataRecorder()
            
    def startClamper(self, roiId):
        '''
        Start to clamp
        '''
        with QWriteLocker(self.__pipelineLock):
            roi = self.__pipeline.roiList[roiId]
            if roi.PID is None:
                QMessageBox(QMessageBox.Warning, 'Error', 'Calibration data incomplete.',
                            QMessageBox.Ok).exec_()
                return
            self.__stage.svoStatus = (False,) * 3
            self.__pipeline.startClamp(roiId)
            
    def isRecordingData(self):
        with QReadLocker(self.__pipelineLock):
            return self.__pipeline.isRecording
            
    def stopClamper(self):
        with QWriteLocker(self.__pipelineLock):
            self.__stage.svoStatus = (True,) * 3
            self.__pipeline.stopClamp()               

    def isClamping(self):
        with QReadLocker(self.__pipelineLock):
            return self.__pipeline.isClamping            
                
    def refreshPref(self):
        '''
        When some certain prefereces, e.g. rInner/rOuter/PixelRatio, are modified, the core
        should be refreshed.
        '''
        with QWriteLocker(self.__pipelineLock):
            self.__pipeline.initPolarGrids()
        
    def snapshot(self):
        imageData = self.__cam.snapshot()
        imageData = self.procPipeline(imageData)
        self.sig_Core_FrameReady.emit(imageData, 0)
        return imageData
        
    def addToAnalysis(self, roiId, roiRect):
        with QWriteLocker(self.__pipelineLock):
            self.__pipeline.addRoi(roiId, roiRect)
    
    def getRoiIdList(self):
        '''
        Get all the ROI IDs.
        '''
        return self.__pipeline.roiList.keys()
            
    def removeFromAnalysis(self, roiId):
        with QWriteLocker(self.__pipelineLock):
            self.__pipeline.removeRoi(roiId)
            
    def setThreshold(self, threshold):
        self.__pipeline.setThreshold(threshold)
        
    def initStage(self):
        stagePref = self.pref['PiezoStage']
        if stagePref['Controller'] == 'Local':
            self.__stage = es.PiezoStage(stagePref['BoardId'])
        elif stagePref['Controller'] == 'Remote':
            self.__stage = es.PiezoStageAdapter()
            self.__stage.address = stagePref['IP']
            self.__stage.port = stagePref['MonitorPort']
            
        try:
            self.__stage.connect()
        except es.PiezoStageError:
            try:
                self.__stage.connect()
            except es.PiezoStageError as e:
                QMessageBox(QMessageBox.Warning, 'Error', 'Unable to initialize the piezo stage:\n%s' % e,
                                QMessageBox.Ok).exec_()
                self.__stage = None
        if self.__stage is not None:
            self.__stage.configStatuses = (True,) * 3
            self.__stage.svoStatus = (True,) * 3
                
    
    def hasStage(self):
        return (self.__stage is not None)
        
    def cleanUp(self):
        if self.hasCamera():
            if self.__cam.isConnected:
                self.__cam.disconnect()
            if gSim:    
                avt.SimCamera.releaseLibrary()
            else:
                avt.AVTCamera.releaseLibrary()
        
        if self.hasStage():
            self.__stageMonitorThread.stop()
            self.__stageMonitorThread.wait()
            self.__stage.disconnect()
        
        self.__savePref()
        
    def getCam(self):
        return self.__cam
    
    def initCamera(self):
        '''
        Initialize the camera
        '''
        try:
            if gSim:
                avt.SimCamera.initLibrary()
                nodeList = avt.SimCamera.getNodeList()
                self.__cam = avt.SimCamera.makeCameraInstance(nodeList[0])
            else:
                avt.AVTCamera.initLibrary()
                nodeList = avt.AVTCamera.getNodeList()
                self.__cam = avt.AVTCamera.makeCameraInstance(nodeList[0])
            self.__cam.connect()
            # Initialize the parameters
            widthInfo = self.__cam.width
            heightInfo = self.__cam.height
            self.__cam.roi = (0, 0, widthInfo['Max'], heightInfo['Max'])
            self.__cam.camName = self.__cam.deviceName
            prefCam = self.pref['Camera']
            self.__cam.shutter = prefCam['Shutter']
            self.__cam.gain = prefCam['Gain']
            self.__cam.brightness = prefCam['Brightness']
            self.__cam.deinterlace = prefCam['DeInterlace']
            self.__cam.setImageMode(prefCam['ImageMode'])
        except:
            QMessageBox(QMessageBox.Warning, 'Error', 'Unable to initialize the camera.',
                            QMessageBox.Ok).exec_()
            self.__cam = None
            
    def hasCamera(self):
        return (self.__cam is not None)
            
    def __loadPref(self):
        def defaultPref():
            self.pref = {}
            # Camera
            camPref = {}
            camPref['Shutter'] = 500
            camPref['Gain'] = 0
            camPref['Brightness'] = 50
            camPref['DeInterlace'] = True
            camPref['ImageMode'] = 1
            self.pref['Camera'] = camPref
            
            # PiezoStage
            stagePref = {}
            stagePref['Controller'] = 'Local'
            stagePref['IP'] = '127.0.0.1'
            stagePref['MonitorPort'] = 8182
            stagePref['CommPort'] = 8183
            stagePref['BoardId'] = 1
            self.pref['PiezoStage'] = stagePref
            
            # Analyzer
            anaPref = {}
            anaPref['IsThreshold'] = False
            anaPref['Threshold'] = 10
            anaPref['Algorithm'] = 'None'
            anaPref['InnerRadius'] = 3
            anaPref['OuterRadius'] = 8
            anaPref['Granularity'] = 1
            anaPref['DataLocation'] = '.\\'
            anaPref['MaxQueueLength'] = 500
            anaPref['PersistenceLength'] = 50
            anaPref['kBT'] = 4.2
            anaPref['DNALength'] = 16700
            anaPref['PulseDelta'] = 1
            self.pref['Analyzer'] = anaPref
            
            # Calibration
            calibrPref = {}
            calibrPref['StepCount'] = 32
            calibrPref['LowerEnd'] = (-0.5, -0.5, -1.0)
            calibrPref['UpperEnd'] = (0.5, 0.5, 1.0)
            calibrPref['P-Term'] = (-0.025, 0.025, -0.25)
            calibrPref['I-Term'] = (0,) * 3
            calibrPref['D-Term'] = (0,) * 3
            calibrPref['Velocity'] = (0.2, 0.2, 1)
            self.pref['Calibration'] = calibrPref
            
            # Geometry
            geoPref = {}
            geoPref['UmPixel'] = 0.1
            geoPref['PixelRatio'] = 8.4 / 9.8
            self.pref['Geometry'] = geoPref
            
            # Misc
            miscPref = {}
            miscPref['ColorMap'] = 'Gray'
            miscPref['Threshold'] = 10
            miscPref['IsThreshold'] = True
            self.pref['Misc'] = miscPref
            
            
            with open(self.userName + '_Bioscope.cfg', 'w') as f:
                json.dump(self.pref, f)
        
        try:
            with open(self.userName + '_Bioscope.cfg', 'r') as iniFile:
                data = iniFile.readlines()[0]
                self.pref = json.loads(data)
        except ValueError:
            logging.debug('default')
            defaultPref()
        except IOError:
            defaultPref()
            
    def __savePref(self):
        with open(self.userName + '_Bioscope.cfg', 'w') as f:
            json.dump(self.pref, f)
    
    def setDeinterlace(self, value):
        self.__cam.deinterlace = value
        
    def deinterlace(self):
        return self.__cam.deinterlace
    
    def setExposure(self, value):
        try:
            self.__cam.shutter = value
        except avt.AVTCameraError as err:
            self.message(str(err))
    
    def exposure(self):
        try:
            return self.__cam.shutter
        except avt.AVTCameraError as err:
            self.message(str(err))
    
    def setGain(self, value):
        try:
            self.__cam.gain = value
        except avt.AVTCameraError as err:
            self.message(str(err))
        
    def gain(self):
        try:
            return self.__cam.gain
        except avt.AVTCameraError as err:
            self.message(str(err))
    
    def setBrightness(self, value):
        try:
            self.__cam.brightness = value
        except avt.AVTCameraError as err:
            self.message(str(err))
    def brightness(self):
        try:
            return self.__cam.brightness
        except avt.AVTCameraError as err:
            self.message(str(err))
    
    def setRoi(self, value):
        try:
            self.__cam.roi = (0,) * 4
            self.__cam.roi = value
        except avt.AVTCameraError as err:
            self.message(str(err))
    def fullRoi(self):
        try:
            wmax = self.__cam.width['Max']
            hmax = self.__cam.height['Max']
            self.__cam.roi = (0,) * 4
            self.__cam.roi = (0, 0, wmax, hmax)
        except avt.AVTCameraError as err:
            self.message(str(err))
    def roi(self):
        try:
            return self.__cam.roi    
        except avt.AVTCameraError as err:
            self.message(str(err))
    
    @pyqtSlot(object)
    def onFrameReady(self, imageData):
        # Discard the first frame
        if imageData['FrameId'] == 0:
            return
        imageData = self.procPipeline(imageData)                    
        self.sig_Core_FrameReady.emit(imageData, self.__imageCache.qsize() / float(self.__imageCache.maxsize))
    
    @pyqtSlot()
    def onAcqAborted(self):
        logging.debug('onAcqAborted')
    
    @pyqtSlot()
    def onAcqFinished(self):
        pass
    
    class AcqThread(QThread):
        '''
        The acquisition thread will try to retrieve image data
        from the ring buffer.
        
        Signal: frameReady(), acqAborted(), acqFinished()
        '''
        
        sig_AcqThread_FrameReady = pyqtSignal(object)
        sigAcqAborted = pyqtSignal(name='acqAborted')
        sigAcqFinished = pyqtSignal(name='acqFinished')
        
        def __init__(self, frameCount, parent=None):
            super(QThread, self).__init__(parent)
            self.__frameCount = frameCount
            self.core = BioScopeCore.getInstance()
            self.__cam = self.core.getCam()
            self.__stopFlag = False
            
        def stop(self):
            self.__stopFlag = True
            
        def __retrieve(self, discard):
            '''
            Retrieve a frame from the camera, process it through the pipeline,
            store the processed data, and then emit the 'frameReady' signal
            '''
            imageData = self.__cam.getImage()
            # always discard the first frame
            if not discard:
                self.sig_AcqThread_FrameReady.emit(imageData)
            
        def run(self):
            try:
                self.__cam.openCapture()
                self.__cam.startDevice(self.__frameCount)
            except avt.AVTCameraError as err:
                self.core.message(str(err))
                return
            
            while True:
                for i in xrange(self.__frameCount):
                    if self.__stopFlag:
                        break
#                    logging.debug('#%d' % i)
                    try:
                        self.__retrieve(i == 0)
                    except Queue.Empty:
                        # Abort
                        logging.debug('Queue.Empty exception. Aborted.')
                        self.sigAcqAborted.emit()
                        return
                if self.__stopFlag:
                        break
                self.__cam.stopDevice()
                self.__cam.startDevice(self.__frameCount)
            
            self.sigAcqFinished.emit()
            try:
                self.__cam.stopDevice()
                self.__cam.closeCapture()
            except avt.AVTCameraError as err:
                self.core.message(str(err))
                return
                    
    def startAcquisition(self, frameCount=None):
        '''
        Start the acquisition. Acquire for infinite images 
        if frameCount is none.
        '''
        if frameCount is None:
            frameCount = self.__cam.getParameter(avt.fg.FGP_BURSTCOUNT)['Max'] / 2
        self.__imageCache = Queue.Queue(64)
        self.__acqThread = BioScopeCore.AcqThread(frameCount)
        self.__acqThread.sig_AcqThread_FrameReady.connect(self.onFrameReady, Qt.DirectConnection)
        self.__acqThread.acqFinished.connect(self.onAcqFinished)
        self.__acqThread.acqAborted.connect(self.onAcqAborted)
        self.__acqThread.start()
        
    def stopAcquisition(self):
        self.__acqThread.stop()
        self.__acqThread.wait()
        self.__cam.stopDevice()
        
    def isAcquiring(self):
        return False if self.__acqThread is None else self.__acqThread.isRunning()
    
    def procPipeline(self, imageData):
        '''
        Feed the image data into the pipeline for processing
        '''
        with QReadLocker(self.__pipelineLock):
            return self.__pipeline.runPipeline(imageData)
        
    def position(self):
        '''
        Get the position. => (1.2, 2.4, 8.1)
        '''
        with QWriteLocker(self.__stageLock):
            try:
                return self.__stage.position
            except es.PiezoStageError as err:
                self.message(str(err))
    def setPosition(self, value):
        '''
        Set the position.
        Usage: self.position = (2,3,4)
               self.position = (10, 2)   # for the 1st and 2nd axes
               self.position = {1:2, 3:8.7}
        '''
        with QWriteLocker(self.__stageLock):
            try:
                self.__stage.position = value
            except es.PiezoStageError as err:
                self.message(str(err))
            
    def moveRelative(self, value):
        with QWriteLocker(self.__stageLock):
            try:
                self.__stage.moveRelative(value)
            except es.PiezoStageError as err:
                self.message(str(err))
                
    def message(self, msg):
        self.sig_Core_Message.emit(msg)
            
    def moveToCenter(self):
        '''
        Move the stage to the center along all servo-enabled axes
        '''
        with QWriteLocker(self.__stageLock):
            try:
                # Determine the axes with servo enabled
                svo = self.__stage.svoStatus
                # Centered positions
                upper = self.__stage.upperLimit
                lower = self.__stage.lowerLimit
                pos = tuple(map(lambda u, l:(u + l) / 2.0, upper, lower))
                for i in xrange(len(svo)):
                    if not svo[i]:
                        continue
                    self.__stage.position = {i + 1:pos[i]}
            except es.PiezoStageError as err:
                self.message(str(err))
    
    def openLoopValue(self):
        '''
        Get the open-loop values. => (1.2, 2.4, 8.1)
        '''
        with QWriteLocker(self.__stageLock):
            try:
                return self.__stage.openLoopValue
            except es.PiezoStageError as err:
                self.message(str(err))
    def setOpenLoopValue(self, value):
        with QWriteLocker(self.__stageLock):
            try:
                self.__stage.openLoopValue = value
            except es.PiezoStageError as err:
                self.message(str(err))
                
    def pulseOpenLoop(self, delta):
        with QWriteLocker(self.__stageLock):
            try:
                original = self.__stage.openLoopValue
                logging.debug(str(original))
                val = tuple(delta[i] + original[i] for i in xrange(3))
                logging.debug(str(val))
                self.__stage.openLoopValue = val 
            except es.PiezoStageError as err:
                self.message(str(err))
            
    def svoStatus(self):
        '''
        Get the servo statuses
        '''
        with QWriteLocker(self.__stageLock):
            try:
                return self.__stage.svoStatus
            except es.PiezoStageError as err:
                self.message(str(err))
    def setSvoStatus(self, value):
        with QWriteLocker(self.__stageLock):
            try:
                self.__stage.svoStatus = value
            except es.PiezoStageError as err:
                self.message(str(err))
            
    class StageMonitorThread(QThread):
        '''
        A thread which monitors the PI stage, and update the information
        periodically.
        '''
        def __init__(self, interval=0.5, callback=None, parent=None):
            super(BioScopeCore.StageMonitorThread, self).__init__(parent)
            self.__callback = callback
            self.__interval = interval
            self.__stop = False
            
        def stop(self):
            self.__stop = True
            
        def run(self):
            core = BioScopeCore.getInstance()
            while True:
                if self.__stop:
                    break
                try:
                    pos = core.position()
                    ov = core.openLoopValue()
                    svo = core.svoStatus()
                    if self.__callback is not None:
                        self.__callback(pos, ov, svo)                    
                except Exception as err:
                    logging.debug(err)
                finally:
                    time.sleep(self.__interval)
    
    def startStageMonitor(self):
        def func(pos, ov, svo):
            '''
            Call the core to send stage signals
            '''
            stageInfo = {}
            stageInfo['Positions'] = pos
            stageInfo['OpenLoopValues'] = ov
            stageInfo['ServoStatuses'] = svo
            self.sig_Core_UpdateStage.emit(stageInfo)
            
        self.__stageMonitorThread = BioScopeCore.StageMonitorThread(callback=func)
        self.__stageMonitorThread.start()
    
    class CalibrateThread(QThread):
        '''
        To do calibration
        '''
        def __init__(self, parent=None):
            super(BioScopeCore.CalibrateThread, self).__init__(parent)
            self.__stopFlag = False
            
        def run(self):
            # Get the stops
            core = BioScopeCore.getInstance()
            calibrPref = core.pref['Calibration']
            steps = int(calibrPref['StepCount'])
            lower = calibrPref['LowerEnd']
            upper = calibrPref['UpperEnd']
            delta = map(lambda i:(upper[i] - lower[i]) / (0.5 * steps), xrange(3))
            l = map(lambda i: map(lambda j: lower[j] + i * delta[j], xrange(3)), xrange(steps / 2))
            s = len(l) / 2
            a = l[1:s + 1]
            b = l[s:]
            l.reverse()
            l = l[1:]
            b.extend(l)
            b.extend(a)
            posStops = b
            original = core.position()            
            core.setSvoStatus((True,) * 3)
            calibrInfo = {}
            cnt = 0
            core.sig_Core_CalibrProgressStart.emit()
            # clear the existing ROI coeffs
            for k in core.getRoiIdList():
                core.setRoiCalCoeff(k, None)
            for pos in posStops:
                if self.__stopFlag:
                    core.sig_Core_CalibrProgressEnd.emit()
                    return
                                
                core.sig_Core_CalibrProgress.emit(float(cnt) / steps)
                cnt += 1
                core.setPosition(map(lambda i:pos[i] + original[i], xrange(3)))
                time.sleep(0.05)
                result = core.snapshot()['GosseResult']
                # [(13340442103L, (270.46394366281066, 175.43254407783201, 0.94573643410852704)), (13340442147L, (679.04082673525932, 352.35052837141166, 0.88461538461538458))]
                curPos = core.position()
                curOV = core.openLoopValue()
                for item in result:
                    roiId = item[0]
                    if not calibrInfo.has_key(roiId):
                        calibrInfo[roiId] = []
                    calibrInfo[roiId].append(curPos + curOV + item[1])
#                    try:
#                    except KeyError:
#                        calibrInfo[roiId] = []
#                        calibrInfo[roiId].append(curPos + curOV + item[1])
            core.sig_Core_CalibrProgressEnd.emit()
            '''
            Sample:
            {13340445150L: [(49.9966, 50.0007, 4.9983, 51.4465, 52.2824, 6.0874, 18.178003331283261, 383.513557334013, 0.86440677966101698), 
            (55.0009, 55.0032, 6.4992, 58.4782, 59.2499, 7.8135, 18.133202983225956, 383.5178901586043, 0.85123966942148754),
             (49.9948, 49.9994, 4.9986, 50.3516, 51.3043, 5.6668, 18.191327170273095, 383.50421852383124, 0.8717948717948717), 
             (44.994, 44.9973, 3.4985, 43.2887, 44.2654, 3.9301, 18.181780263856815, 383.53514181404114, 0.85593220338983056), 
             (39.992, 39.9969, 1.9975, 36.7736, 37.7663, 2.389, 18.166110338241566, 383.51724242531657, 0.86324786324786329), 
             (44.9983, 45.0017, 3.4991, 44.7212, 45.5736, 4.4247, 18.189053356154545, 383.51818207479232, 0.8728813559322034), 
             (49.9999, 50.003, 4.9992, 51.7869, 52.5951, 6.1687, 18.207865798136908, 383.48716975423162, 0.8728813559322034)], 
             13340445185L: [(49.9966, 50.0007, 4.9983, 51.4465, 52.2824, 6.0874, 679.04647496144617, 352.1483359596221, 0.86538461538461542), 
             (55.0009, 55.0032, 6.4992, 58.4782, 59.2499, 7.8135, 679.0405547719763, 352.10906668826055, 0.86666666666666659),              
             (49.9948, 49.9994, 4.9986, 50.3516, 51.3043, 5.6668, 679.04889006974429, 352.14843567386123, 0.8834951456310679), 
             (44.994, 44.9973, 3.4985, 43.2887, 44.2654, 3.9301, 679.020910558742, 352.07434166231678, 0.84761904761904772), 
             (39.992, 39.9969, 1.9975, 36.7736, 37.7663, 2.389, 679.02712168256426, 352.12559475216625, 0.875), 
             (44.9983, 45.0017, 3.4991, 44.7212, 45.5736, 4.4247, 679.02768019674943, 352.11777317775977, 0.86407766990291257), 
             (49.9999, 50.003, 4.9992, 51.7869, 52.5951, 6.1687, 679.04978956818479, 352.01650840114394, 0.83809523809523812)]}
            '''
                        
            # Fitting
            for roiId in calibrInfo:
                info = calibrInfo[roiId]
                posx = numpy.array(tuple(v[0] for v in info))          
                posy = numpy.array(tuple(v[1] for v in info))
                posz = numpy.array(tuple(v[2] for v in info))
                ovx = numpy.array(tuple(v[3] for v in info))
                ovy = numpy.array(tuple(v[4] for v in info))
                ovz = numpy.array(tuple(v[5] for v in info))
                crdx = numpy.array(tuple(v[6] for v in info))
                crdy = numpy.array(tuple(v[7] for v in info))
                scorz = numpy.array(tuple(v[8] for v in info))
                px = np.polyfit(ovx, crdx, 1)
                py = np.polyfit(ovy, crdy, 1)
                pz = np.polyfit(ovz, scorz, 1)
                core.setRoiPid(roiId, pTerm=tuple(map(lambda v:0.1 / v[0], (px, py, pz))))
                px = np.polyfit(posx, crdx, 1)
                py = np.polyfit(posy, crdy, 1)
                pz = np.polyfit(posz, scorz, 2)
                core.setRoiCalCoeff(roiId, (px, py, pz, original))
                core.initXYQueue(roiId)
                
            core.sig_Core_CalibrInfo.emit(calibrInfo)
            core.updateCalibrInfo(calibrInfo)
        
        def stop(self):
            self.__stopFlag = True
            self.wait()
            
    def calibrate(self):
        if self.__calibrThread is None or not self.__calibrThread.isRunning():
            self.__calibrThread = BioScopeCore.CalibrateThread()
            self.__calibrThread.start()
        else:
            self.__calibrThread.stop()
        
    def updateCalibrInfo(self, info):
        '''
        Update the calibration info
        
        Format: {roiId:[(x,y,z,ovx,ovy,ovz,pixX,pixY,scoreZ),...],...}
        '''
        with QWriteLocker(self.__pipelineLock):
            for k in info: 
                self.__pipeline.updateRoiCalibrInfo(k, info[k])
    
class ImagePipeline(QObject):
    '''
    The pipeline class for processing images.
    '''
    
    class Roi():        
        def __init__(self, roiId, rect, calibrInfo=None):
            '''
            roiId: 3143241234L, rect: (0,0,8,8)
            '''            
            self.roiId = roiId
            self.rect = rect
            self.calibrInfo = calibrInfo
            pref = BioScopeCore.getInstance().pref['Calibration']
            self.PID = {'P-Term':pref['P-Term'], 'I-Term':pref['I-Term'], 'D-Term':pref['D-Term']}
            self.calCoeff = None
    
    def __init__(self, parent=None):
        super(ImagePipeline, self).__init__(parent)
        self.roiList = {}
        self.loggerList = {}
        self.startTs = 0
        self.__threshold = BioScopeCore.getInstance().pref['Misc']['Threshold']
        self.processors = [self.__applyThreshold, self.deBackground, self.__gosseCenter, self.calcForce, self.doClamp, self.recordData]
        self.initPolarGrids()
        self.background = None
        self.isRecording = False
        self.isClamping = False
        # Do not calculate forces by default
        self.isCalcForce = True
        self.lastClamp = time.clock()
        # Adjust the RxTIme timestamp to seconds elapsed since the Unix Epoch
        self.tsOffset = None
        
    def initPolarGrids(self):
        core = BioScopeCore.getInstance()
        pref = core.pref['Analyzer']
        rInner = pref['InnerRadius']
        rOuter = pref['OuterRadius']
        granularity = pref['Granularity']
        mat = numpy.array(tuple((r, t * 2 * numpy.pi / int(2 * numpy.pi * r / granularity)) \
                          for r in xrange(1, rInner, granularity) for t in xrange(int(2 * numpy.pi * r / granularity))))
        self.__innerPolarGridX = mat[:, 0] * numpy.cos(mat[:, 1])
        self.__innerPolarGridY = mat[:, 0] * numpy.sin(mat[:, 1])
        mat = numpy.array(tuple((r, t * 2 * numpy.pi / int(2 * numpy.pi * r / granularity)) \
                          for r in xrange(rInner, rOuter, granularity) for t in xrange(int(2 * numpy.pi * r / granularity))))
        self.__outerPolarGridX = mat[:, 0] * numpy.cos(mat[:, 1])
        self.__outerPolarGridY = mat[:, 0] * numpy.sin(mat[:, 1])

    def addRoi(self, roiId, roiRect):
        '''
        Roi: key-value pair: {roiId:roiRect}
        '''
        self.roiList[roiId] = ImagePipeline.Roi(roiId, roiRect)
        
    def updateRoiCalibrInfo(self, roiId, info):
        self.roiList[roiId].calibrInfo = info
        
    def removeRoi(self, roiId):
        self.roiList.pop(roiId)
        
    def setThreshold(self, threshold):
        self.__threshold = threshold
    
    def __applyThreshold(self, imageData):
        if self.__threshold is None:
            return imageData
        matData = imageData['NumArray']
        matData *= (matData >= self.__threshold)
        imageData['NumArray'] = matData
        imageData['RawData'] = matData.tostring()
        return imageData
        
    def __gosseCenterXY(self, xyVec):  
        # Normalization
        xStd = np.std(xyVec)
#        xyVec.shape = -1, 1
        l = xyVec.shape[0]
        xMean = np.mean(xyVec)
        xSum = (xyVec - xMean) / xStd
        
        # center
        xSumA = np.flipud(xSum)        
        # Denominator: 1,2,3,...,N,N-1,N-2,...,1
        def func(i):
            v = i + 2 if i <= l - 1 else 2 * l - i
            return v
            
        c = np.correlate(xSum, xSumA, mode='full')# / \
#            np.array(map(func, range(2 * l - 1)))
            
        cmax = np.argmax(c)
        xfit = range(cmax - 2, cmax + 3)
        yfit = c[cmax - 2:cmax + 3]
        try:
            p = np.polyfit(xfit, yfit, 2)
            return -p[1] / (2 * p[0]) / 2
        except:
            pass
    
    def __gosseZ(self, subData, result):
        cx, cy = result
        def getSum(xGrid, yGrid):
            # integer
            xGridInt = numpy.array(xGrid, dtype=numpy.int32)
            yGridInt = numpy.array(yGrid, dtype=numpy.int32)
            # remainder
            xR = xGrid - xGridInt
            yR = yGrid - yGridInt

            # S00.0, S00.1, S00.2,...
            s1 = subData[yGridInt, xGridInt]
            # S01.0, S01.1, S01.2,...
            s2 = subData[yGridInt + 1, xGridInt]
            # S10.0, S10.1,...
            s3 = subData[yGridInt, xGridInt + 1]
            # S11.0, S11.1,...
            s4 = subData[yGridInt + 1, xGridInt + 1]
            S1 = numpy.array((s1, s2, s3, s4), dtype=numpy.float64)
            S1.shape = -1, S1.size
            p1 = (1 - xR) * (1 - yR)
            p2 = xR * (1 - yR)
            p3 = yR * (1 - xR)
            p4 = xR * yR
            S2 = numpy.array((p1, p2, p3, p4))
            S2.shape = -1, S2.size

            return numpy.dot(S1[0, :], S2[0, :])
        return getSum(self.__outerPolarGridX + cx, self.__outerPolarGridY + cy) / \
            getSum(self.__innerPolarGridX + cx, self.__innerPolarGridY + cy)
    
    def __gosseCenter(self, imageData):
        '''
        Gosse center tracking
        '''
        if len(self.roiList.keys()) == 0:
            imageData['GosseResult'] = None
            return imageData
        
        data = imageData['NumArray']
        core = BioScopeCore.getInstance()
        def func(roiId):
            roi = self.roiList[roiId].rect
            subData = data[roi[1]:roi[1] + roi[3], roi[0]:roi[0] + roi[2]]
            xSum = np.sum(subData, 0)
            ySum = np.sum(subData, 1)
            result = map(self.__gosseCenterXY, (xSum, ySum))
            if result[0] is None or result[1] is None:
                return            
            cx = result[0] + roi[0]
            cy = result[1] + roi[1]
            resultZ = self.__gosseZ(data, (cx, cy))
            pos = (result[0] + roi[0], result[1] + roi[1], resultZ)
            
            # now tries to calculate the real physical coordinates in um
            coeff = core.getRoiCalCoeff(roiId)
            if coeff is not None:
                px, py, pz, original = coeff
                cx, cy, cz = pos
                dd = pz[1] ** 2 - 4 * pz[0] * (pz[2] - cz)
                if dd < 0:
                    posz = 0
                else:
                    posz1 = -(pz[1] + math.sqrt(dd)) / (2 * pz[0])
                    posz2 = -(pz[1] - math.sqrt(dd)) / (2 * pz[0])
                    oz = original[2]
                    posz = posz1 if abs(posz1 - oz) < abs(posz2 - oz) else posz2                
                posR = ((cx - px[1]) / px[0], (cy - py[1]) / py[0], posz)
                gosseResult = [roiId, pos, posR]
            else:
                gosseResult = [roiId, pos]
            
            # Update the roi
            dx = round(result[0] - 0.5 * roi[2])
            dy = round(result[1] - 0.5 * roi[3])
            if dx != 0 or dy != 0:
                roi = list(roi)
                roi[0] += dx
                roi[1] += dy
                self.roiList[roiId].rect = tuple(roi)
                BioScopeCore.getInstance().sig_BioScopeCore_UpdateRoi.emit((roiId, (dx, dy)))
            return gosseResult
        
        imageData['GosseResult'] = map(func, self.roiList.keys()) 
        return imageData
    
    def deBackground(self, imageData):
        '''
        Reduce the background
        '''
        if self.background is None:
            return imageData
        mat = imageData['NumArray']
        if mat.shape[0] != self.background.shape[0] or mat.shape[1] != self.background.shape[1]:
            # Dimensions don't coincident.
            logging.debug('Dimensions don\'t coincident.')
            self.background = None
            return imageData
        mat = mat - self.background
        imageData['NumArray'] = mat - mat.min()
        imageData['RawData'] = numpy.array(imageData['NumArray'], dtype=numpy.uint8).tostring()
        return imageData
    
    def updateIValue(self, posDelta):
        popValue = (0,) * 3
        if self.__iValueCnt > self.__iValQueueSize - 1:
            popValue = self.__iValQueue.get()
            self.__iValueCnt -= 1
        self.__iValQueue.put(posDelta)
        self.__iValueCnt += 1
        self.iClampValue = tuple(map(lambda i:self.iClampValue[i] + posDelta[i] - popValue[i], xrange(3)))
    
    def startClamp(self, roiId):
        '''
        Run for the first time when clamping is started. Get the initial positions of X/Y/Z
        '''
        self.isClamping = True
        self.clampRoiId = roiId
        self.clampOrigin = None
        
        # Store the i-values
        self.__iValQueue = Queue.Queue()
        self.__iValueCnt = 0
        self.__iValQueueSize = 100
        
        # low-pass filter
        self.__lowPass = Queue.Queue()
        self.__lowPassCnt = 0
        self.__lowPassSize = 50
        
        if not self.isRecording:
            # start the recorder
            self.startByClamp = True
            self.isRecording = True        
        
    def stopClamp(self):
        self.isClamping = False
        self.clampOrigin = None
        if self.startByClamp:
            # stop the recorders
            for roiId in self.loggerList.keys():
                self.loggerList[roiId].close() 
            self.loggerList = {}
            self.startByClamp = False
            self.isRecording = False
        
    def recordData(self, imageData):
        '''
        Record format:
        X/Y/Z_Pix: coordinates (pixel)
        X/Y/Z_Phys: physical coordinates(um), zero if the system hasn't been calibrated.
        X/Y/Z_Pos: PI-E761 positions(um)
        X/Y/Z_Value: PI-E761 open-loop values
        
        '''
        if not self.isRecording:
            return imageData
        gosseResult = imageData['GosseResult']
        camRoi = imageData['ROI']
        if gosseResult is None:
            return imageData
        
        frameId = imageData['FrameId']
        ts = imageData['TimeStamp'] / 1e7
        if self.tsOffset is None:
            # Calculate the offset:
            dt = calendar.timegm(time.gmtime())
            self.tsOffset = ts - dt
        core = BioScopeCore.getInstance()
        for item in gosseResult:
            roiId = item[0]
#            coeff = core.getRoiCalCoeff(roiId)
            try:
                rdr = self.loggerList[roiId]
            except KeyError:
                baseDir = BioScopeCore.getInstance().pref['Analyzer']['DataLocation']
                dir1 = '%s/%s' % (baseDir, time.strftime('%Y%m%d'))
                if not os.path.exists(dir1):            
                    os.makedirs(dir1)
                fname = '%s/%s_%d.txt' % (dir1, time.strftime('%Y%m%d_%H%M%S'), roiId)
                rdr = open(fname, 'w')
                rdr.write('FrameId,\tTimestamp,\tX_Pix,\tY_Pix,\tZ_Pix,\tX_Phys,\tY_Phys,\tZ_Phys,\tX_Pos,\tY_Pos,\tZ_Pos,\tX_Value,\tY_Value,\tZ_Value,\tX_Target,\tY_Target,\tZ_Target,\tX_IVal,\tY_IVal,\tZ_IVal\n')
                self.loggerList[roiId] = rdr
                
                
#            if coeff is not None:
#                # Try to calculate the 'real' coordinate in microns
#                px, py, pz, original = coeff
#                cx, cy, cz = pos
#                dd = pz[1] ** 2 - 4 * pz[0] * (pz[2] - cz)
#                if dd < 0:
#                    logging.debug('%f,%f,%f' % pz)
#                posz1 = -(pz[1] + math.sqrt(dd)) / (2 * pz[0])
#                posz2 = -(pz[1] - math.sqrt(dd)) / (2 * pz[0])
#                oz = original[2]
#                posz = posz1 if abs(posz1 - oz) < abs(posz2 - oz) else posz2                
#                pos = (pos[0] + camRoi[0], pos[1] + camRoi[1],
#                       pos[2]) + ((cx - px[1]) / px[0], (cy - py[1]) / py[0], posz)
#            else:
#                pos = (pos[0] + camRoi[0], pos[1] + camRoi[1], pos[2]) + (0, 0, 0)
    
            pos = item[1]
            if len(item) == 2:
                p = (pos[0] + camRoi[0], pos[1] + camRoi[1], pos[2]) + (0, 0, 0)
            else:
                pR = item[2]
                p = (pos[0] + camRoi[0], pos[1] + camRoi[1], pos[2]) + pR

            if self.isClamping:
                targetOv = self.targetOv
                stagePos = self.stagePos
                stageOv = self.stageOv
                iClampVal = self.iClampValue
            else:
                targetOv = (0, 0, 0)
                stagePos = core.position()
                stageOv = core.openLoopValue()
                iClampVal = targetOv
                
            data = (frameId, ts - self.tsOffset) + p + stagePos + stageOv + targetOv + iClampVal
            rdr.write(('%d' + ',\t%f' * 19 + '\n') % data)
        return imageData
    
    def startDataRecorder(self):
        self.isRecording = True
        
    def stopDataRecorder(self):
        self.isRecording = False
        map(lambda k:self.loggerList[k].close(), self.loggerList.keys())
        self.loggerList = {}
        
    def calcForce(self, imageData):
        '''
        With the particle-localization data, one can calculate the magnetic force
        '''
        if not self.isCalcForce:
            return imageData
        
        gosseResult = imageData['GosseResult']
        if gosseResult is None:
            return imageData
        
        core = BioScopeCore.getInstance()
        pref = core.pref['Analyzer']
        P = pref['PersistenceLength']
        L0 = pref['DNALength']
        kBT = pref['kBT']
        def f1(v):
            '''
            Get the force from var.
            '''
            # m*y^2 + (1-2*m)*y + (m-2) = 0
            # y = l / L0
            # F = kBT*L0*y / v
            v = v * 1e6
            m = 4 * (P * L0 / v - 1)
            if m == float('nan') or m == float('inf'):
                return 0            
            dd = (1 - 2 * m) ** 2 - 4 * m * (m - 2)
            if dd < 0:
                # Something wrong must have happened
                return 0
            y1 = (2 * m - 1 + math.sqrt(dd)) / (2 * m)
            y2 = (2 * m - 1 - math.sqrt(dd)) / (2 * m)
            if y1 >= 0 and y1 <= 1:
                y = y1
            else:
                y = y2
            return kBT * L0 * y / v

        for item in gosseResult:
            if len(item) < 3:
                # no calibrated coordinates
                continue
            
            roiId = item[0]
            pR = item[2]
            xque, yque = self.roiList[roiId].xyQueue
            xque.append(pR[0])
            yque.append(pR[1])
            l = tuple(map(f1, map(numpy.var, (xque, yque))))
            item.append(l)
        
        return imageData
        
    def doClamp(self, imageData):
        '''
        Do the clamping
        '''
        if not self.isClamping:
            return imageData
        
        core = BioScopeCore.getInstance()
        gosseResult = imageData['GosseResult']
        if gosseResult is None:
            return imageData
        
        vco = core.pref['Calibration']['Velocity']
        t0 = time.clock()
        dt = t0 - self.lastClamp
        self.lastClamp = t0
        
        for item in gosseResult:
            roiId = item[0]
            pos = item[1]
            if roiId != self.clampRoiId:
                continue
            self.stagePos = core.position()
            self.stageOv = core.openLoopValue()        
            if self.clampOrigin is None:
                # This is the first time during a feedback
                self.iClampValue = (0,) * 3
                self.__lowPassDelta = (0,) * 3
                self.clampOrigin = pos
                self.targetOv = self.stageOv
            else:
                pid = core.getRoiPid(roiId)
                pTerm = pid['P-Term']
                iTerm = pid['I-Term']
                
                delta = tuple(map(lambda i:pos[i] - self.clampOrigin[i], xrange(3)))
                self.updateIValue(delta)
                
                # low pass filter for p-Terms
                popValue = (0,) * 3
                if self.__lowPassCnt >= self.__lowPassSize - 1:
                    popValue = self.__lowPass.get()
                    self.__lowPassCnt -= 1
                self.__lowPass.put(delta)
                self.__lowPassCnt += 1
                self.__lowPassDelta = tuple(self.__lowPassDelta[i] + delta[i] - popValue[i] for i in xrange(3))
                
                delta = tuple(delta[i] / self.__lowPassCnt for i in xrange(3))                            
                
#                self.iClampValue = tuple(map(lambda i:self.iClampValue[i] + delta[i], xrange(3)))
                def func(i):
                    d = -delta[i] * pTerm[i] - self.iClampValue[i] * iTerm[i]
                    m = vco[i] * dt
                    d = d if abs(d) <= m else m if d > 0 else -m
                    return self.stageOv[i] + d
                self.targetOv = tuple(map(func, xrange(3)))
#                logging.debug('delta: %f, iValue: %f, openVal: %f, targetVal: %f' % \
#                              (delta[2], self.iClampValue[2], self.stageOv[2], self.targetOv[2]))
                core.setOpenLoopValue(self.targetOv)
            break
        return imageData
    
    def runPipeline(self, imageData):
        rawData = imageData['RawData']
        depth = imageData['Depth']
        rc = imageData['ROI']
        if isinstance(rawData, str):
            data = numpy.fromstring(rawData[:rc[2] * rc[3] * depth / 8], dtype=numpy.uint8 if depth == 8 else numpy.float64)
            rc = imageData['ROI']
            data.shape = rc[3], rc[2]
            imageData['NumArray'] = data
        for proc in self.processors:
            imageData = proc(imageData)
        return imageData
            
class AnalysisDockWidget(QWidget):
    '''
    This is a dock for analysis settings
    '''
    
    def __init__(self, parent=None):
        super(AnalysisDockWidget, self).__init__(parent)
        
        layout = QVBoxLayout()
        gosseEnabled = QCheckBox('Gosse Analysis')
        layout.addWidget(gosseEnabled)
        
        rInnerLabel = QLabel('Inner Radius: ')
        rInnerEdt = QLineEdit('4')
        rOuterLabel = QLabel('Outer Radius: ')
        rOuterEdt = QLineEdit('8')
        paraLayout = QHBoxLayout()
        map(lambda widget:paraLayout.addWidget(widget),
            (rInnerLabel, rInnerEdt, rOuterLabel, rOuterEdt))
        layout.addLayout(paraLayout)
                
        calLabel = QLabel('Calibration Proximity: ')
        calEdt = QTextEdit('4')
        calStart = QPushButton('Start')
        paraLayout = QHBoxLayout()
        paraLayout.addWidget(calLabel)
        paraLayout.addWidget(calEdt)
        paraLayout.addWidget(calStart)
        layout.addLayout(paraLayout)
        
        self.setLayout(layout)
        
class PulseDialog(QDialog):
    def __init__(self, parent=None):
        super(PulseDialog, self).__init__(parent)
        
        mainLayout = QHBoxLayout()
        delta = BioScopeCore.getInstance().pref['Analyzer']['PulseDelta']
        self.edtDelta = QLineEdit('%.3f' % delta)
        labelDelta = QLabel("Delta")
        btnOk = QPushButton('OK')
        btnOk.clicked.connect(self.accept)
        btnCancel = QPushButton('Cancel')
        btnCancel.clicked.connect(self.reject)
        
        mainLayout.addWidget(labelDelta)
        mainLayout.addWidget(self.edtDelta)
        mainLayout.addWidget(btnOk)
        mainLayout.addWidget(btnCancel)
        self.setLayout(mainLayout)
        
    def accept(self):
        core = BioScopeCore.getInstance()
        val = float(self.edtDelta.text())
        core.pref['Analyzer']['PulseDelta'] = val
        
        try:
            originalSVO = core.svoStatus()
            core.setSvoStatus((False,) * 3) 
            core.pulseOpenLoop((val,) * 3)
            core.setSvoStatus(originalSVO)
        except es.PiezoStageError as err:
            core.message(str(err))
                
class PrefDialog(QDialog):
    '''
    Preferences dialog
    '''
    def __init__(self, parent=None):
        super(PrefDialog, self).__init__(parent)
        self.mainLayout = QVBoxLayout()
        self.__initCalibr()
        self.__initGeometry()
        self.__initAnalyzer()
        btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)        
        self.mainLayout.addWidget(btnBox)
        
        self.setLayout(self.mainLayout)
        
    def accept(self):
        pref = BioScopeCore.getInstance().pref
        try:
            calPref = pref['Calibration']
            bkp = copy.deepcopy(calPref)
            calPref['StepCount'] = int(self.__edtSteps.text())
            calPref['LowerEnd'] = tuple(map(lambda v:float(v.text()),
                                            (self.__edtXStart, self.__edtYStart, self.__edtZStart)))
            calPref['UpperEnd'] = tuple(map(lambda v:float(v.text()),
                                          (self.__edtXEnd, self.__edtYEnd, self.__edtZEnd)))
            calPref['I-Term'] = tuple(map(lambda v:float(v.text()),
                                        (self.edtITermX, self.edtITermY, self.edtITermZ)))
            calPref['Velocity'] = tuple(map(lambda v:float(v.text()),
                                        (self.edtVcoX, self.edtVcoY, self.edtVcoZ)))
        except ValueError:
            pref['Calibration'] = bkp
            
        try:
            geoPref = pref['Geometry']
            bkp = copy.deepcopy(geoPref)
            geoPref['UmPixel'] = float(self.edtUmPixel.text())
            geoPref['PixelRatio'] = float(self.edtPixelRatio.text())
        except ValueError:
            pref['Geometry'] = bkp
            
        try:
            anaPref = pref['Analyzer']
            bkp = copy.deepcopy(anaPref)
            anaPref['InnerRadius'] = int(self.edtInnerRadius.text())
            anaPref['OuterRadius'] = int(self.edtOuterRadius.text())
            anaPref['Granularity'] = int(self.edtGranularity.text())
            anaPref['DataLocation'] = self.dataLocation
        except ValueError:
            pref['Analyzer'] = bkp
            
        BioScopeCore.getInstance().refreshPref()
        
        super(PrefDialog, self).accept()
        
    def __initCalibr(self):
        calibrGroup = QGroupBox('Calibration')
        core = BioScopeCore.getInstance()
        calibrPref = core.pref['Calibration']
        steps = calibrPref['StepCount']
        lower = calibrPref['LowerEnd']
        upper = calibrPref['UpperEnd']
        iTerm = calibrPref['I-Term']
        vco = calibrPref['Velocity']
        gridLayout = QGridLayout()
        self.__edtSteps = QLineEdit('%d' % steps)
        gridLayout.addWidget(QLabel('# of steps:'), 0, 0)
        gridLayout.addWidget(self.__edtSteps, 0, 1)
        self.__edtXStart = QLineEdit('%.4f' % lower[0])
        self.__edtXEnd = QLineEdit('%.4f' % upper[0])
        self.__edtYStart = QLineEdit('%.4f' % lower[1])
        self.__edtYEnd = QLineEdit('%.4f' % upper[1])
        self.__edtZStart = QLineEdit('%.4f' % lower[2])
        self.__edtZEnd = QLineEdit('%.4f' % upper[2])
        def func(axis, edtLower, edtUpper, row):
            gridLayout.addWidget(QLabel('Axis %s:' % axis), row, 0, Qt.AlignRight)
            gridLayout.addWidget(edtLower, row, 1)
            gridLayout.addWidget(QLabel('~'), row, 2)
            gridLayout.addWidget(edtUpper, row, 3)
        map(func, ('X', 'Y', 'Z'), (self.__edtXStart, self.__edtYStart, self.__edtZStart),
            (self.__edtXEnd, self.__edtYEnd, self.__edtZEnd), xrange(1, 4))
        
        gridLayout.addWidget(QLabel('I-Term:'), 4, 0, Qt.AlignRight)
        iTermLayout = QHBoxLayout()
        self.edtITermX = QLineEdit('%.4f' % iTerm[0])
        self.edtITermY = QLineEdit('%.4f' % iTerm[1])
        self.edtITermZ = QLineEdit('%.4f' % iTerm[2])
        map(lambda w:iTermLayout.addWidget(w),
            (self.edtITermX, self.edtITermY, self.edtITermZ))
        gridLayout.addLayout(iTermLayout, 4, 1, 1, 3)
        
        gridLayout.addWidget(QLabel('Velocity Control:'), 5, 0, Qt.AlignRight)
        vcoLayout = QHBoxLayout()
        self.edtVcoX = QLineEdit('%.4f' % vco[0])
        self.edtVcoY = QLineEdit('%.4f' % vco[1])
        self.edtVcoZ = QLineEdit('%.4f' % vco[2])
        map(lambda w:vcoLayout.addWidget(w),
            (self.edtVcoX, self.edtVcoY, self.edtVcoZ))
        gridLayout.addLayout(vcoLayout, 5, 1, 1, 3)
        
        calibrGroup.setLayout(gridLayout)
        self.mainLayout.addWidget(calibrGroup)
        
    def __initGeometry(self):
        geoGroup = QGroupBox('Geometry')
        gridLayout = QGridLayout()
        pref = BioScopeCore.getInstance().pref['Geometry']
        umPixel = pref['UmPixel']
        pixelRatio = pref['PixelRatio']
        self.edtUmPixel = QLineEdit('%f' % umPixel)
        self.edtPixelRatio = QLineEdit('%f' % pixelRatio)
        gridLayout.addWidget(QLabel('Um/Pixel:'), 0, 0)
        gridLayout.addWidget(self.edtUmPixel, 0, 1)
        gridLayout.addWidget(QLabel('Pixel ratio:'), 1, 0)
        gridLayout.addWidget(self.edtPixelRatio, 1, 1)
        geoGroup.setLayout(gridLayout)
        self.mainLayout.addWidget(geoGroup)
        
    def __initAnalyzer(self):
        anaGroup = QGroupBox('Analyzer')
        g = QGridLayout()
        pref = BioScopeCore.getInstance().pref['Analyzer']
        inR = pref['InnerRadius']
        otR = pref['OuterRadius']
        self.dataLocation = pref['DataLocation']
        granularity = pref['Granularity']
        self.edtInnerRadius = QLineEdit('%d' % inR)
        self.edtOuterRadius = QLineEdit('%d' % otR)
        self.edtGranularity = QLineEdit('%d' % granularity)
        btnLocation = QPushButton('Data Location')
        btnLocation.clicked.connect(self.setLocation)
        btnOpenLocation = QPushButton('Open Data Location')
        btnOpenLocation.clicked.connect(self.openLocation)
        g.addWidget(QLabel('Inner Radius:'), 0, 0)
        g.addWidget(self.edtInnerRadius, 0, 1)
        g.addWidget(QLabel('Outer Radius:'), 1, 0)
        g.addWidget(self.edtOuterRadius, 1, 1)
        g.addWidget(QLabel('Granularity:'), 2, 0)
        g.addWidget(self.edtGranularity, 2, 1)
        btnLayout = QHBoxLayout()
        btnLayout.addWidget(btnLocation)
        btnLayout.addWidget(btnOpenLocation)
        g.addLayout(btnLayout, 3, 0, 1, 2)
        anaGroup.setLayout(g)
        self.mainLayout.addWidget(anaGroup)
        
    def setLocation(self):
        pref = BioScopeCore.getInstance().pref['Analyzer']
        self.dataLocation = pref['DataLocation']
        dlg = QFileDialog(caption='Select the location', directory=self.dataLocation)
        dlg.setFileMode(QFileDialog.Directory)
        if dlg.exec_() == QDialog.Accepted:
            loc = '%s' % dlg.selectedFiles()[0]
            self.dataLocation = loc
            
    def openLocation(self):
        loc = BioScopeCore.getInstance().pref['Analyzer']['DataLocation']
        loc = '"%s"' % loc.replace('/', '\\')
        os.system('explorer %s' % loc)

class PlotDialog(QDialog):
    def __init__(self, roiId, data, parent=None):
        super(PlotDialog, self).__init__(parent)
        
        # Create the mpl Figure and FigCanvas objects. 
        # 5x4 inches, 100 dots-per-inch
        #
        dpi = 100
        fig = Figure((8.0, 8.0), dpi=dpi)
        canvas = FigureCanvas(fig)
        canvas.setParent(self)
        axisX = fig.add_subplot(311)
        axisX.set_xlabel('X(um)')        
        axisY = fig.add_subplot(312)
        axisY.set_xlabel('Y(um)')
        axisZ = fig.add_subplot(313)
        axisZ.set_xlabel('Z(um)')
        fig.subplots_adjust(hspace=0.5)
        map(lambda axis:axis.grid(True), (axisX, axisY, axisZ))
        map(lambda axis:axis.hold(True), (axisX, axisY, axisZ))
        toolbar = NavigationToolbar(canvas, self)

        vbox = QVBoxLayout()
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbox.addWidget(canvas)
        vbox.addWidget(toolbar)       

        for item in data:
            x1 = item[0]
            y1 = item[1]
            x2 = item[2]
            y2 = item[3]
            x3 = item[4]
            y3 = item[5]
            axisX.scatter(x1, y1)
            axisY.scatter(x2, y2)
            axisZ.scatter(x3, y3)
        
        groupBox = QGroupBox('Parameters')
        core = BioScopeCore.getInstance()
        pid = core.getRoiPid(roiId)
        lblPTerm = QLabel('P-Term: %f, %f, %f' % tuple(map(lambda i:pid['P-Term'][i], xrange(3))))
#        coeff = core.getRoiCalCoeff(roiId)
#        ce = coeff[:2]
#        ce += coeff[2]
#        lblCal = QLabel('coeff X: %f, coeff Y: %f, coeff Z: %f, %f', ce)
        layout = QVBoxLayout()
        layout.addWidget(lblPTerm)
#        layout.addWidget(lblCal)
        groupBox.setLayout(layout)
        vbox.addWidget(groupBox)
        
        btnBox = QDialogButtonBox()   
        btnBox.addButton('Save', QDialogButtonBox.ActionRole)
        btnBox.addButton('Close', QDialogButtonBox.RejectRole)
        btnBox.clicked.connect(self.onBtnBoxClicked)
        vbox.addWidget(btnBox)
        self.btnBox = btnBox
        self.setLayout(vbox)
            
    def onBtnBoxClicked(self, button):
        if self.btnBox.buttonRole(button) == QDialogButtonBox.ActionRole:
            self.saveData()
        else:
            self.accept()
            
    def saveData(self):
        '''
        Save the calibration data
        '''
        logging.debug('Accepted')
        self.accept()

class LoginDialog(QDialog):
    '''
    The startup login window.
    '''
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        
        userList = QListWidget()
        userList.addItems(self.getUsers())
        userList.setCurrentRow(0)
        userList.setSelectionMode(QAbstractItemView.SingleSelection)
        userList.itemDoubleClicked.connect(self.onItemDoubleClicked)
        self.userList = userList
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel('Select a user:'))
        layout.addWidget(userList)
        
        btnBox = QDialogButtonBox()
        self.btnNew = QPushButton('New')
        btnBox.addButton(self.btnNew, QDialogButtonBox.ActionRole)
        self.btnRemove = QPushButton('Remove')
        btnBox.addButton(self.btnRemove, QDialogButtonBox.ActionRole)
        btnBox.addButton('Login', QDialogButtonBox.AcceptRole)
        btnBox.clicked.connect(self.onClicked)
        btnBox.accepted.connect(self.accept)
        layout.addWidget(btnBox)
        
        self.setLayout(layout)
        
    def onItemDoubleClicked(self, item):
        self.userList.setCurrentItem(item)
        self.accept()
        
    def onClicked(self, button):
        if button == self.btnNew:
            # New user
            name, ret = QInputDialog.getText(self, 'New User', 'Name of the new user:')
            if not ret:
                return
            name = str(name)
            if name == '':
                return
            newItem = QListWidgetItem(name)
            self.userList.addItem(newItem)
            self.userList.setCurrentItem(newItem)
        elif button == self.btnRemove:
            # Remove the user
            items = self.userList.selectedItems()
            if len(items) == 0:
                logging.debug('empty')
                return
            self.userList.takeItem(self.userList.row(items[0]))
    
    def accept(self):
        items = self.userList.selectedItems()
        if len(items) == 0:
            return
        self.user = items[0].text()
        super(LoginDialog, self).accept()
        
    def getUsers(self):
        '''
        Return a list of users
        '''
        import re
        files = os.listdir('.')
        l = []
        
        p = re.compile('^(.+)_Bioscope.cfg$')
        def func(fileName):
            r = p.match(fileName)
            if r is None:
                return
            l.append(r.groups()[0])
        map(func, files)
        
        return l
        
class BioScopeMainWindow(QMainWindow):
    '''
    The main window class of BioScope
    '''
    
    mainWindow = None
    
    @classmethod
    def getInstance(cls):
        return cls.mainWindow
    
    def __init__(self, app=None, parent=None):
        super(BioScopeMainWindow, self).__init__(parent)
        self.app = app
        BioScopeMainWindow.mainWindow = self
        
        controlMenu = self.menuBar().addMenu('&Control')
        analysisMenu = self.menuBar().addMenu('&Analysis')
        optionMenu = self.menuBar().addMenu('&Options')
        optionMenu.addAction(self.__createAction('&Preferences', self.prefDlg, 'Ctrl+,'))
        helpMenu = self.menuBar().addMenu('&Help')
        helpMenu.addAction(self.__createAction('About', self.aboutDlg))
        
        core = BioScopeCore.getInstance()
        if core.hasCamera():
            controlMenu.addAction(self.__createAction('&Snapshot', self.snapshot, shortcut='F6'))
            self.toggleLiveAction = self.__createAction('Live View', self.toggleLive, shortcut='F5')
            controlMenu.addAction(self.toggleLiveAction)
            controlMenu.addAction(self.__createAction('Set &ROI', self.setRoi, 'Ctrl+R'))
            controlMenu.addAction(self.__createAction('Full &Frame', self.fullFrame, 'Ctrl+F'))
            controlMenu.aboutToShow.connect(self.onShowControlMenu)
            
        if core.hasCamera():
            analysisMenu.addAction(self.__createAction('&Take Background', self.takeBackground, shortcut='Ctrl-B'))
            analysisMenu.addAction(self.__createAction('&Remove Background', self.removeBackground, shortcut='Ctrl-D'))
            analysisMenu.addSeparator()
            self.dataRecorder = self.__createAction('Record &Data', self.toggleDataRecorder, checkable=True)
            analysisMenu.addAction(self.dataRecorder)
            self.applyPulseAction = self.__createAction('Apply Pulse', self.applyPulse)
            analysisMenu.addAction(self.applyPulseAction)
            analysisMenu.aboutToShow.connect(self.onShowAnalysisMenu)

        # Dock widget
        self.createDockWindows()
        
        # Status bar
        status = self.statusBar()
        coordLabel = QLabel()
        status.addPermanentWidget(coordLabel)
        status.coord = coordLabel
        fpsLabel = QLabel()
        status.addPermanentWidget(fpsLabel)
        status.fps = fpsLabel
        
        self.__view = BioScopeView()
        self.setCentralWidget(self.__view)
        core = BioScopeCore.getInstance()
        # Draw the acquired images
        core.sig_Core_FrameReady.connect(self.__view.onFrameReady)
        # Update the ROI information
        core.sig_Core_FrameReady.connect(self.roiTable.onFrameReady)
        # Show FPS information
        core.sig_Core_FrameReady.connect(self.onFrameReady)
        core.sig_Core_CalibrInfo.connect(self.plotCalibrInfo)
        core.sig_Core_CalibrProgress.connect(self.calibrProgress)
        core.sig_Core_CalibrProgressStart.connect(self.calibrProgressStart)
        core.sig_Core_CalibrProgressEnd.connect(self.calibrProgressEnd)
        core.sig_Core_Message.connect(self.showMessage)
        self.__view.sig_Scene_BroadcastInfo.connect(self.onUpdateImageInfo)
        self.__view.sig_BioScopeView_AddToAnalysis.connect(self.roiTable.onAddToAnalysis)
        self.__view.sig_BioScopeView_RemoveFromAnalysis.connect(self.roiTable.onRemoveFromAnalysis)
        core.sig_BioScopeCore_UpdateRoi.connect(self.__view.updateRoi)
        core.sig_BioScopeCore_UpdateRoi.connect(self.roiTable.updateRoi)
        
        self.roiTable.sig_RoiListDockWidget_selectionChanged.connect(self.__view.setSelectedRoi)
        
        # Set the initial size
        self.setGeometry(QRect(100, 100, 1000, 600))
        
        # Preferences
        self.__gosseEnabled = False        
        
        # Others
        self.__genColorSpace()
        self.__colormap = 'Gray'
        self.__fpsQueue = collections.deque([], 10)
        self.lastUpdate = 0
        
        self.setWindowState(Qt.WindowMaximized)
        
    def applyPulse(self):
        '''
        Shwo the pulse setting dialog
        '''
        dlg = PulseDialog()
        dlg.exec_()
        
    def toggleDataRecorder(self):
        # Is the data location reachable?
        core = BioScopeCore.getInstance()
        baseDir = core.pref['Analyzer']['DataLocation']
        if not os.path.exists(baseDir):            
            QMessageBox(QMessageBox.Warning, 'Error', 'The data location:\n%s\nis inaccessible.' % baseDir,
                            QMessageBox.Ok).exec_()
            return
        
        if core.isRecordingData():
            core.stopDataRecorder()
        else:
            core.startDataRecorder()                
        
    @pyqtSlot()
    def onShowControlMenu(self):
        core = BioScopeCore.getInstance()
        if core.hasCamera():
            if core.isAcquiring():
                self.toggleLiveAction.setText('Stop')
            else:
                self.toggleLiveAction.setText('Live View')
                
    @pyqtSlot()
    def onShowAnalysisMenu(self):
        core = BioScopeCore.getInstance()
        if core.isRecordingData():
            self.dataRecorder.setChecked(True)
        else:
            self.dataRecorder.setChecked(False)
    
    def snapshot(self):
        core = BioScopeCore.getInstance()
        if core.hasCamera():
            if core.isAcquiring():
                QMessageBox(QMessageBox.Warning, 'Error', 'Camera is acquiring.',
                            QMessageBox.Ok).exec_()
                return                            
            core.snapshot()
        else:
            QMessageBox(QMessageBox.Warning, 'Error', 'Camera not exists.',
                            QMessageBox.Ok).exec_()
                            
    def toggleLive(self):
        core = BioScopeCore.getInstance()        
        if core.hasCamera():
            if core.isAcquiring():
                self.camCtrl.btnLive.setText('Live View')
                core.stopAcquisition()
            else:
                self.camCtrl.btnLive.setText('Stop')
                core.startAcquisition()
        else:
            QMessageBox(QMessageBox.Warning, 'Error', 'Camera not exists.',
                            QMessageBox.Ok).exec_()                
    
    def setRoi(self):
        self.__view.setRoi()
        
    def fullFrame(self):
        self.__view.fullRoi()
    
    @pyqtSlot()
    def calibrProgressStart(self):
        prog = QProgressBar()
        prog.setMinimum(0)
        prog.setMaximum(100)
        status = self.statusBar()
        status.addWidget(prog)
        status.progress = prog
        self.roiTable.btnCalibrate.setText('Stop')
    
    @pyqtSlot(float)
    def calibrProgress(self, value):
        prog = self.statusBar().progress
        prog.setValue(int(value * 100))
        
    @pyqtSlot()
    def calibrProgressEnd(self):
        status = self.statusBar()
        status.removeWidget(status.progress)
        status.progress = None
        self.roiTable.btnCalibrate.setText('Calibrate')
        
    def onClamp(self, roiId):
        core = BioScopeCore.getInstance()
        if core.isClamping():
            self.roiTable.setClampBtnText('Start Clamp')
            core.stopClamper()
        else:
            self.roiTable.setClampBtnText('Stop Clamp')
            core.startClamper(roiId)
        
    @pyqtSlot(object)
    def showMessage(self, msg):
        self.statusBar().showMessage(msg, 3000)
    
    @pyqtSlot(object)
    def plotCalibrInfo(self, info):
        # The first item
        roiId = info.keys().__iter__().next()
        data = info[roiId]
        x = numpy.array(tuple(v[0] for v in data))
        y = numpy.array(tuple(v[1] for v in data))
        z = numpy.array(tuple(v[2] for v in data))
        ovx = numpy.array(tuple(v[3] for v in data))
        ovy = numpy.array(tuple(v[4] for v in data))
        ovz = numpy.array(tuple(v[5] for v in data))
        crdx = numpy.array(tuple(v[6] for v in data))
        crdy = numpy.array(tuple(v[7] for v in data))
        scorz = numpy.array(tuple(v[8] for v in data))
#        px = np.polyfit(x, crdx, 1)
#        py = np.polyfit(y, crdy, 1)
#        pz = np.polyfit(z, scorz, 1)

#        dlg = PlotDialog(roiId, ((ovx, crdx, ovy, crdy, ovz, scorz),))
        dlg = PlotDialog(roiId, ((x, crdx, y, crdy, z, scorz),))
        self.app.calibrPlotDialog = dlg
        dlg.show()
    
    @pyqtSlot(object, float)
    def onFrameReady(self, imageData, level):
        ts = time.clock()
        self.__fpsQueue.append(ts)
        if ts - self.lastUpdate < 0.1:
            return
        self.lastUpdate = ts
        
        cnt = len(self.__fpsQueue)
        if cnt <= 1:
            return
        fps = cnt / (self.__fpsQueue[cnt - 1] - self.__fpsQueue[0])
        lbl = self.statusBar().fps
        lbl.setText('FPS: %.1f' % fps)
        self.camCtrl.showBufferLevel(level)
    
    @pyqtSlot(tuple)
    def onUpdateImageInfo(self, data):
        pos = data[0]
        value = data[1]
        lbl = self.statusBar().coord
        if pos is None and value is None:
            lbl.setText('')
        else:
            lbl.setText('X=%d, Y=%d, I=%s' % (pos[0], pos[1], value))
    
    @pyqtSlot(int)
    def onAcqStarted(self, frameCount):
        core = BioScopeCore.getInstance()
        if core.isAcquiring():
            box = QMessageBox(QMessageBox.Warning, 'Error', 'Camera is acquiring',
                            QMessageBox.Ok)
            box.exec_()
            return
        core.startAcquisition(frameCount)
        
    @pyqtSlot()
    def onAcqAborted(self):
        core = BioScopeCore.getInstance()
        core.stopAcquisition()
        
    @pyqtSlot()
    def calibrate(self):        
        core = BioScopeCore.getInstance()
        if core.isAcquiring():
            core.stopAcquisition()
            BioScopeMainWindow.getInstance().camCtrl.btnLive.setText('Live View')
        if core.isRecordingData():
            core.stopDataRecorder()
        BioScopeCore.getInstance().calibrate()
        
    def createDockWindows(self):
        core = BioScopeCore.getInstance()
        self.__docks = {}
        
        widget = RoiListDockWidget()
        dock = QDockWidget()
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setWidget(widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.roiTable = widget
        self.__docks['RoiListDock'] = dock
        
        if core.hasCamera():
            widget = CamCtrlDockWidget()
            self.connect(widget, SIGNAL('onQuit()'), self.app.quit)
            dock = QDockWidget()
            dock.setAllowedAreas(Qt.LeftDockWidgetArea | 
                                 Qt.RightDockWidgetArea)
            dock.setWidget(widget)
            dock.setWindowTitle(core.getCam().deviceName)
            self.addDockWidget(Qt.LeftDockWidgetArea, dock)
            self.camCtrl = widget
            self.__docks['CamCtrlDock'] = dock
        
        if core.hasStage():
            widget = StageCtrlDockWidget()
            dock = QDockWidget()
            dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            dock.setWidget(widget)
            dock.setWindowTitle('PI Stage')
            self.addDockWidget(Qt.LeftDockWidgetArea, dock)
            self.__docks['StageCtrlDock'] = dock
        
    def __setRoi(self):
        if self.__pixmapItem is not None:
            roi = self.__pixmapItem.roi            
            if roi is None:
                return
            
            logging.info('Setting roi: %s' % roi)
            self.__cam.roi = roi
            
    def __restoreRoi(self):
        self.__cam.restoreRoi()
        
    def takeBackground(self):
        core = BioScopeCore.getInstance()
        if core.isAcquiring():
            core.stopAcquisition()
            self.camCtrl.btnLive.setText('Live View')
        core.takeBackground()
    
    def removeBackground(self):
        BioScopeCore.getInstance().removeBackground()  
    def __genColorSpace(self):
        # Jet
        table = []
        for i in xrange(256):
            rgb = colorsys.hls_to_rgb(i / 256.0, 0.5, 0.75)
            entry = tuple(255 - int(i * 256) for i in rgb)
#            table.append(qRgb(*entry))
            table.append(qRgb(i, i * 0.4, 0))
        
        self.__colorTable = {}
        self.__colorTable['Jet'] = table
        
        # Gray
        self.__colorTable['Gray'] = []
        
    def __isStageAlive(self, alive):
##        logging.info('Stage status: %s' % alive)
#        if alive:
#            self.statusBar().showMessage('Connected to PI stage.', 5000)
#        else:
#            self.statusBar().showMessage("Unable to connect to PI stage.", 5000)
        pass
        
    def __acqFinished(self):
        dlg = QMessageBox(QMessageBox.Information, 'Finished',
                               'Acquisition finished.', QMessageBox.Ok, self)
        dlg.exec_()
        self.__isLive = False
        
    def __toggleGosseProc(self):
        '''
        Enable/disable the Gosse processing procedure in live view
        '''
        self.__gosseEnabled = not self.__gosseEnabled
        logging.debug('Gosse processing %s' % ('enabled' if self.__gosseEnabled else 'disabled'))
        
    def __gosse(self, data):
        return (15, 14)
        
    def prefDlg(self):
        '''
        Shwo the preferences dialog
        '''
        dlg = PrefDialog()
        dlg.exec_()
        
    def aboutDlg(self):
        '''
        Show the Help->About dialog
        '''
        logging.debug('About dialog opened')
        
    def __createAction(self, text, slot=None, shortcut=None, icon=None, \
                     tip=None, checkable=False, signal="triggered()"):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon(":/%s.png" % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.triggered.connect(slot)
#            self.connect(action, SIGNAL(signal), slot)
        if checkable:
            action.setCheckable(True)
        return action

#class client(object):
#    def __init__(self):
#        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#        sock.settimeout(1)
#        sock.connect(('127.0.0.1', 8182))
#        self.__sock = sock
#        
#        # Pulse
#        for i in range(1):
#            self.toConn(sock, 1, 1, None)
#            result = self.fromConn(sock)
#            self.__logData(result)
#            
#        for i in range(2):
#            extraData = struct.pack('>2H', i, i * 2)
#            self.toConn(sock, 1, 2, extraData)
#            result = self.fromConn(sock)
#            self.__logData(result)
#        
#        
#        
#    def __logData(self, result):
#        devId = result['DevId']
#        funcId = result['FuncId']
#        extraLen = result['ExtraLen']
#        extraData = result['ExtraData']
#        if extraData is None:
#            extraString = ''
#        else:
#            extraString = self.strToHex(extraData)
#        
#        logging.info('Client: DevId: %d, FuncId: %d, ExtraLen: %d, Extra: %s' % \
#                     (devId, funcId, extraLen, extraString))
#        
#    def strToHex(self, data):
#        return ' '.join('0x%x' % ord(i) for i in data)
#        
#    def fromConn(self, conn):
#        '''
#        According to MODBUS, parse inputs from the connection
#        
#        Return: {'DevId':X, 'FuncId':X, 'ExtraLen':X, 'ExtraData':X}
#        
#        Modbus: DevId(1) FuncId(1) ExtraLen(2) ExtraData(ExtraLen)
#        '''
#        try:
#            data = conn.recv(4)
#            if len(data) != 4:
#                # Discard
#                return None
#            
#            devId, funcId = tuple(ord(i) for i in data[:2])
#            extraLen, = struct.unpack('>H', data[2:])
#            extraData = None
#            if extraLen != 0:
#                # Extra data must be retrieved
#                bytesLeft = extraLen
#                extraData = ''
#                while bytesLeft > 0:
#                    tmp = conn.recv(bytesLeft)
#                    extraData += tmp
#                    bytesLeft -= len(tmp)
#            
#            return {'DevId':devId, 'FuncId':funcId, \
#                    'ExtraLen':extraLen, 'ExtraData':extraData}
#        except:
#            return None
#        
#    def toConn(self, conn, devId, funcId, extraData=None):
#        '''
#        According to MODBUS, output to connection
#        
#        Modbus: DevId(1) FuncId(1) ExtraLen(2) ExtraData(ExtraLen)        
#        '''
#        data = ''.join(chr(i) for i in (devId, funcId))
#        if extraData is not None:
#            extraLen = struct.pack('>H', len(extraData))
#            data = ''.join((data, extraLen, extraData))
#        else:
#            extraLen = struct.pack('>H', 0)
#            data += extraLen            
#        
#        conn.send(data)
#                         
#    def process(self, conn, funcId, extraData):
#        if funcId == 1:
#            # Pulse
#            self.toConn(conn, 0, funcId)
#        elif funcId == 2:
#            # Add
#            n1, n2 = struct.unpack('>2H', extraData)
#            extraData = struct.pack('>i', n1 + n2)
#            self.toConn(conn, 0, funcId, extraData)    

class BioScopeScene(QGraphicsScene):
    '''
    Scene class, can remove rois
    '''
    def __init__(self, parent=None):
        super(BioScopeScene, self).__init__(parent)
        self.setBackgroundBrush(QBrush(Qt.black))
        self.__pixmapItem = None
        self.tmpRoi = None
        self.roiMap = {}
        self.lastUpdate = time.clock()
        self.camRoi = (0, 0, 0, 0)
        
    def setSelectedRoi(self, roiIdList):
        '''
        Set the rois to selected status
        '''
        map(lambda roiId:self.roiMap[roiId].setSelected(False), self.roiMap.keys())
        map(lambda roiId:self.roiMap[roiId].setSelected(True), roiIdList)
        
    def removeTmpRoi(self):
        # Remove the tmpRoi
        if self.tmpRoi is not None:
            self.removeItem(self.tmpRoi)
            self.tmpRoi = None
            
    def addToAnalysis(self):
        '''
        Add the tmpRoi to the roiMap
        '''
        roiId = int(time.time() * 10)
        roi = BioScopeRoiItem(self.tmpRoi.boundingRect(), 'Analysis', self.__pixmapItem)
        roi.setFlags(QGraphicsItem.ItemIsSelectable)
        roi.roiId = roiId
        self.connect(roi.actions['Remove'], SIGNAL('triggered()'),
                             lambda : self.removeFromAnalysis(roiId))
        self.roiMap[roiId] = roi
        # Remove the tmpRoi
        self.removeTmpRoi()
        rc = tuple(map(lambda v:int(v), roi.boundingRect().getRect()))
        BioScopeCore.getInstance().addToAnalysis(roiId, rc)
        rc = list(rc)
        rc[0] += self.camRoi[0]
        rc[1] += self.camRoi[1]
        self.views()[0].sig_BioScopeView_AddToAnalysis.emit((roiId, tuple(rc)))
        
    def removeFromAnalysis(self, roiId):
        roiGroup = self.roiMap[roiId]
        self.roiMap.pop(roiId)
        self.removeItem(roiGroup)
        BioScopeCore.getInstance().removeFromAnalysis(roiId)
        self.views()[0].sig_BioScopeView_RemoveFromAnalysis.emit(roiId)
        
    def updateRoi(self, data):
        roiId, delta = data
        roiItem = self.roiMap[roiId]
        roiItem.moveBy(delta[0], delta[1])
            
    def clearAll(self):
        '''
        Clear all the items
        '''
        self.removeTmpRoi()
        map(self.removeFromAnalysis, self.roiMap.keys())
        self.removeItem(self.__pixmapItem)        
        self.__pixmapItem = None
        self.clear()
    
    @pyqtSlot()
    def setRoi(self):
        '''
        Set the camera ROI to __tmpRoi
        '''
        if self.tmpRoi is None:
            QMessageBox(QMessageBox.Warning, 'Error', 'Please specify the ROI first.', QMessageBox.Ok).exec_()
            return
        
        core = BioScopeCore.getInstance()
        resume = False
        if core.isAcquiring():
            core.stopAcquisition()
            resume = True
        rc = self.tmpRoi.rect()
        # scan line alignment
        rc.adjust(rc.left() % 2, rc.top() % 2, 0, 0)
        rc.adjust(0, 0, -rc.width() % 4, -rc.height() % 2)
        rc = map(lambda v:int(v), (rc.left(), rc.top(), rc.width(), rc.height()))
        rc[0] += self.camRoi[0]
        rc[1] += self.camRoi[1]
        core.setRoi(rc)
        self.clearAll()
        mainWnd = BioScopeMainWindow.getInstance()
        if resume:
            core.startAcquisition()
            mainWnd.camCtrl.btnLive.setText('Stop')
        else:
            core.snapshot()
            mainWnd.camCtrl.btnLive.setText('Live View')
    
    @pyqtSlot()
    def fullRoi(self):
        '''
        Set the camera ROI to full
        '''
        core = BioScopeCore.getInstance()
        resume = False
        if core.isAcquiring():
            core.stopAcquisition()
            resume = True
        core.fullRoi()
        self.clearAll()
        mainWnd = BioScopeMainWindow.getInstance()
        if resume:
            core.startAcquisition()
            mainWnd.camCtrl.btnLive.setText('Stop')
        else:
            core.snapshot()
            mainWnd.camCtrl.btnLive.setText('Live View')
        
    def draw(self, data):
        t = time.clock()
        if t - self.lastUpdate < 0.05:
            return
        self.lastUpdate = t
        rc = self.sceneRect()
                
        # The ROI on CCD chips
        mismatch = False
        if self.camRoi[2] != data['ROI'][2] or self.camRoi[3] != data['ROI'][3]:
            mismatch = True
            self.camRoi = data['ROI']
            self.clearAll()
        width = self.camRoi[2]
        height = self.camRoi[3]

        rawData = data['RawData']
        img = QImage(rawData, width, height, QImage.Format_Indexed8)
        pixmap = QPixmap.fromImage(img)
        pixRatio = BioScopeCore.getInstance().pref['Geometry']['PixelRatio']
        wscale = rc.width() / (width * pixRatio)
        hscale = rc.height() / height
        gscale = min(wscale, hscale)
        if self.__pixmapItem is None or mismatch:
            if wscale > hscale:
                # Translate horizontally
                xoffset = (rc.width() / (gscale * pixRatio) - width) / 2.0
                yoffset = 0
            elif wscale < hscale:
                xoffset = 0
                yoffset = (rc.height() / gscale - height) / 2.0
            else:
                xoffset = 0
                yoffset = 0
                
            self.__pixmapItem = BioScopePixmapItem()
            self.__pixmapItem.scale(gscale * pixRatio, gscale)
            self.__pixmapItem.translate(xoffset, yoffset)
            self.addItem(self.__pixmapItem)
            
#        self.__pixmapItem.resetTransform()
        self.__pixmapItem.setPixmap(pixmap)
        self.__pixmapItem.qimage = img
        
        def drawCenterMarker(resultItem):
            # Draw the guidelines
            core = BioScopeCore.getInstance()
            pref = core.pref['Analyzer']
            rInner = pref['InnerRadius']
            rOuter = pref['OuterRadius']
            halfCross = rInner / 3.0
            pen = QPen(Qt.red)
            
            roiId = resultItem[0]
            center = resultItem[1]
#            rc = tuple(map(lambda v:int(v), self.roiMap[roiId].boundingRect().getRect()))
            rc = self.roiMap[roiId].boundingRect()
            roi = self.roiMap[roiId]
            map(self.removeItem, roi.childItems())
            cx, cy = center[:2]
            cx += 0.5
            cy += 0.5
            cx -= roi.pos().x()
            cy -= roi.pos().y()
            lineh = QGraphicsLineItem(cx - halfCross, cy, cx + halfCross, cy, roi)
            lineh.setPen(pen)        
            linev = QGraphicsLineItem(cx, cy - halfCross, cx , cy + halfCross, roi)
            linev.setPen(pen)
            inner = QGraphicsEllipseItem(cx - rInner / pixRatio, cy - rInner, 2 * rInner / pixRatio, 2 * rInner, roi)
            inner.setPen(pen)
            outer = QGraphicsEllipseItem(cx - rOuter / pixRatio, cy - rOuter, 2 * rOuter / pixRatio, 2 * rOuter, roi)
            outer.setPen(pen)
            # Draw the text
            cx, cy, cz = center
            if len(resultItem) == 2:
                # no calibration data
                msg = '(%.2f, %.2f, %.4f)' % (cx + self.camRoi[0], cy + self.camRoi[1], cz)
            else:
                # with calibrated coordinates
                pR = resultItem[2]
                msg = '(%.4f, %.4f, %.4f)' % pR
                if len(resultItem) == 4:
                    # with forces
                    forces = resultItem[3]
                    msg = '(%.4f, %.4f, %.4f, Fx=%f, Fy=%f)' % (pR + forces)
                
#            if coeff is None:
#                # No calibration data, we'll directly display the pixel and score values
#            else:
#                # Try to calculate the 'real' coordinate in microns
#                px, py, pz, original = coeff
#                dd = pz[1] ** 2 - 4 * pz[0] * (pz[2] - cz)
#                posz1 = -(pz[1] + math.sqrt(dd)) / (2 * pz[0])
#                posz2 = -(pz[1] - math.sqrt(dd)) / (2 * pz[0])
#                oz = original[2]
#                posz = posz1 if abs(posz1 - oz) < abs(posz2 - oz) else posz2                
#                msg = '(%.4f, %.4f, %.4f, Fx=%f, Fy=%f)' % \
#                    ((cx - px[1]) / px[0], (cy - py[1]) / py[0], posz,) 
            textItem = QGraphicsTextItem(msg, roi)
            font = QFont('Arial')
            textItem.setFont(font)
            textItem.setDefaultTextColor(Qt.red)
            textItem.setScale(1 / gscale)
            textItem.translate(cx + rOuter, cy + rOuter)
            
        gr = data['GosseResult']
        if gr is not None:
            map(drawCenterMarker, gr)
#        try:
#        except:
#            pass

class BioScopeView(QGraphicsView):
    '''
    Custom class for the view. Reimplement the keyboard
    events handler, which can delete rois
    
    Signals: sig_Scene_BroadcastInfo((pos, value)), sig_BioScopeView_AddToAnalysis((roiId, roiRc))
    Slots: onFrameReady, setSelectedRoi
    '''
    sig_Scene_BroadcastInfo = pyqtSignal(tuple)
    sig_BioScopeView_AddToAnalysis = pyqtSignal(tuple)
    sig_BioScopeView_RemoveFromAnalysis = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super(BioScopeView, self).__init__(parent)
        self.setScene(BioScopeScene())
    
    def broadcastInfo(self, pos, value):
        self.sig_Scene_BroadcastInfo.emit((pos, value))

    def setRoi(self):
        self.scene().setRoi()
        
    def fullRoi(self):
        self.scene().fullRoi()
        
    @pyqtSlot(object)
    def updateRoi(self, data):
        self.scene().updateRoi(data)
        
    def keyPressEvent(self, event):
        '''
        Handle the deletion
        '''
        # Remove the selected
        if event.key() == Qt.Key_Delete:
            def func(item):
                if item.roiType == 'Temp':
                    self.scene().removeTmpRoi()
                elif item.roiType == 'Analysis':
                    self.scene().removeFromAnalysis(item.roiId)
            map(func, self.scene().selectedItems())
                        
    @pyqtSlot(object, float)
    def onFrameReady(self, imageData, level):
        self.scene().draw(imageData)
        
    @pyqtSlot(tuple)
    def setSelectedRoi(self, roiIdList):
        '''
        Set the rois to selected status
        '''
        self.scene().setSelectedRoi(roiIdList)
                        
    def resizeEvent(self, event):
        sz = event.size()
        w = sz.width()
        w = w if w % 2 == 0 else w - 1
        h = sz.height()
        h = w if h % 2 == 0 else h - 1
        rc = QRectF(0, 0, w, h)
        self.scene().setSceneRect(rc)
    
def main(argv):
    app = QApplication(argv)
    
    login = LoginDialog()
    if login.exec_() == QDialog.Rejected:
        return
    
    app.core = BioScopeCore(login.user)
    mainWindow = BioScopeMainWindow(app)
    mainWindow.setWindowTitle('Bioscope - %s' % login.user)
    mainWindow.show()
    
    app.exec_()
    
    app.core.cleanUp()
    app.exit()
    
def analysis():
    p = pstats.Stats('Bioscope_profiler')
    p.strip_dirs().sort_stats('time').print_stats(20)
    
if __name__ == '__main__':
    main(sys.argv)
#    cProfile.run('main(sys.argv)', 'Bioscope_profiler')
#    analysis()
