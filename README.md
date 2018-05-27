#Welcome to Curve Editor!

This module will allow you to create curves to add to any scene

##Installation
* In Slicer, click Edit -> Application settings
* In the left hand side, click modules
* Under 'Additional module paths', click add and navigate to the directory where 'CurveEditor.py' is saved
* Restart Slicer and the module will be active

##First curve
* In the dropdown menu next to 'Modules', select 'CurveEditor' -> '3D Curve Editor'
* In 'Source points' select the source from an existing list or create a new list of fiducials
* In 'Curve model' Select a model to save the curve to, or create a new curve
* Create a set of points
    * Select the Fiducials button (blue arrow with red circle) and place in the 3D view
    * Under 'X, Y, Z Coordinates' enter desired values and click 'Add Fiducial'
* Click the 'Generate/Update Curve' button

##Editing curves
* Any fiducials position can be altered in the 3D view by clicking and dragging
* These are seen in the fiducials table when selected under 'source points'
* To delete a set of points, select them in 'Source Points' then under the same dropdown, select 'Delete Current ...'
* To delete a curve, select it in the 'Curve model' menu, then select 'Delete current ...'
* Any number of curves can be added by selecting the desired set of points and creating a new curve model
* To alter the radius, change the 'Thickness' slider
* Any curve can be switched between linear or spline be selecting the toggle under 'interpolation'
