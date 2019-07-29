'''
GUI to explore simulation results

Rick Waasdorp, 29-07-2019
v1.1
'''

from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QPushButton, QSizePolicy, QComboBox, QSpacerItem, QSlider, QStyle,
                             QToolButton, QVBoxLayout, QWidget, QMainWindow, QMenu, QAction, QLabel, QMessageBox, QScrollArea, QFileDialog)
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QFont
from PyQt5.QtCore import QDir, Qt, QSize
from math import floor, ceil
import os
import time
import configparser
import pandas as pd
import numpy as np


class JumpSlider(QSlider):
    def mousePressEvent(self, ev):
        """ Jump to click position """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width()))

    def mouseMoveEvent(self, ev):
        """ Jump to pointer position while moving """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width()))


class SolutionBrowser(QMainWindow):
    def __init__(self):
        super(SolutionBrowser, self).__init__()

        # parse config
        self.parse_config()

        # set size mainwindow
        self.setWindowTitle('Solution Browser')
        self.resize(self.hsize, self.vsize)
        if self.isStartMaximized:
            self.setWindowState(Qt.WindowMaximized)

        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

        # load layout top and bottom frames
        self.layouts = SolutionBrowserLayout(self)
        self.setCentralWidget(self.layouts)

        self.createActions()
        self.createMenus()

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

    def resizeEvent(self, event):
        # print("resize")
        self.fitToWindow(True)
        # time.sleep(.300)

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

        for idx, name, values in zip(range(len(self.parNames)), self.parNames, self.uniqueVals):
            frame, label, valueBox, slider, valIdx = self.createSliderGroup(idx, name, values)
            self.parFrames.append(frame)
            self.parLabels.append(label)
            self.parBoxes.append(valueBox)
            self.parSliders.append(slider)
            self.valIndices.append(valIdx)
            layout.addWidget(frame)

        layout.setContentsMargins(1, 1, 1, 1)
        self.ParameterFrame.setLayout(layout)

        layout.addWidget(frame)

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

        valIdx = floor((len(parameterValues)-1)/2)

        valueBox = QComboBox(frame)
        valueBox.addItems([str(x) for x in parameterValues])
        valueBox.setCurrentIndex(valIdx)
        valueBox.currentIndexChanged.connect(boxChange)

        slider = JumpSlider(Qt.Horizontal)
        slider.setRange(0, len(parameterValues)-1)
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

        if source == 'slider':
            self.updateImage()

    def updateImage(self):
        # print(self.valIndices)

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
        row_idx = self.parData[pd.Series(row)].index
        imgFileName = self.parData['imgFile'].iloc[row_idx[0]]
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
            # get parameter names:
            parNames = list(self.parData.columns)
            parNames.remove('SimNum')
            self.parNames = parNames

            # get unique values per paramter
            uniqueVals = []
            for par in parNames:
                uniqueVals.append(self.parData[par].unique())
            self.uniqueVals = uniqueVals

            # add file location to data frame
            fnameBase = '{0}_{1}\\fig\\overview_{0}_{1}.png'.format(simulationName, '%03i')
            imgFiles = []
            for num in list(self.parData['SimNum']):
                imgFiles.append(os.path.join(batchFolder, fnameBase % (num, num)))

            self.parData['imgFile'] = imgFiles

    def open_image(self, fileName=None):
        if not fileName:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())
        else:
            image = QImage(fileName)
            if image.isNull():
                msg = QMessageBox()
                fileParts = fileName.split('\\')
                msg.setText('Cannot load:\n%s' % fileParts[-1])
                msg.setWindowTitle("Image Viewer")
                msg.setDetailedText("%s" % fileName)
                msg.setStyleSheet("QLabel{min-width: 700px;}")
                msg.exec()
                # msg.setModal(False)
                # msg.setIcon(QMessageBox.information)
                # msg.setFixedSize(QSize(600, 400))
                # QMessageBox.information(self, "Image Viewer", "Cannot load %s." % fileName)
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
            f_width = area_size.width()/image_size.width()
            f_height = area_size.height()/image_size.height()
            new_factor = min((f_width, f_height))
            self.scaleImage(new_factor)
            self.reuseScaleFactor = new_factor

        # if not isResizeEvent:
        #     self.normalSize()
        self.updateActions()

    def createActions(self):
        self.openAct = QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open_image)
        self.openBatchAct = QAction("&Open Batch...", self,
                                    shortcut="Ctrl+P", triggered=self.open_batch)
        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)
        self.zoomInAct = QAction("Zoom &In (25%)", self, shortcut="Ctrl+=",
                                 enabled=False, triggered=self.zoomIn)
        self.zoomOutAct = QAction("Zoom &Out (25%)", self, shortcut="Ctrl+-",
                                  enabled=False, triggered=self.zoomOut)
        self.normalSizeAct = QAction("&Normal Size", self, shortcut="Ctrl+S",
                                     enabled=False, triggered=self.normalSize)
        self.fitToWindowAct = QAction("&Fit to Window", self, enabled=False,
                                      checkable=True, shortcut="Ctrl+F", triggered=self.fitToWindow)

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openBatchAct)
        self.fileMenu.addAction(self.openAct)
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
                               + ((factor - 1) * scrollBar.pageStep()/2)))

    def parse_config(self):
        # config file name
        configFileName = 'mySolutionBrowserConfig.ini'
        filePath = os.path.dirname(os.path.realpath(__file__))
        configFilePath = os.path.join(filePath, configFileName)
        print(configFilePath)
        # check if exists
        if os.path.isfile(configFilePath):
            # try:
            print('loading config file')
            self.load_config_file(configFilePath)
            # except:
            #     print('could not load config')
            #     return
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
        # config.set('DATA', 'default_set', 'mega_batch2')
        config.set('DATA', 'default_set')

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

        # print(self.base_folder)
        # print(self.parlist_filename)
        # print(self.default_set)
        # print(type(self.base_folder))
        # print(type(self.parlist_filename))
        # print(type(self.default_set))


class SolutionBrowserLayout(QWidget):
    def __init__(self, parent):
        super(SolutionBrowserLayout, self).__init__(parent)

        # principal layout
        self.principalLayout = QVBoxLayout(self)

        self.ImageViewerFrame = QFrame(self)
        self.ImageViewerFrame.setFrameShape(QFrame.StyledPanel)
        self.ImageViewerFrame.setFrameShadow(QFrame.Raised)
        # self.ImageViewerFrame.setStyleSheet("background-color: blue")

        self.ParameterFrame = QFrame(self)
        self.ParameterFrame.setFrameShape(QFrame.StyledPanel)
        self.ParameterFrame.setFrameShadow(QFrame.Raised)
        # self.ParameterFrame.setStyleSheet("background-color: red")

        self.principalLayout.addWidget(self.ImageViewerFrame)
        self.principalLayout.addWidget(self.ParameterFrame)

        self.principalLayout.setContentsMargins(1, 1, 1, 1)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    w = SolutionBrowser()
    w.show()
    sys.exit(app.exec_())
