# Using Slicer Link

## Update a part

1. Edit the part in Onshape.
2. Click **Send / Update** in Slicer Link and wait for it to finish.
3. In your slicer's **Prepare** view, right-click the existing object and choose
   **Reload from disk**. For several parts, select their object rows together.

Check the new geometry, placement, and painted settings before printing. Stock
reload can recenter geometry when its bounds change. Updates are manual.

## Save and reopen

Save your slicer project as `.3mf`. In Slicer Link, expand **Keep the link after
reopening a saved project**, choose **Connect saved project**, then **Send / Update**.
Keep the model files the app creates beside your project.

Next time, reopen the `.3mf` in your slicer and update normally. If you move the
project, connect its new location and send again. A project file alone does not
transfer your Onshape connection to another computer.

## More parts or another slicer

Click **Change slicer or document** to reopen the guided selection. For a new,
empty slicer project, **Open selected parts again** imports the linked parts
again. It can create duplicates, so use it only when those objects are missing.

Choose one slicer window for importing. If several projects are open, this
version cannot select a particular window or plate. Slicing and printing remain
under your control.

## Close or update the app

Use **Stop local app** under **Connection & API use** before installing an update.
Keep the app's data folder and your project files. Closing the browser tab alone
leaves the app running.
