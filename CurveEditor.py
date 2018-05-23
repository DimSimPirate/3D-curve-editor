from __main__ import vtk, qt, ctk, slicer
import os
import unittest
import numpy
import math

class CurveEditor:
    def __init__(self, parent):
        parent.title = "3D Curve Editor"
        parent.categories = ["CurveEditor"]
        parent.dependencies = []
        parent.contributors = ["Matthew Burgess"]
        parent.helpText = """Create 3D curves by:
            - First selecting input points using the Fiducial tool
            - Select the source points either from an existing list, or F for newly created set
            - Select model to save the curve to
            - Set the radius of the 3D curve
            - Select either none (linear) or cardinal (curved) for interpolation
            - Select auto update for continuous feedback
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
        self.logic = CurveLogic()

    def setup(self):

        # Tags to manage event observers
        self.tagSourceNode = None
        self.tagDestinationNode = None

        #Generate inputs and set up a new curve
        createCurveButton = ctk.ctkCollapsibleButton()
        createCurveButton.text = "Create Curve"
        self.layout.addWidget(createCurveButton)

        curveLayout = qt.QFormLayout(createCurveButton)

        #Select source points
        self.SourceSelector = slicer.qMRMLNodeComboBox()
        self.SourceSelector.nodeTypes = ( ("vtkMRMLMarkupsFiducialNode"), "" )
        self.SourceSelector.addEnabled = True
        self.SourceSelector.removeEnabled = True
        self.SourceSelector.noneEnabled = True
        self.SourceSelector.renameEnabled = True
        self.SourceSelector.setMRMLScene( slicer.mrmlScene )
        self.SourceSelector.setToolTip( "Pick up a Markups node listing fiducials." )
        curveLayout.addRow("Source points: ", self.SourceSelector)

        #
        # Target point (vtkMRMLMarkupsFiducialNode)
        #
        self.DestinationSelector = slicer.qMRMLNodeComboBox()
        self.DestinationSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
        self.DestinationSelector.addEnabled = True
        self.DestinationSelector.removeEnabled = True
        self.DestinationSelector.noneEnabled = True
        self.DestinationSelector.renameEnabled = True
        self.DestinationSelector.selectNodeUponCreation = True
        self.DestinationSelector.setMRMLScene( slicer.mrmlScene )
        self.DestinationSelector.setToolTip( "Pick up or create a Model node." )
        curveLayout.addRow("Curve model: ", self.DestinationSelector)

        #
        # Radius for the tube
        #
        self.RadiusSliderWidget = ctk.ctkSliderWidget()
        self.RadiusSliderWidget.singleStep = 1.0
        self.RadiusSliderWidget.minimum = 1.0
        self.RadiusSliderWidget.maximum = 50.0
        self.RadiusSliderWidget.value = 5.0
        self.RadiusSliderWidget.setToolTip("Set the raidus of the tube.")
        curveLayout.addRow("Radius (mm): ", self.RadiusSliderWidget)

        #
        # Radio button to select interpolation method
        #
        self.InterpolationLayout = qt.QHBoxLayout()
        self.InterpolationNone = qt.QRadioButton("None")
        self.InterpolationCardinalSpline = qt.QRadioButton("Cardinal Spline")
        self.InterpolationLayout.addWidget(self.InterpolationNone)
        self.InterpolationLayout.addWidget(self.InterpolationCardinalSpline)

        self.InterpolationGroup = qt.QButtonGroup()
        self.InterpolationGroup.addButton(self.InterpolationNone)
        self.InterpolationGroup.addButton(self.InterpolationCardinalSpline)

        curveLayout.addRow("Interpolation: ", self.InterpolationLayout)

        #
        # Check box to start curve visualization
        #
        self.EnableAutoUpdateCheckBox = qt.QCheckBox()
        self.EnableAutoUpdateCheckBox.checked = 0
        self.EnableAutoUpdateCheckBox.setToolTip("If checked, the CurveMaker module keeps updating the model as the points are updated.")
        curveLayout.addRow("Auto update:", self.EnableAutoUpdateCheckBox)

        #
        # Button to generate a curve
        #
        self.GenerateButton = qt.QPushButton("Generate Curve")
        self.GenerateButton.toolTip = "Generate Curve"
        self.GenerateButton.enabled = True
        curveLayout.addRow("", self.GenerateButton)

        # Connections
        self.InterpolationNone.connect('clicked(bool)', self.onSelectInterpolationNone)
        self.InterpolationCardinalSpline.connect('clicked(bool)', self.onSelectInterpolationCardinalSpline)
        self.EnableAutoUpdateCheckBox.connect('toggled(bool)', self.onEnableAutoUpdate)
        self.SourceSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSourceSelected)
        self.DestinationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onDestinationSelected)
        self.RadiusSliderWidget.connect("valueChanged(double)", self.onTubeUpdated)
        self.GenerateButton.connect('clicked(bool)', self.onGenerateCurve)

        # Set default
        ## default interpolation method
        self.InterpolationCardinalSpline.setChecked(True)
        self.onSelectInterpolationCardinalSpline(True)

        self.layout.addStretch(1)


    def cleanup(self):
        pass

    def onEnableAutoUpdate(self, state):
        self.logic.enableAutomaticUpdate(state)

    def onGenerateCurve(self):
        self.logic.generateCurveOnce()

    def onSourceSelected(self):
        # Remove observer if previous node exists
        if self.logic.SourceNode and self.tagSourceNode:
            self.logic.SourceNode.RemoveObserver(self.tagSourceNode)

        # Update selected node, add observer, and update control points
        if self.SourceSelector.currentNode():
            self.logic.SourceNode = self.SourceSelector.currentNode()

            # Check if model has already been generated with for this fiducial list
            tubeModelID = self.logic.SourceNode.GetAttribute('CurveEditor.CurveModel')
            self.DestinationSelector.setCurrentNodeID(tubeModelID)
            self.tagSourceNode = self.logic.SourceNode.AddObserver('ModifiedEvent', self.logic.controlPointsUpdated)

        # Update checkbox
        if (self.SourceSelector.currentNode() == None or self.DestinationSelector.currentNode() == None):
            self.EnableAutoUpdateCheckBox.setCheckState(False)
        else:
            self.logic.SourceNode.SetAttribute('CurveEditor.CurveModel',self.logic.DestinationNode.GetID())
            self.logic.updateCurve()

    def onDestinationSelected(self):
        if self.logic.DestinationNode and self.tagDestinationNode:
            self.logic.DestinationNode.RemoveObserver(self.tagDestinationNode)
            if self.logic.DestinationNode.GetDisplayNode() and self.tagDestinationDispNode:
                self.logic.DestinationNode.GetDisplayNode().RemoveObserver(self.tagDestinationDispNode)

        # Update destination node
        if self.DestinationSelector.currentNode():
            self.logic.DestinationNode = self.DestinationSelector.currentNode()

            if self.logic.DestinationNode.GetDisplayNode():
                self.tagDestinationDispNode = self.logic.DestinationNode.GetDisplayNode().AddObserver(vtk.vtkCommand.ModifiedEvent, self.onModelDisplayModifiedEvent)

        # Update checkbox
        if (self.SourceSelector.currentNode() == None or self.DestinationSelector.currentNode() == None):
            self.EnableAutoUpdateCheckBox.setCheckState(False)
        else:
            self.logic.SourceNode.SetAttribute('CurveEditor.CurveModel',self.logic.DestinationNode.GetID())
            self.logic.updateCurve()


    def onTubeUpdated(self):
        self.logic.setTubeRadius(self.RadiusSliderWidget.value)

    def onReload(self,moduleName="CurveEditor"):
        """Generic reload method for any scripted module.
        ModuleWizard will subsitute correct default moduleName.
        """
        globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)


    def onSelectInterpolationNone(self, s):
        self.logic.setInterpolationMethod(0)

    def onSelectInterpolationCardinalSpline(self, s):
        self.logic.setInterpolationMethod(1)

    def onTargetFiducialsSelected(self):
        # Remove observer if previous node exists
        if self.targetFiducialsNode and self.tag:
            self.targetFiducialsNode.RemoveObserver(self.tag)

        # Update selected node, add observer, and update control points
        if self.targetFiducialsSelector.currentNode():
            self.targetFiducialsNode = self.targetFiducialsSelector.currentNode()

        else:
            self.targetFiducialsNode = None
            self.tag = None


class CurveLogic:

    def __init__(self):
        self.SourceNode = None
        self.DestinationNode = None
        self.TubeRadius = 5.0

        self.AutomaticUpdate = False
        self.NumberOfIntermediatePoints = 20
        self.ModelColor = [0.0, 1.0, 0.0]

        self.CurvePoly = None
        self.interpResolution = 25

        # Interpolation method:
        #  0: None
        #  1: Cardinal Spline (VTK default)
        self.InterpolationMethod = 0

        self.CurveLength = -1.0  ## Length of the curve (<0 means 'not measured')

    def setNumberOfIntermediatePoints(self,npts):
        if npts > 0:
            self.NumberOfIntermediatePoints = npts
        self.updateCurve()

    def setTubeRadius(self, radius):
        self.TubeRadius = radius
        self.updateCurve()

    def setInterpolationMethod(self, method):
        if method > 3 or method < 0:
            self.InterpolationMethod = 0
        else:
            self.InterpolationMethod = method
        self.updateCurve()

    def enableAutomaticUpdate(self, auto):
        self.AutomaticUpdate = auto
        self.updateCurve()

    def generateCurveOnce(self):
        prevAutomaticUpdate = self.AutomaticUpdate
        self.AutomaticUpdate = True
        self.updateCurve()
        self.AutomaticUpdate = prevAutomaticUpdate

    def controlPointsUpdated(self,caller,event):
        if caller.IsA('vtkMRMLMarkupsFiducialNode') and event == 'ModifiedEvent':
            self.updateCurve()

    def nodeToPoly(self, sourceNode, outputPoly, closed=False):
        points = vtk.vtkPoints()
        cellArray = vtk.vtkCellArray()

        nOfControlPoints = sourceNode.GetNumberOfFiducials()
        pos = [0.0, 0.0, 0.0]
        posStartEnd = [0.0, 0.0, 0.0]

        offset = 0

        if not closed:
            points.SetNumberOfPoints(nOfControlPoints)
            cellArray.InsertNextCell(nOfControlPoints)
        else:
            posStart = [0.0, 0.0, 0.0]
            posEnd = [0.0, 0.0, 0.0]
            sourceNode.GetNthFiducialPosition(0,posStart)
            sourceNode.GetNthFiducialPosition(nOfControlPoints-1,posEnd)
            posStartEnd[0] = (posStart[0]+posEnd[0])/2.0
            posStartEnd[1] = (posStart[1]+posEnd[1])/2.0
            posStartEnd[2] = (posStart[2]+posEnd[2])/2.0
            points.SetNumberOfPoints(nOfControlPoints+2)
            cellArray.InsertNextCell(nOfControlPoints+2)

            points.SetPoint(0,posStartEnd)
            cellArray.InsertCellPoint(0)

            offset = 1

        for i in range(nOfControlPoints):
            sourceNode.GetNthFiducialPosition(i,pos)
            points.SetPoint(offset+i,pos)
            cellArray.InsertCellPoint(offset+i)

        offset = offset + nOfControlPoints

        if closed:
            points.SetPoint(offset,posStartEnd)
            cellArray.InsertCellPoint(offset)

        outputPoly.Initialize()
        outputPoly.SetPoints(points)
        outputPoly.SetLines(cellArray)

    def nodeToPolyCardinalSpline(self, sourceNode, outputPoly, closed=False):

        nOfControlPoints = sourceNode.GetNumberOfFiducials()
        pos = [0.0, 0.0, 0.0]

        # One spline for each direction.
        aSplineX = vtk.vtkCardinalSpline()
        aSplineY = vtk.vtkCardinalSpline()
        aSplineZ = vtk.vtkCardinalSpline()

        if closed:
            aSplineX.ClosedOn()
            aSplineY.ClosedOn()
            aSplineZ.ClosedOn()
        else:
            aSplineX.ClosedOff()
            aSplineY.ClosedOff()
            aSplineZ.ClosedOff()

        for i in range(0, nOfControlPoints):
            sourceNode.GetNthFiducialPosition(i, pos)
            aSplineX.AddPoint(i, pos[0])
            aSplineY.AddPoint(i, pos[1])
            aSplineZ.AddPoint(i, pos[2])

        # Interpolate x, y and z by using the three spline filters and
        # create new points
        nInterpolatedPoints = (self.interpResolution+2)*(nOfControlPoints-1) # One section is devided into self.interpResolution segments
        points = vtk.vtkPoints()
        r = [0.0, 0.0]
        aSplineX.GetParametricRange(r)
        t = r[0]
        p = 0
        tStep = (nOfControlPoints-1.0)/(nInterpolatedPoints-1.0)
        nOutputPoints = 0

        if closed:
            while t < r[1]+1.0:
                points.InsertPoint(p, aSplineX.Evaluate(t), aSplineY.Evaluate(t), aSplineZ.Evaluate(t))
                t = t + tStep
                p = p + 1
            ## Make sure to close the loop
            points.InsertPoint(p, aSplineX.Evaluate(r[0]), aSplineY.Evaluate(r[0]), aSplineZ.Evaluate(r[0]))
            p = p + 1
            points.InsertPoint(p, aSplineX.Evaluate(r[0]+tStep), aSplineY.Evaluate(r[0]+tStep), aSplineZ.Evaluate(r[0]+tStep))
            nOutputPoints = p + 1
        else:
            while t < r[1]:
                points.InsertPoint(p, aSplineX.Evaluate(t), aSplineY.Evaluate(t), aSplineZ.Evaluate(t))
                t = t + tStep
                p = p + 1
            nOutputPoints = p

        lines = vtk.vtkCellArray()
        lines.InsertNextCell(nOutputPoints)
        for i in range(0, nOutputPoints):
            lines.InsertCellPoint(i)

        outputPoly.SetPoints(points)
        outputPoly.SetLines(lines)

    def pathToPoly(self, path, poly):
        points = vtk.vtkPoints()
        cellArray = vtk.vtkCellArray()

        points = vtk.vtkPoints()
        poly.SetPoints(points)

        lines = vtk.vtkCellArray()
        poly.SetLines(lines)

        linesIDArray = lines.GetData()
        linesIDArray.Reset()
        linesIDArray.InsertNextTuple1(0)

        polygons = vtk.vtkCellArray()
        poly.SetPolys( polygons )
        idArray = polygons.GetData()
        idArray.Reset()
        idArray.InsertNextTuple1(0)

        for point in path:
            pointIndex = points.InsertNextPoint(*point)
            linesIDArray.InsertNextTuple1(pointIndex)
            linesIDArray.SetTuple1( 0, linesIDArray.GetNumberOfTuples() - 1 )
            lines.SetNumberOfCells(1)

    def calculateLineLength(self, poly):
        lines = poly.GetLines()
        points = poly.GetPoints()
        pts = vtk.vtkIdList()

        lines.GetCell(0, pts)
        ip = numpy.array(points.GetPoint(pts.GetId(0)))
        n = pts.GetNumberOfIds()

        # Check if there is overlap between the first and last segments
        # (for making sure to close the loop for spline curves)
        if n > 2:
            slp = numpy.array(points.GetPoint(pts.GetId(n-2)))
            # Check distance between the first point and the second last point
            if numpy.linalg.norm(slp-ip) < 0.00001:
                n = n - 1

        length = 0.0
        pp = ip
        for i in range(1,n):
            p = numpy.array(points.GetPoint(pts.GetId(i)))
            length = length + numpy.linalg.norm(pp-p)
            pp = p

        return length


    def updateCurve(self):

        if self.AutomaticUpdate == False:
            return

        if self.SourceNode and self.DestinationNode:

            if self.SourceNode.GetNumberOfFiducials() < 2:
                if self.CurvePoly != None:
                    self.CurvePoly.Initialize()

                self.CurveLength = 0.0

            else:

                if self.CurvePoly == None:
                    self.CurvePoly = vtk.vtkPolyData()

                if self.DestinationNode.GetDisplayNodeID() == None:
                    modelDisplayNode = slicer.vtkMRMLModelDisplayNode()
                    modelDisplayNode.SetColor(self.ModelColor)
                    slicer.mrmlScene.AddNode(modelDisplayNode)
                    self.DestinationNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())

                if self.InterpolationMethod == 0:
                    self.nodeToPoly(self.SourceNode, self.CurvePoly, False)

                elif self.InterpolationMethod == 1: # Cardinal Spline
                    self.nodeToPolyCardinalSpline(self.SourceNode, self.CurvePoly, False)

                self.CurveLength = self.calculateLineLength(self.CurvePoly)

            tubeFilter = vtk.vtkTubeFilter()

            tubeFilter.SetInputData(self.CurvePoly)
            tubeFilter.SetRadius(self.TubeRadius)
            tubeFilter.SetNumberOfSides(20)
            tubeFilter.CappingOn()
            tubeFilter.Update()

            self.DestinationNode.SetAndObservePolyData(tubeFilter.GetOutput())
            self.DestinationNode.Modified()

            if self.DestinationNode.GetScene() == None:
                slicer.mrmlScene.AddNode(self.DestinationNode)

            displayNode = self.DestinationNode.GetDisplayNode()
            if displayNode:
                displayNode.SetActiveScalarName('')
