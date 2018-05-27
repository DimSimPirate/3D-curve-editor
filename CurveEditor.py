from __main__ import vtk, qt, ctk, slicer
import os
import unittest
import numpy
import math
#import unittest

class CurveEditor:
    def __init__(self, parent):
        parent.title = "3D Curve Editor"
        parent.categories = ["CurveEditor"]
        #parent.dependencies = []
        parent.contributors = ["Matthew Burgess"]
        parent.helpText = """Create 3D curves by: \r\n
            - First selecting input points using the Fiducial tool \r\n
            - Select the source points either from an existing list, or F for newly created set \r\n
            - Select model to save the curve to \r\n
            - Set the radius of the 3D curve \r\n
            - Select either none (linear) or cardinal (curved) for interpolation \r\n
            - Select auto update for continuous feedback \r\n
            - Press Generate Curve"""
        self.parent = parent

class CurveEditorWidget:
    def __init__(self, parent = None):
        if not parent:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
        else:
            self.parent = parent
        self.layout = self.parent.layout()
        if not parent:
            self.setup()
            self.parent.show()
        self.logic = Logic()

    def setup(self):

        # Tags are used to manage event ovservers
        self.tagSourceNode = None
        self.tagDestinationNode = None

        #Set up area for creating curves
        createCurveBttn = ctk.ctkCollapsibleButton()
        createCurveBttn.text = "Create Curve"
        self.layout.addWidget(createCurveBttn)
        layout = qt.QFormLayout(createCurveBttn)

        #Selecting source points from fiducials
        self.SourceSelector = slicer.qMRMLNodeComboBox()
        self.SourceSelector.nodeTypes = ( ("vtkMRMLMarkupsFiducialNode"), "" )
        self.SourceSelector.addEnabled = True
        self.SourceSelector.removeEnabled = True
        self.SourceSelector.noneEnabled = True
        self.SourceSelector.renameEnabled = True
        self.SourceSelector.setMRMLScene( slicer.mrmlScene )
        self.SourceSelector.setToolTip("Select fiducial source")
        layout.addRow("Source points: ", self.SourceSelector)

        #Selecting destination for new curve
        self.DestinationSelector = slicer.qMRMLNodeComboBox()
        self.DestinationSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
        self.DestinationSelector.addEnabled = True
        self.DestinationSelector.removeEnabled = True
        self.DestinationSelector.noneEnabled = True
        self.DestinationSelector.renameEnabled = True
        self.DestinationSelector.selectNodeUponCreation = True
        self.DestinationSelector.setMRMLScene( slicer.mrmlScene )
        self.DestinationSelector.setToolTip( "Select destination for curve" )
        layout.addRow("Curve model: ", self.DestinationSelector)

        #x, y, z inputs for new fiducial
        self.validator = qt.QDoubleValidator()
        self.AddFiducialLayout = qt.QHBoxLayout()
        self.AddX = qt.QLineEdit("X")
        self.AddX.setValidator(self.validator)
        self.AddY = qt.QLineEdit("Y")
        self.AddY.setValidator(self.validator)
        self.AddZ = qt.QLineEdit("Z")
        self.AddZ.setValidator(self.validator)
        self.AddFiducialLayout.addWidget(self.AddX)
        self.AddFiducialLayout.addWidget(self.AddY)
        self.AddFiducialLayout.addWidget(self.AddZ)
        layout.addRow("X, Y, Z coordinates for new fiducial: ", self.AddFiducialLayout)

        #Add fiducial button
        self.AddFiducialButton = qt.QPushButton("Add Fiducial")
        self.AddFiducialButton.toolTip = "Adds curve point using given x, y, z coordinates"
        self.AddFiducialButton.enabled = True
        layout.addRow("", self.AddFiducialButton)

        #Current fiducials table
        self.FiducialTable = qt.QTableWidget(1, 4)
        self.FiducialTableHeaders = ["Name", "X (mm)", "Y (mm)", "Z (mm)"]
        self.FiducialTable.setHorizontalHeaderLabels(self.FiducialTableHeaders)
        layout.addWidget(self.FiducialTable)

        #Radius of curve
        self.RadiusSliderWidget = ctk.ctkSliderWidget()
        self.RadiusSliderWidget.singleStep = 0.5
        self.RadiusSliderWidget.minimum = 0.5
        self.RadiusSliderWidget.maximum = 20.0
        self.RadiusSliderWidget.value = 3.0
        self.RadiusSliderWidget.setToolTip("Determines the thickness of the curve")
        layout.addRow("Thickness: ", self.RadiusSliderWidget)

        #Select the method of interpolation
        self.InterpolationLayout = qt.QHBoxLayout()
        self.InterpolationLinear = qt.QRadioButton("Linear")
        self.InterpolationLinear.setToolTip( "Straight lines from point to point" )
        self.InterpolationSpline = qt.QRadioButton("Spline")
        self.InterpolationSpline.setToolTip( "Cardinal spline will create curvature between points" )
        self.InterpolationLayout.addWidget(self.InterpolationLinear)
        self.InterpolationLayout.addWidget(self.InterpolationSpline)
        self.InterpolationGroup = qt.QButtonGroup()
        self.InterpolationGroup.addButton(self.InterpolationLinear)
        self.InterpolationGroup.addButton(self.InterpolationSpline)
        layout.addRow("Interpolation: ", self.InterpolationLayout)

        #Button for generating specified curve
        self.GenerateButton = qt.QPushButton("Generate/Update Curve")
        self.GenerateButton.toolTip = "Creates or updates curve specified"
        self.GenerateButton.enabled = True
        layout.addRow("", self.GenerateButton)

        #Linking buttons to methods
        self.InterpolationLinear.connect('clicked(bool)', self.onSelectInterpolationLinear)
        self.InterpolationSpline.connect('clicked(bool)', self.onSelectInterpolationSpline)
        self.SourceSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSourceSelected)
        self.DestinationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onDestinationSelected)
        self.AddX.textChanged.connect(lambda inputSelection: self.checkInputState('x'))
        self.AddX.textChanged.emit(self.AddX.text)
        self.AddY.textChanged.connect(lambda inputSelection: self.checkInputState('y'))
        self.AddY.textChanged.emit(self.AddY.text)
        self.AddZ.textChanged.connect(lambda inputSelection: self.checkInputState('z'))
        self.AddZ.textChanged.emit(self.AddZ.text)
        self.AddFiducialButton.connect('clicked(bool)', self.addFiducial)
        self.RadiusSliderWidget.connect("valueChanged(double)", self.onThicknessUpdated)
        self.GenerateButton.connect('clicked(bool)', self.generateCurve)

        #Default checkboxes
        self.InterpolationSpline.setChecked(True)
        self.onSelectInterpolationSpline(True)

        self.layout.addStretch(1)

    #Sets the selected source nodes from the dropdown menu
    def onSourceSelected(self):
        if self.SourceSelector.currentNode():
            self.logic.SourceNode = self.SourceSelector.currentNode()
            curveId = self.logic.SourceNode.GetAttribute('CurveEditor.CurveModel')
            self.DestinationSelector.setCurrentNodeID(curveId)
        self.updateFiducialsTable();

        if (self.SourceSelector.currentNode() != None and self.DestinationSelector.currentNode() != None):
            self.logic.SourceNode.SetAttribute('CurveEditor.CurveModel',self.logic.DestinationNode.GetID())

    #Sets the selected curve destination from the dropdown menu
    def onDestinationSelected(self):
        if self.DestinationSelector.currentNode():
            self.logic.DestinationNode = self.DestinationSelector.currentNode()
        if (self.SourceSelector.currentNode() != None and self.DestinationSelector.currentNode() != None):
            self.logic.SourceNode.SetAttribute('CurveEditor.CurveModel',self.logic.DestinationNode.GetID())

    #Checks whether the inputs for a new fiducial are valid
    def checkInputState(self, inputSelection):
        if inputSelection == 'x':
            sender = self.AddX
        elif inputSelection == 'y':
            sender = self.AddY
        else:
            sender = self.AddZ
        state = self.validator.validate(sender.text, 0)
        if state == qt.QValidator.Acceptable:
            colour = '#c4df9b'
        else:
            colour = '#f6989d'
        sender.setStyleSheet('QLineEdit {background-color: %s}' % colour)

    #Adds new fiducial to selected source points
    def addFiducial(self):
        if self.SourceSelector.currentNode != None:
            if self.AddX.hasAcceptableInput and self.AddY.hasAcceptableInput and self.AddZ.hasAcceptableInput:
                x = float(self.AddX.text)
                y = float(self.AddY.text)
                z = float(self.AddZ.text)
                self.logic.SourceNode.AddFiducial(x, y, z)
                self.updateFiducialsTable()
                self.logic.updateCurve()

    #Updates table of fiducial names and positions
    def updateFiducialsTable(self):
        if not self.logic.SourceNode or self.logic.SourceNode == None:
            self.FiducialTable.clear()
            self.FiducialTable.setHorizontalHeaderLabels(self.FiducialTableHeaders)
        else:
            self.FiducialTableData = []
            numControlPoints = self.logic.SourceNode.GetNumberOfFiducials()
            self.FiducialTable.setRowCount(numControlPoints)

            for i in range(numControlPoints):
                name = self.logic.SourceNode.GetNthFiducialLabel(i)
                pos = [0, 0, 0]
                self.logic.SourceNode.GetNthFiducialPosition(i, pos)
                cellName = qt.QTableWidgetItem(name)
                cellX = qt.QTableWidgetItem('%.3f' % pos[0])
                cellY = qt.QTableWidgetItem('%.3f' % pos[1])
                cellZ = qt.QTableWidgetItem('%.3f' % pos[2])
                row = [cellName, cellX, cellY, cellZ]
                self.FiducialTable.setItem(i, 0, row[0])
                self.FiducialTable.setItem(i, 1, row[1])
                self.FiducialTable.setItem(i, 2, row[2])
                self.FiducialTable.setItem(i, 3, row[3])
                self.FiducialTableData.append(row)

            self.FiducialTable.show()

    #Sets radius of tube to slider value
    def onThicknessUpdated(self):
        self.logic.setCurveThickness(self.RadiusSliderWidget.value)

    #Sets interpolation method to linear
    def onSelectInterpolationLinear(self, s):
        self.logic.setInterpolationMethod(0)

    #Sets interpolation method to spline
    def onSelectInterpolationSpline(self, s):
        self.logic.setInterpolationMethod(1)

    #Creates or updates a new curve and updates the fiducials table
    def generateCurve(self):
        self.logic.updateCurve()
        self.updateFiducialsTable()

class Logic:

    def __init__(self):
        self.SourceNode = None
        self.DestinationNode = None
        self.CurveThickness = 5.0
        self.NumberOfIntermediatePoints = 20
        self.CurveColour = [0.0, 1.0, 0.0]
        self.CurvePoly = None
        self.Resolution = 30
        self.CurveFaces = 20
        self.InterpolationMethod = 0

    def setCurveThickness(self, radius):
        self.CurveThickness = radius
        self.updateCurve()

    def setInterpolationMethod(self, method):
        self.InterpolationMethod = method
        self.updateCurve()

    #Takes a set of fiducials and outputs polyline
    def nodesToLinear(self, sourceNode, outputPoly):
        points = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        numControlPoints = sourceNode.GetNumberOfFiducials()
        pos = [0.0, 0.0, 0.0]
        offset = 0

        points.SetNumberOfPoints(numControlPoints)
        cells.InsertNextCell(numControlPoints)

        for i in range(numControlPoints):
            sourceNode.GetNthFiducialPosition(i,pos)
            points.SetPoint(offset+i,pos)
            cells.InsertCellPoint(offset+i)

        offset = offset + numControlPoints

        outputPoly.Initialize()
        outputPoly.SetPoints(points)
        outputPoly.SetLines(cells)

    #Takes a set of fiducials and outputs a splined polyline
    def nodesToSpline(self, sourceNode, outputPoly):
        numControlPoints = sourceNode.GetNumberOfFiducials()
        pos = [0.0, 0.0, 0.0]

        #Three independent splines for x, y, and z
        xSpline = vtk.vtkCardinalSpline()
        ySpline = vtk.vtkCardinalSpline()
        zSpline = vtk.vtkCardinalSpline()
        xSpline.ClosedOff()
        ySpline.ClosedOff()
        zSpline.ClosedOff()

        for i in range(0, numControlPoints):
            sourceNode.GetNthFiducialPosition(i, pos)
            xSpline.AddPoint(i, pos[0])
            ySpline.AddPoint(i, pos[1])
            zSpline.AddPoint(i, pos[2])

        #There will be a self.resolution number of intermediate points
        interpolatedPoints = (self.Resolution+2)*(numControlPoints-1)
        points = vtk.vtkPoints()
        r = [0.0, 0.0]
        xSpline.GetParametricRange(r)
        t = r[0]
        p = 0
        tStep = (numControlPoints-1.0)/(interpolatedPoints-1.0)
        numOutputPoints = 0

        while t < r[1]:
            points.InsertPoint(p, xSpline.Evaluate(t), ySpline.Evaluate(t), zSpline.Evaluate(t))
            t = t + tStep
            p = p + 1
        numOutputPoints = p

        lines = vtk.vtkCellArray()
        lines.InsertNextCell(numOutputPoints)
        for i in range(0, numOutputPoints):
            lines.InsertCellPoint(i)

        outputPoly.SetPoints(points)
        outputPoly.SetLines(lines)

    #Updates the curve based on logic parameters
    def updateCurve(self):
        if self.SourceNode and self.DestinationNode:
            if self.SourceNode.GetNumberOfFiducials() < 2:
                if self.CurvePoly != None:
                    self.CurvePoly.Initialize()
            else:
                if self.CurvePoly == None:
                    self.CurvePoly = vtk.vtkPolyData()
                if self.DestinationNode.GetDisplayNodeID() == None:
                    modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
                    modelDisplayNode.SetColor(self.CurveColour)
                    slicer.mrmlScene.AddNode(modelDisplayNode)
                    self.DestinationNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
                if self.InterpolationMethod == 0:
                    self.nodesToLinear(self.SourceNode, self.CurvePoly)
                elif self.InterpolationMethod == 1:
                    self.nodesToSpline(self.SourceNode, self.CurvePoly)

            tubeFilter = vtk.vtkTubeFilter()
            tubeFilter.SetInputData(self.CurvePoly)
            tubeFilter.SetRadius(self.CurveThickness)
            tubeFilter.SetNumberOfSides(self.CurveFaces)
            tubeFilter.CappingOn()
            tubeFilter.Update()

            self.DestinationNode.SetAndObservePolyData(tubeFilter.GetOutput())
            self.DestinationNode.Modified()

            if self.DestinationNode.GetScene() == None:
                slicer.mrmlScene.AddNode(self.DestinationNode)

            displayNode = self.DestinationNode.GetDisplayNode()
            if displayNode:
                displayNode.SetActiveScalarName('')

#class Tests(unittest.TestCase):
#    def test(self):
#        curveEditor = CurveEditor()
#        self.assertEquals()
