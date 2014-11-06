#/*##########################################################################
# Copyright (C) 2014 European Synchrotron Radiation Facility
#
# This file is part of the PyMca X-ray Fluorescence Toolkit developed at
# the ESRF by the Software group.
#
# This toolkit is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# PyMca is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# PyMca; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# PyMca follows the dual licensing model of Riverbank's PyQt and cannot be
# used as a free plugin for a non-free program.
#
# Please contact the ESRF industrial unit (industry@esrf.fr) if this license
# is a problem for you.
#############################################################################*/
__author__ = "Tonn Rueter - ESRF Data Analysis Unit"

#
# GUI IMPORTS:
# uic: allows processing of ui files
# qt: PyMca version of qt
#
from PyQt4 import uic
from PyMca5.PyMcaGui import PyMcaQt as qt

#
# IMPORTS FROM RixsTool
#
from RixsTool.widgets.Models import ProjectModel
from RixsTool.Items import SpecItem, ScanItem, ImageItem
from RixsTool.ItemContainer import ItemContainer
from RixsTool.UiPaths import UiPaths

import numpy
import platform
from cStringIO import StringIO
#from os import linesep as OsLineSep
from os.path import splitext as OsPathSplitExt

DEBUG = 0
PLATFORM = platform.system()
NEWLINE = '\n'  # instead of OsLineSep


class RIXSMainWindow(qt.QMainWindow):
    def __init__(self, parent=None):
        qt.QMainWindow.__init__(self, parent)

        uiFilePath = UiPaths.mainWindowUiPath()

        uic.loadUi(uiFilePath, self)

        self.setWindowTitle('RixsTool')

        # TODO: Move this connect to RixsMaskImageWidget
        self.imageView.sigMaskImageWidgetSignal.connect(self.handleMaskImageSignal)

        #
        # Connect all the actions generated by the ui file. This mainly concerns the apps menu bar.
        # New actions can be registered in the functions body.
        #
        self.connectActions()

        # TODO: Do i really need more than one project at a time? This is currently unused anyway...
        self.projectDict = {
            '<current>': None,
            '<default>': ProjectModel()
        }
        self.currentProject = self.setCurrentProject()

        #
        # Handle data that enters the data visualization from the project visualization
        #
        self.projectBrowser.showSignal.connect(self._handleShowSignal)

        #
        # SIGNALS FROM
        # Tool windows from RixsTool allow interaction with the displayed data. They can be divided into
        # two types: inplace calculations with the result being immediately displayed and export tools
        # that take data present in the visualization and inject it into the current project.
        #
        # The signals of the latter must therefore trigger this injection process, while signals of the former
        # are handled internally by the RixsMaskImageWidget.
        #

        #
        # INTEGRATION
        #
        self.imageView.exportWidget.exportSelectedSignal.connect(self.exportSelectedImage)
        self.imageView.exportWidget.exportCurrentSignal.connect(self.exportCurrentImage)

        #
        # ENERGY SCALE
        #
        self.imageView.energyScaleTool.energyScaleSignal.connect(self.setEnergyScale)

    def setEnergyScale(self):
        scale = self.imageView.energyScaleTool.energyScale()
        if DEBUG >= 1:
            print('RIXSMainWindow.setEnergyScale -- scale: %s' % str(scale))

    def exportSelectedImage(self):
        #items = self.projectBrowser.selectedItems()
        items = self.projectBrowser.selectedContainers()
        self.exportingImages(items)

    def exportCurrentImage(self):
        #item = self.imageView.currentImageItem
        imageItem = self.imageView.currentImageItem
        if not imageItem:
            return
        try:
            container = self.currentProject[imageItem.key()]
        except KeyError:
            print('RIXSMainWindow.exportCurrentImage -- Image not found in project!')
        #if not container:
            return
        self.exportingImages([container])

    def exportingImages(self, itemContainerList):
        #def imageToSpectrum(self, imageItemList):
        if DEBUG >= 1:
            print('ProjectView.exportingImages -- Received %d item' % len(itemContainerList))
        toolList = self.imageView.toolList
        exportWidget = self.imageView.exportWidget
        #specContainer = self.currentProject['Spectra']

        for container in filter(ItemContainer.hasItem, itemContainerList):
            if container in self.currentProject:
                item = container.item()
                data = item.array

                if DEBUG >= 1:
                    print('ProjectView.exportingImages -- Found it! %s' % container.label)
                for step in toolList:
                    #
                    # HERE BE PROCESSING.. Apply filter and alignment to all images
                    #
                    if not step.active():
                        continue
                    parameters = step.getValues()
                    data = step.process(data, parameters)

                #
                # Build new tree item
                #
                result = exportWidget.process(data, {})

                key = item.key()
                newKey = key.replace('.edf', '.dat')

                newItem = SpecItem(
                    key=newKey,
                    header=item.header,
                    array=result,
                    fileLocation=''
                )

                #newContainer = ItemContainer(
                #    item=newItem,
                #    parent=specContainer,
                #    label=None  # is set automatically
                #)

                self.currentProject.addItem(newItem)

    def handleMaskImageSignal(self, ddict):
        if DEBUG >= 1:
            print("RIXSMainWindow.handleMaskImageSignal -- ddict: %s" % str(ddict))

    def handleToolStateChangedSignal(self, state, tool):
        if DEBUG >= 1:
            print("RIXSMainWindow.handleToolStateChangedSignal -- state: %d" % state)
            print("\t%s" % str(tool))

    def setCurrentProject(self, key='<default>'):
        """
        Changes the project. Function is not used at the moment.
        """
        #project = self.projectDict.get(key, None)
        model = self.projectDict['<default>']
        if not model:
            if DEBUG >= 1:
                print('RIXSMainWindow.setCurrentProject -- project not found')
            return self.projectDict['<default>']
        else:
            model = ProjectModel()
        self.fileBrowser.addSignal.connect(model.addFileInfoList)
        #self.projectBrowser.showSignal.connect(self._handleShowSignal)
        self.projectBrowser.setModel(model)
        self.projectDict[key] = model
        return model

    def _handleShowSignal(self, itemList):
        """
        :param list itemList: List of :py:class:`RixsTool.Items.ProjectItem`

        Slot to handle the showSignal emitted by :py:class:`RixsTool.Items.ProjectItem`. Depeding on the item type,
         the item data is visualized.
        """
        for item in itemList:
            if isinstance(item, ImageItem):
                #
                # Received 2-D data, use imageView
                #
                self.imageView.setImageItem(item)
                if DEBUG >= 1:
                    print('RIXSMainWindow._handleShowSignal -- Received ImageItem')
            elif isinstance(item, ScanItem) or isinstance(item, SpecItem):
                #
                # Received 1-D data, use specView
                #
                if DEBUG >= 1:
                    print('RIXSMainWindow._handleShowSignal -- Received SpecItem')
                if hasattr(item, 'scale'):
                    scale = item.scale()
                else:
                    numberOfPoints = len(item.array)
                    scale = numpy.arange(numberOfPoints)  # TODO: Lift numpy dependency here
                # def addCurve(self, x, y, legend, info=None, replace=False, replot=True, **kw):
                self.specView.addCurve(
                    x=scale,
                    y=item.array,
                    legend=item.key(),
                    replace=False,
                    replot=True
                )
                #raise NotImplementedError('RIXSMainWindow._handleShowSignal -- Received ScanItem')
        if DEBUG >= 1:
            print('RIXSMainWindow._handleShowSignal -- Done!')

    def connectActions(self):
        """
        Routine that connects the actions that can be triggered in the menu bar to the proper functions. This
        should only be done during instantiation.
        """
        actionList = [(self.colormapAction, self.imageView.selectColormap),
                      (self.bandPassFilterAction, self.openBandPassTool),
                      (self.integrationAction, self.imageView.showExportWidget),
                      (self.bandPassFilterID32Action, self.openBandPassID32Tool),
                      (self.energyScaleAction, self.imageView.energyScaleTool.show),
                      (self.saveSpectraAction, self.saveSpectra),
                      (self.projectBrowserShowAction, self.openProjectView)]
        for action, function in actionList:
            action.triggered[()].connect(function)
        if DEBUG >= 1:
            print('All Actions connected..')

    def saveSpectra(self):
        """
        Save routine that writes exports all spectra of the 'Spectra' node in a text file.
        """
        try:
            (fileNameList, singleFile, comment) = RixsSaveSpectraDialog.\
                getSaveFileName(parent=self,
                                caption='Save spectra',
                                directory=str(qt.QDir.home().absolutePath()))
            fileName = fileNameList[0]
        except IndexError:
            # Returned list is empty
            return
        except ValueError:
            # Returned list is empty
            return

        if DEBUG >= 1:
            print('RIXSMainWindow.saveSpectra -- result: %s' % str(fileNameList))
        #return

        #
        # Loop through all spectra in the top level of 'Spectra' group
        #
        specNode = self.currentProject['Spectra']
        specString = StringIO()
        specString.write(NEWLINE)

        itemList = [node.item() for node in specNode.children if node.hasItem]
        for idx, item in enumerate(itemList):
            #
            # Determine data shall be written
            #
            if isinstance(item, ScanItem):
                data = numpy.vstack((item.scale(), item.array)).T  # Stack and transpose
            elif isinstance(item, SpecItem):
                #
                # SpecItem does not have a scale, generate one by
                #
                scale = numpy.arange(
                    start=0,
                    stop=len(item.array),
                    dtype=item.array.dtype)
                data = numpy.vstack((scale, item.array)).T  # Stack and transpose
            else:
                raise NotImplementedError('RIXSMainWindow.saveSpectra -- Unknown item type: %s' % type(item))

            if data.ndim == 1:
                nRows, nCols = data.shape[0], 1
            elif data.ndim == 2:
                nRows, nCols = data.shape
            else:
                raise NotImplementedError('RIXSMainWindow.saveSpectra -- Can write item with dimensionality > 2')

            scanNo = 1

            #
            # Start to write spec file header...
            #
            specString.write('#S %d %s' % (scanNo, item.key()) + NEWLINE)

            #
            # Write EDF header in #U comments
            #
            if DEBUG >= 1:
                print("RIXSMainWindow.saveSpectra -- header: type(header):%s\n'%s'" % (type(item.header),
                                                                                       item.header))
            #headerLines = item.header.split('\n')
            ## Determine order of magnitude
            #if len(headerLines) > 0 and len(item.header) > 0:
            #    magnitude = len(str(len(headerLines)))
            #    for jdx, line in enumerate(headerLines):
            #        # Format string explanation:
            #        # #U              -> prefix, indicates header in spec file
            #        # {idx:0>{width}} -> write value 'idx' in a string with 'width' letters,
            #        #                    align value of 'idx' on the right and fill the
            #        #                    remaining space with zeros (i.e. leading zeros)
            #        # {line}          -> place value 'line' here
            #        specString.write(
            #            '#U{idx:0>{width}} {line}'.format(idx=jdx, width=magnitude, line=line) + NEWLINE
            #        )

            #
            # .. finish to write spec file header
            #
            specString.write('#N %d' % nCols + NEWLINE)  # Number of columns
            specString.write('#L PixelNo  Counts' + NEWLINE)  # Column labels

            #
            # Write data using numpy.savetxt, parameter fname can be file handle
            #
            numpy.savetxt(
                fname=specString,
                X=data,
                fmt='%.6f',
                delimiter=' ',
                newline=NEWLINE
            )

            specString.write(NEWLINE)

            if not singleFile:
                #
                # File names feature indexation
                #
                path, ext = OsPathSplitExt(fileName)
                numberedPath = '{path}_{idx:0>{width}}{ext}'.format(
                    path=path,
                    idx=idx,
                    width=len(itemList),
                    ext=ext
                )
                with open(numberedPath, 'wb') as fileHandle:
                    fileHandle.write(specString.getvalue())

                #
                # Reset StringIO
                #
                specString = StringIO()

        if singleFile:
            with open(fileName, 'wb') as fileHandle:
                fileHandle.write(specString.getvalue())

        if DEBUG >= 1:
            print('RIXSMainWindow.saveSpectra -- Done!')

    def openBandPassTool(self):
        self.imageView.setCurrentFilter('bandpass')

    def openBandPassID32Tool(self):
        self.imageView.setCurrentFilter('bandpassID32')

    def openProjectView(self):
        self.projectBrowser.show()


class RixsSaveSpectraDialog(qt.QFileDialog):
    def __init__(self, parent, caption, directory):
        qt.QFileDialog.__init__(self, parent, caption, directory, '')

        saveOptsGB = qt.QGroupBox('Save options', self)
        saveOptsBG = qt.QButtonGroup()
        self.singleFile = qt.QRadioButton('Save spectra in one single file', self)
        self.individualFiles = qt.QRadioButton('Save spectra in individual files', self)
        self.singleFile.setChecked(True)

        saveOptsBG.addButton(self.individualFiles)
        saveOptsBG.addButton(self.singleFile)
        saveOptsBG.setExclusive(True)  # Only one button at a time can be checked

        mainLayout = self.layout()
        optsLayout = qt.QGridLayout()
        optsLayout.addWidget(self.individualFiles, 0, 0)
        optsLayout.addWidget(self.singleFile, 1, 0)
        saveOptsGB.setLayout(optsLayout)
        mainLayout.addWidget(saveOptsGB, 4, 0, 1, 3)

    @staticmethod
    def getSaveFileName(parent, caption, directory, typeFilter=None, selectedFilter=None, options=None):
        dial = RixsSaveSpectraDialog(parent, caption, directory)
        dial.setAcceptMode(qt.QFileDialog.AcceptSave)
        singleFile = None
        comment = None
        fileNameList = []
        if dial.exec_():
            singleFile = dial.singleFile.isChecked()
            fileNameList = [qt.safe_str(fn) for fn in dial.selectedFiles()]
        return fileNameList, singleFile, comment


class DummyNotifier(qt.QObject):
    def signalReceived(self, val=None):
        print('DummyNotifier.signal received -- kw:\n', str(val))

if __name__ == '__main__':
    app = qt.QApplication([])
    win = RIXSMainWindow()
    win.show()
    app.exec_()
