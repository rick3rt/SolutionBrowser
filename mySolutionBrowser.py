'''
GUI to explore simulation results

Rick Waasdorp, 29-07-2019
v1.2 (not really consistent in updating)
'''

from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QPushButton, QSizePolicy, QComboBox, QSpacerItem, QSlider, QStyle,
                             QToolButton, QVBoxLayout, QWidget, QMainWindow, QMenu, QAction, QLabel, QMessageBox, QScrollArea, QFileDialog, QTextBrowser, QShortcut)
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QFont, QKeySequence, QIcon
from PyQt5.QtCore import QDir, Qt, QSize
from math import floor, ceil
from MatFileLoader import MatFileLoader
from time import sleep
import os
import time
import configparser
import pandas as pd
import numpy as np
try:
    from ahk import AHK
except ImportError:
    AHK = None


class JumpSlider(QSlider):
    def mousePressEvent(self, ev):
        """ Jump to click position """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width()))

    def mouseMoveEvent(self, ev):
        """ Jump to pointer position while moving """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width()))


class CtrlButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super(CtrlButton, self).__init__(*args, **kwargs)
        self.__isCtrlPressed = False
        # self.clicked.connect(self.handleClick)

    def keyPressEvent(self, event):
        super(CtrlButton, self).keyPressEvent(event)
        self._processKeyEvent(event)

    def keyReleaseEvent(self, event):
        super(CtrlButton, self).keyReleaseEvent(event)
        self._processKeyEvent(event)

    def _processKeyEvent(self, event):
        isCtrl = event.modifiers() & Qt.ControlModifier
        self.__isCtrlPressed = bool(isCtrl)

    def handleClick(self):
        print("Ctrl pressed?", self.__isCtrlPressed)

    def isCtrlPressed(self):
        isCtrlPressedBool = self.__isCtrlPressed
        # self.__isCtrlPressed = False
        return isCtrlPressedBool


class SolutionBrowser(QMainWindow):
    def __init__(self, setToLoad=None):
        super(SolutionBrowser, self).__init__()

        # parse config
        self.parse_config()

        # overwrite default set if provided
        if setToLoad:
            self.default_set = setToLoad

        # set size mainwindow
        self.setWindowTitle('Solution Browser')
        self.resize(self.hsize, self.vsize)
        if self.isStartMaximized:
            self.setWindowState(Qt.WindowMaximized)
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

        # icon
        app_icon = QIcon()
        app_icon.addFile(os.path.join('icons', 'icon256.png'), QSize(256, 256))
        app_icon.addFile(os.path.join('icons', 'icon128.png'), QSize(128, 128))
        self.setWindowIcon(app_icon)

        # statusbar
        self.statusbar = self.statusBar()
        self.statusbar_style_alert = "QStatusBar{font-size:10pt;background:rgba(250, 128, 114, 1);color:black;font-weight:bold;}"
        self.statusbar_style_normal = "QStatusBar{font-size:10pt;color:black;font-weight:bold;}"
        self.statusbar.setStyleSheet(self.statusbar_style_normal)
        self.statusbar.showMessage('Starting SolutionBrowser')

        # load layout top and bottom frames
        self.layouts = SolutionBrowserLayout(self)
        self.setCentralWidget(self.layouts)

        self.createActions()
        self.createMenus()

        # create par dialog
        self.parDialogOpen = False
        self.parDialog = ParDialog(self)

        # get frames for easy reference.
        self.ImageViewerFrame = self.layouts.ImageViewerFrame
        self.ParameterFrame = self.layouts.ParameterFrame
        self.ParameterFrame.setFont(font)

        # start image viewer
        self.setup_image_viewer()
        # load default image
        self.open_image('default.jpg')

        # start parameter selection tool
        self.setup_parameter_selector()

        # ahk to communicate with matlab
        if AHK:
            self.ahk = AHK(executable_path=self.ahk_executable_path)

    def resizeEvent(self, event):
        self.fitToWindow(True)

    def setup_image_viewer(self):
        self.scaleFactor = 0.0
        self.reuseScaleFactor = None

        self.imageLabel = QLabel(self.ImageViewerFrame)
        self.imageLabel.setBackgroundRole(QPalette.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.imageLabel.setScaledContents(True)

        self.scrollArea = QScrollArea(self.ImageViewerFrame)
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.imageLabel)

        layout = QHBoxLayout()
        layout.addWidget(self.scrollArea)  # do not add image label
        layout.setContentsMargins(1, 1, 1, 1)
        self.ImageViewerFrame.setLayout(layout)

    def setup_parameter_selector(self):
        if self.default_set:
            self.open_batch(batchFolder=self.default_set)
        else:
            self.open_batch()
        # init h layout
        layout = QHBoxLayout()

        # create the groups
        self.parFrames = []
        self.parLabels = []
        self.parBoxes = []
        self.parSliders = []
        self.valIndices = []

        # create parameter selection boxes (i.e. slider groups)
        for idx, name, values in zip(range(len(self.parNames)), self.parNames, self.uniqueVals):
            frame, label, valueBox, slider, valIdx = self.createSliderGroup(idx, name, values)
            self.parFrames.append(frame)
            self.parLabels.append(label)
            self.parBoxes.append(valueBox)
            self.parSliders.append(slider)
            self.valIndices.append(valIdx)
            layout.addWidget(frame)

        # create overview section.
        ov_frame, simnum_label = self.createOverviewGroup()
        self.simnumLabel = simnum_label
        layout.addWidget(ov_frame)

        layout.setContentsMargins(1, 1, 1, 1)
        self.ParameterFrame.setLayout(layout)

        # call to fix sim number
        self.updateImage()
        self.updateOverviewGroup()

    def createOverviewGroup(self):
        # init frame and layout
        frame = QFrame(self.ParameterFrame)
        grid_layout = QGridLayout()
        frame.setLayout(grid_layout)

        # set simnum if not yet availble
        if not hasattr(self, 'simNum'):
            self.simNum = 000

        if not hasattr(self, 'simImgPath'):
            self.simImgPath = 'null'

        # create sim num label
        simnum_label = QLabel(frame)
        simnum_label.setText('Sim num: %03i' % self.simNum)
        simnum_label.setStyleSheet("QLabel{color:darkblue;font-weight:bold;}")

        # create prev and next button
        prev_but = CtrlButton(frame)
        next_but = CtrlButton(frame)

        prev_but.setIcon(self.style().standardIcon(getattr(QStyle, "SP_MediaSeekBackward")))
        next_but.setIcon(self.style().standardIcon(getattr(QStyle, "SP_MediaSeekForward")))

        prev_but.clicked.connect(self.callUpdateImageDown)
        next_but.clicked.connect(self.callUpdateImageUp)

        # load to matlab
        load_but = QPushButton(frame)
        load_but.setText('Load in Matlab')
        load_but.clicked.connect(self.loadInMatlab)

        # view gif
        view_gif_but = QPushButton(frame)
        view_gif_but.setText('View gif')
        view_gif_but.clicked.connect(self.viewGif)

        # view parameters
        par_but = QPushButton('Parameters', frame)
        par_but.clicked.connect(self.viewParameters)

        # add things layout
        grid_layout.addWidget(simnum_label, 0, 0, 1, 1)
        grid_layout.addWidget(par_but, 0, 1, 1, 1)
        grid_layout.addWidget(prev_but, 1, 0, 1, 1)
        grid_layout.addWidget(next_but, 1, 1, 1, 1)
        grid_layout.addWidget(load_but, 2, 0, 1, 1)
        grid_layout.addWidget(view_gif_but, 2, 1, 1, 1)

        return frame, simnum_label

    def callUpdateImageUp(self):
        sender = self.sender()
        inc = 1
        if isinstance(sender, CtrlButton):
            if sender.isCtrlPressed():
                inc = 10

        if self.simNum <= self.totalNumSims - inc:
            self.simNum += inc
            self.updateImage(self.simNum)
            self.updateSliders()
        else:
            self.statusbar.showMessage('Last simulation reached')
            self.statusbar.setStyleSheet(self.statusbar_style_alert)

    def callUpdateImageDown(self):
        sender = self.sender()
        inc = 1
        if isinstance(sender, CtrlButton):
            if sender.isCtrlPressed():
                inc = 10

        if self.simNum >= inc + 1:
            self.simNum -= inc
            self.updateImage(self.simNum)
            self.updateSliders()
        else:
            self.statusbar.showMessage('First simulation reached')
            self.statusbar.setStyleSheet(self.statusbar_style_alert)

    def updateOverviewGroup(self):
        # update simnum label
        self.simnumLabel.setText('Sim num: %03i' % self.simNum)
        # update statusbar
        self.statusbar.setStyleSheet(self.statusbar_style_normal)
        self.statusbar.showMessage('Simulation %03i loaded: %s' % (self.simNum, self.simImgPath))

        # if parDialog open, update it
        if self.parDialogOpen:
            text = self.getParameterText()
            self.parDialog.updateText(text)

    def loadInMatlab(self):
        # get the name of the current file
        row_idx = self.simNum - 1
        matFileName = self.parData['matFile'].iloc[row_idx]

        # open matlab. Expects ahk script to be running on system.
        # script maps ctrl + m to open matlab command window
        if hasattr(self, 'ahk'):
            self.ahk.send('^m')
            sleep(0.100)  # short delay
            self.ahk.type('clear;load(\'' + matFileName + '\');')
            self.ahk.send('{Enter}')
        else:
            self.statusbar.showMessage(
                'AHK not found! Could not import AHK, make sure it is installed.')

    def viewParameters(self):
        if not self.parDialogOpen:
            # create new window
            self.parDialogOpen = True
            self.parDialog.show()
            # put in the text
            text = self.getParameterText()
            self.parDialog.updateText(text)
        else:
            self.parDialog.close()

    def viewGif(self):
        # get the name of the current file
        row_idx = self.simNum - 1
        gifFileName = self.parData['gifFile'].iloc[row_idx]

        # check if file exist:
        if os.path.isfile(gifFileName):
            os.startfile(gifFileName, 'open')
        else:
            self.statusbar.showMessage('GIF does not exist for %03i...' % self.simNum)
            self.statusbar.setStyleSheet(self.statusbar_style_alert)

    def createSliderGroup(self, idx, parameterName, parameterValues):
        # init frame and layout
        frame = QFrame(self.ParameterFrame)
        grid_layout = QGridLayout()
        frame.setLayout(grid_layout)

        # callback functions TEST
        def sliderChange():
            self.valChange(idx, parameterName, 'slider')

        def boxChange():
            self.valChange(idx, parameterName, 'box')

        # fill in grid
        label = QLabel(frame)
        label.setText(parameterName)

        valIdx = floor((len(parameterValues) - 1) / 2)

        valueBox = QComboBox(frame)
        valueBox.addItems([str(x) for x in parameterValues])
        valueBox.setCurrentIndex(valIdx)
        valueBox.currentIndexChanged.connect(boxChange)

        slider = JumpSlider(Qt.Horizontal)
        slider.setRange(0, len(parameterValues) - 1)
        slider.setValue(valIdx)
        slider.setTickPosition(QSlider.TicksBothSides)
        slider.setTickInterval(1)
        slider.setSingleStep(1)
        slider.valueChanged.connect(sliderChange)

        grid_layout.addWidget(label, 0, 0, 1, 1)
        grid_layout.addWidget(valueBox, 0, 1, 1, 1)
        grid_layout.addWidget(slider, 1, 0, 2, 2)

        return frame, label, valueBox, slider, valIdx

    def valChange(self, parIdx, parName, source):
        if source == 'slider':
            valueIdx = self.parSliders[parIdx].value()
            self.parBoxes[parIdx].setCurrentIndex(valueIdx)

        elif source == 'box':
            valueIdx = self.parBoxes[parIdx].currentIndex()
            self.parSliders[parIdx].setValue(valueIdx)

        self.valIndices[parIdx] = valueIdx

        # only update image once (box is called when slider is changed and vice versa.)
        if source == 'slider':
            self.updateImage()

    def updateSliders(self):
        # get par values based on row idx
        row_idx = self.simNum - 1
        data_row = self.parData.iloc[row_idx]

        # need to determine parameter unique value valIndex based on sim number
        # get values based on index
        for idx, name in enumerate(self.parNames):
            value = self.parData[name].iloc[row_idx]
            result = np.where(self.uniqueVals[idx] == value)
            self.valIndices[idx] = int(result[0])

        # update sliders
        for parIdx, valIdx in enumerate(self.valIndices):
            self.parSliders[parIdx].setValue(valIdx)

    def updateImage(self, simNum=None):
        # if sim num provided skip first section
        if not simNum:
            # get values based on index
            parValues = [None] * len(self.valIndices)
            for idx, val in enumerate(self.valIndices):
                parValues[idx] = self.uniqueVals[idx][val]

            # select the right row:
            criteria_list = []
            for idx, name in enumerate(self.parNames):
                df = self.parData[name] == parValues[idx]
                criteria_list.append(df.values)

            critArray = np.array(criteria_list).transpose()
            row = critArray.all(axis=1)
            row_idx = self.parData[pd.Series(row)].index[0]
            simNum = row_idx + 1
        else:
            row_idx = simNum - 1
        imgFileName = self.parData['imgFile'].iloc[row_idx]
        # set the simNum
        self.simNum = simNum
        self.simImgPath = imgFileName
        # update the label with the new simNim
        self.updateOverviewGroup()

        # open the image
        self.open_image(imgFileName)

    def open_batch(self, batchFolder=None):
        # open folder browser
        baseFolder = self.base_folder
        if not batchFolder:
            batchFolder = QFileDialog.getExistingDirectory(self, "Open Directory", baseFolder)
        else:
            batchFolder = os.path.join(baseFolder, batchFolder)

        if batchFolder:
            # get simulation name
            fc = os.listdir(batchFolder)
            fc = [f for f in fc if 'parlist' not in f and 'params' not in f]
            fc = [f.split('_')[0] for f in fc if '_' in f]
            simulationName = list(set(fc))
            if len(simulationName) > 1:
                raise('ERROR, could not determine simulation name')
            else:
                simulationName = simulationName[0]

            # read csv as dataframe:
            self.parData = pd.read_csv(os.path.join(batchFolder, self.parlist_filename))
            self.totalNumSims = self.parData.shape[0]
            # get parameter names:
            parNames = list(self.parData.columns)
            parNames.remove('SimNum')
            self.parNames = parNames

            # get unique values per paramter
            uniqueVals = []
            for par in parNames:
                uniqueVals.append(self.parData[par].unique())
            self.uniqueVals = uniqueVals

            # add file locations to data frame
            fImgNameBase = '{0}_{1}\\fig\\overview_{0}_{1}.png'.format(simulationName, '%03i')
            fMatNameBase = '{0}_{1}\\{0}_{1}_workspace.mat'.format(simulationName, '%03i')
            fGifNameBase = '{0}_{1}\\fig\\fiber_radius_{0}_{1}.gif'.format(
                simulationName, '%03i')  # fiber_radius_M500_078

            imgFiles = []
            matFiles = []
            gifFiles = []
            for num in list(self.parData['SimNum']):
                imgFiles.append(os.path.join(batchFolder, fImgNameBase % (num, num)))
                matFiles.append(os.path.join(batchFolder, fMatNameBase % (num, num)))
                gifFiles.append(os.path.join(batchFolder, fGifNameBase % (num, num)))

            self.parData['imgFile'] = imgFiles
            self.parData['matFile'] = matFiles
            self.parData['gifFile'] = gifFiles

    def getParameterText(self):
        # load matfile
        row_idx = self.simNum - 1
        matFilePath = self.parData['matFile'].iloc[row_idx]
        try:
            mat = MatFileLoader.loadmat(matFilePath, variable_names=['P'])
        except FileNotFoundError:
            mat = None

        if mat:
            # get parameters and format as strings
            P = mat['P']  # dict for struct P
            # TODO: delete some less meaningful parameters:
            keys_to_delete = ['']

            # make text list
            text_list = []
            str_lengths = np.zeros((len(P), 2))
            for idx, (key, value) in enumerate(P.items()):
                if isinstance(value, np.ndarray):
                    if value.size == 0:
                        value = None
                if value:
                    if value < 0:
                        value = '%.3e' % value
                    elif value >= 0:
                        value = ' %.3e' % value  # space for - sign alignment
                else:
                    value = ''
                text_list.append([key, value])
                str_lengths[idx, 0] = len(key)
                str_lengths[idx, 1] = len(value)

            # find pad length
            pad_col1 = int(str_lengths[:, 0].max()) + 2
            pad_col2 = int(str_lengths[:, 1].max()) + 2

            text = ''
            for t in text_list:
                name = t[0].rjust(pad_col1)
                value = t[1].ljust(pad_col2)
                text += name + '\t:\t' + value + '\n'
            return text
        else:
            return 'mat file not found... :('

    def open_image(self, fileName=None):
        if not fileName:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())
        else:
            image = QImage(fileName)
            if image.isNull():
                self.statusbar.showMessage('Failed to load %03i: %s' %
                                           (self.simNum, self.simImgPath))
                self.statusbar.setStyleSheet(self.statusbar_style_alert)
                return

            self.imageLabel.setPixmap(QPixmap.fromImage(image))

            self.fitToWindowAct.setEnabled(True)
            self.updateActions()

            if not self.fitToWindowAct.isChecked():
                self.imageLabel.adjustSize()

            if self.reuseScaleFactor:
                self.scaleFactor = self.reuseScaleFactor
                self.scaleImage(self.scaleFactor, isAbsolute=True)
            else:
                self.scaleFactor = 1.0

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.imageLabel.adjustSize()
        self.scaleFactor = 1.0

    def fitToWindow(self, isResizeEvent=False):
        fitToWindow = self.fitToWindowAct.isChecked()
        if fitToWindow:
            # reset image size
            self.normalSize()
            # keep aspect ratio...
            image_size = self.imageLabel.pixmap().size()
            area_size = self.scrollArea.viewport().size()
            f_width = area_size.width() / image_size.width()
            f_height = area_size.height() / image_size.height()
            new_factor = min((f_width, f_height))
            self.scaleImage(new_factor)
            self.reuseScaleFactor = new_factor

        # if not isResizeEvent:
        #     self.normalSize()
        self.updateActions()

    def createActions(self):
        self.openAct = QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open_image)
        self.openBatchAct = QAction("&Open Batch...", self,
                                    shortcut="Ctrl+B", triggered=self.open_batch)
        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)
        self.zoomInAct = QAction("Zoom &In (25%)", self, shortcut="Ctrl+=",
                                 enabled=False, triggered=self.zoomIn)
        self.zoomOutAct = QAction("Zoom &Out (25%)", self, shortcut="Ctrl+-",
                                  enabled=False, triggered=self.zoomOut)
        self.normalSizeAct = QAction("&Normal Size", self, shortcut="Ctrl+S",
                                     enabled=False, triggered=self.normalSize)
        self.fitToWindowAct = QAction("&Fit to Window", self, enabled=False,
                                      checkable=True, shortcut="Ctrl+F", triggered=self.fitToWindow)
        self.openParAct = QAction("&View Parameters", self,
                                  shortcut="Ctrl+p", triggered=self.viewParameters)

        self.closeWindow = QShortcut(QKeySequence("Ctrl+W"), self)
        self.closeWindow.activated.connect(self.close)

        self.nextShortcut = QShortcut(QKeySequence("Right"), self)
        self.prevShortcut = QShortcut(QKeySequence("Left"), self)
        self.nextShortcut.activated.connect(self.callUpdateImageUp)
        self.prevShortcut.activated.connect(self.callUpdateImageDown)

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openBatchAct)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.openParAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)

        self.helpMenu = QMenu("&Help", self)
        # self.helpMenu.addAction(self.aboutAct)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.helpMenu)

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

    def scaleImage(self, factor, isAbsolute=False):
        if isAbsolute:
            self.scaleFactor = factor
        else:
            self.scaleFactor *= factor

        self.imageLabel.resize(self.scaleFactor * self.imageLabel.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                               + ((factor - 1) * scrollBar.pageStep() / 2)))

    def parse_config(self):
        # config file name
        configFileName = 'mySolutionBrowserConfig.ini'
        filePath = os.path.dirname(os.path.realpath(__file__))
        configFilePath = os.path.join(filePath, configFileName)
        # check if exists
        if os.path.isfile(configFilePath):
            print('loading config file')
            self.load_config_file(configFilePath)
        else:
            print('creating new config file')
            self.create_config_file(configFilePath)
            print('load just created config file')
            self.load_config_file(configFilePath)

    def create_config_file(self, configFilePath):
        # create config parser:
        config = configparser.ConfigParser(allow_no_value=True)
        # window settings
        config.add_section('WINDOW')
        config.set('WINDOW', 'hsize', '3600')
        config.set('WINDOW', 'vsize', '1600')
        config.set('WINDOW', 'start_maximized', 'yes')
        # data settings
        config.add_section('DATA')
        config.set('DATA', 'base_folder',
                   'C:\\Users\\rickw\\OneDrive\\Studie\\BMD_Master\\Internship_ImPhys\\EMech_waves\\mechanical_model\\model\\data')
        config.set('DATA', 'parlist_filename', 'parlist_sim.csv')
        config.set('DATA', 'default_set')
        # AHK settings
        config.add_section('AHK')
        config.set('AHK', 'executable_path')

        # Writing our configuration file to
        with open(configFilePath, 'w') as configfile:
            config.write(configfile)

    def load_config_file(self, configFilePath):
        # create config parser:
        config = configparser.ConfigParser(allow_no_value=True)
        # load config file
        config.read(configFilePath)

        # Window section
        self.hsize = config.getint('WINDOW', 'hsize')
        self.vsize = config.getint('WINDOW', 'vsize')
        self.isStartMaximized = config.getboolean('WINDOW', 'start_maximized')

        # data section
        self.base_folder = config.get('DATA', 'base_folder')
        self.parlist_filename = config.get('DATA', 'parlist_filename')
        self.default_set = config.get('DATA', 'default_set')

        # AHK section
        self.ahk_executable_path = config.get('AHK', 'executable_path')


class SolutionBrowserLayout(QWidget):
    def __init__(self, parent):
        super(SolutionBrowserLayout, self).__init__(parent)

        # principal layout
        self.principalLayout = QVBoxLayout(self)

        self.ImageViewerFrame = QFrame(self)
        self.ImageViewerFrame.setFrameShape(QFrame.StyledPanel)
        self.ImageViewerFrame.setFrameShadow(QFrame.Raised)

        self.ParameterFrame = QFrame(self)
        self.ParameterFrame.setFrameShape(QFrame.StyledPanel)
        self.ParameterFrame.setFrameShadow(QFrame.Raised)

        self.principalLayout.addWidget(self.ImageViewerFrame)
        self.principalLayout.addWidget(self.ParameterFrame)

        self.principalLayout.setContentsMargins(1, 1, 1, 1)


class ParDialog(QMainWindow):
    def __init__(self, parent=None):
        super(ParDialog, self).__init__(parent)

        # keep parent
        self.parent = parent

        # set mainwindow things
        self.setWindowTitle('View Parameters')
        self.hsize = 1000
        self.vsize = 1200
        self.resize(self.hsize, self.vsize)

        # set font
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

        # add frame
        self.frame = QFrame(self)
        self.layout = QVBoxLayout(self.frame)

        # add stuff to frame
        self.label = QLabel(self.frame)
        self.label.setText('Parameters:')

        # Add text field
        self.textfield = QTextBrowser(self.frame)
        self.textfield.insertPlainText("Parameter names and values listed here:\n")
        self.textfield.setLineWrapMode(0)
        monofont = QFont()
        monofont.setFamily("Courier New")
        self.textfieldFontSize = 10
        monofont.setPointSize(self.textfieldFontSize)
        self.monofont = monofont
        self.textfield.setFont(monofont)

        # add to layout
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.textfield)
        self.setCentralWidget(self.frame)
        # self.layout.setContentsMargins(1, 1, 1, 1)
        self.createActions()

    def closeEvent(self, event):
        # let parent now that I am closed
        self.parent.parDialogOpen = False

    def updateText(self, text=None):
        self.textfield.clear()
        if text:
            self.textfield.insertPlainText(text)
        else:
            self.textfield.insertPlainText("updated\n")

    def createActions(self):
        self.close_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.close_shortcut.activated.connect(self.closeWindowAndParent)

        self.close_dialog_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_dialog_shortcut.activated.connect(self.close)

        self.close_dialog_shortcut2 = QShortcut(QKeySequence("Ctrl+P"), self)
        self.close_dialog_shortcut2.activated.connect(self.close)

        self.font_plus = QShortcut(QKeySequence("Ctrl+="), self)
        self.font_plus.activated.connect(self.increaseFontSize)

        self.font_min = QShortcut(QKeySequence("Ctrl+-"), self)
        self.font_min.activated.connect(self.decreaseFontSize)

    def closeWindowAndParent(self):
        self.close()
        self.parent.close()

    def increaseFontSize(self):
        self.textfieldFontSize += 1
        self.updateFontSize()

    def decreaseFontSize(self):
        self.textfieldFontSize -= 1
        self.updateFontSize()

    def updateFontSize(self):
        self.monofont.setPointSize(self.textfieldFontSize)
        self.textfield.setFont(self.monofont)


if __name__ == '__main__':
    import sys
    import ctypes
    # fix icon stuff
    myappid = u'mycompany.myproduct.subproduct.version'  # arbitrary string (unicode)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # cd to file dir
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # see if there are any input arguments
    if len(sys.argv) > 1:
        batchToLoad = sys.argv[1]
    else:
        batchToLoad = None

    # launch app
    app = QApplication(sys.argv)
    w = SolutionBrowser(batchToLoad)
    w.show()

    # exit when app is exit
    sys.exit(app.exec_())
