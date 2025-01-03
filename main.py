import os
import sys
import rasterio
import psycopg2
import geopandas as gpd
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMenu, QAction, QMessageBox, QDockWidget, QVBoxLayout,
    QWidget, QCheckBox, QListWidget, QListWidgetItem, QFileDialog, QDialog, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QComboBox, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QBrush, QLinearGradient


# Global variables
app = QApplication(sys.argv)
window = QMainWindow()
layers = {}
canvas = None
tocListWidget = None


def initUI():
    global canvas, tocListWidget, tocDockWidget

    # Main window setup
    window.setWindowTitle('GeoSpyTia')
    window.setGeometry(100, 100, 800, 600)

    # Menu Bar
    menubar = window.menuBar()

    # File Menu
    fileMenu = menubar.addMenu('File')
    fileMenu.addAction(create_action('New', newFile))
    fileMenu.addAction(create_action('Open', openFile))
    fileMenu.addAction(create_action('Save', saveFile))
    fileMenu.addAction(create_action('Connect To Database', connectToDatabase))
    fileMenu.addAction(create_action('Exit', window.close))

    # Geoprocessing Menu
    geoprocessingMenu = menubar.addMenu('Geoprocessing')
    geoprocessingMenu.addAction(create_action('Buffer', bufferDialog))
    geoprocessingMenu.addAction(create_action('Clip', clipDialog))
    geoprocessingMenu.addAction(create_action('Intersect', intersectDialog))

    # Toolbox Menu
    toolboxMenu = menubar.addMenu('Toolbox')
    toolboxMenu.addAction(create_action('NDVI', ndviDialog))
    toolboxMenu.addAction(create_action('NDBI', ndbiDialog))
    toolboxMenu.addAction(create_action('LST', lstDialog))
    toolboxMenu.addAction(create_action('Raster Overlay', rasterOverlayDialog))
    



    # Help Menu
    helpMenu = menubar.addMenu('Help')
    helpMenu.addAction(create_action('Read', showHelp))

    # Toolbar
    toolbar = window.addToolBar('Toolbar')
    toolbar.addAction(create_action_with_icon('New', 'icons/newfile.png', newFile))
    toolbar.addAction(create_action_with_icon('Open', 'icons/openfolder.png', openFile))
    toolbar.addAction(create_action_with_icon('Save', 'icons/save.png', saveFile))
    toolbar.addAction(create_action_with_icon('Zoom In', 'icons/zoomin.png', zoomIn))
    toolbar.addAction(create_action_with_icon('Zoom Out', 'icons/zoomout.png', zoomOut))
    
    
    # Create the "Add Data" dropdown menu
    addDataMenu = QMenu(window)
    addDataMenu.addAction(create_action('Load Data', openFile))
    addDataMenu.addAction(create_action('From Database', importFromDatabase))

    # Create the "Add Data" toolbar action with the dropdown menu
    addDataAction = QAction(QIcon('icons/adddata.png'), '', window)
    addDataAction.setMenu(addDataMenu)

    # Add the action to the toolbar
    toolbar.addAction(addDataAction)

    toolbar.addAction(create_action_with_icon('TOC', 'icons/toc.png', toggleTOC))
    toolbar.addAction(create_action_with_icon('Pan', 'icons/navigation.png', navPan))


    # TOC (Table of Contents)
    tocDockWidget = QDockWidget("Table of Contents", window)
    tocListWidget = QListWidget()
    tocDockWidget.setWidget(tocListWidget)
    window.addDockWidget(Qt.LeftDockWidgetArea, tocDockWidget)
    tocListWidget.setContextMenuPolicy(Qt.CustomContextMenu)
    tocListWidget.customContextMenuRequested.connect(showContextMenu)

    # Canvas for map display
    canvas = FigureCanvas(Figure())
    centralWidget = QWidget()
    layout = QVBoxLayout()
    layout.addWidget(canvas)
    centralWidget.setLayout(layout)
    window.setCentralWidget(centralWidget)

    # Show window
    window.show()

def toggleTOC():
    if tocDockWidget.isHidden():
        tocDockWidget.show()
    

def addData():
    dialog = QDialog(window)
    dialog.setWindowTitle("Add Data")

    layout = QFormLayout(dialog)

    # Data source selection
    sourceLabel = QLabel("Data Source:")
    sourceComboBox = QComboBox()
    sourceComboBox.addItems(["Raster", "Vector"])
    layout.addRow(sourceLabel, sourceComboBox)

    # File selection
    fileLabel = QLabel("File:")
    fileLineEdit = QLineEdit()
    fileBrowseButton = QPushButton("Browse")
    fileBrowseButton.clicked.connect(lambda: browseFile(fileLineEdit, 'All Files (*)'))
    layout.addRow(fileLabel, fileLineEdit)
    layout.addRow("", fileBrowseButton)

    # Import button
    importButton = QPushButton("Import")
    importButton.clicked.connect(lambda: importData(sourceComboBox.currentText(), fileLineEdit.text()))
    
    layout.addRow("", importButton)

    dialog.setLayout(layout)
    dialog.exec_()


def importData(dataType, filePath):
    if dataType == "Raster":
        loadRaster(filePath)
    elif dataType == "Vector":
        loadVector(filePath)
    else:
        QMessageBox.warning(window, 'Unsupported Data Type', 'Unsupported data type selected!')


def create_action(name, func):
    action = QAction(name, window)
    action.triggered.connect(func)
    return action


def create_action_with_icon(name, icon_path, func):
    action = QAction(QIcon(icon_path), name, window)
    action.triggered.connect(func)
    return action


def newFile():
    global layers
    reply = QMessageBox.question(window, 'New File', 'Are you sure you want to create a new file? Unsaved changes will be lost.', QMessageBox.Yes | QMessageBox.No)
    if reply == QMessageBox.No:
        return
    tocListWidget.clear()
    layers.clear()
    updateDisplay()
    QMessageBox.information(window, 'New File', 'New file created!')


def openFile():
    filePath, _ = QFileDialog.getOpenFileName(window, 'Open File', '', 
                                              'Raster Files (*.tif *.tiff *.img);;Vector Files (*.shp);;All Files (*)')
    if filePath:
        if filePath.endswith(('.tif', '.tiff', '.img')):
            loadRaster(filePath)
        elif filePath.endswith('.shp'):
            loadVector(filePath)
        else:
            QMessageBox.warning(window, 'Unsupported Format', 'Unsupported file format!')


def saveFile():
    filePath, _ = QFileDialog.getSaveFileName(window, 'Save File', '', 
                                              'Raster Files (*.tif *.tiff *.img);;Vector Files (*.shp);;All Files (*)')
    if filePath:
        try:
            for layer_data in layers.values():
                if layer_data['type'] == 'raster':
                    np.save(filePath, layer_data['data'])
                elif layer_data['type'] == 'vector':
                    layer_data['data'].to_file(filePath)
            QMessageBox.information(window, 'Save File', 'File saved successfully!')
        except Exception as e:
            QMessageBox.critical(window, 'Save File', f'Failed to save file: {e}')


def loadRaster(filePath):
    global layers
    with rasterio.open(filePath) as src:
        data = src.read(1)
        layers[os.path.basename(filePath)] = {'type': 'raster', 'data': data}
        updateTOC()


def loadVector(filePath):
    global layers
    gdf = gpd.read_file(filePath)
    layers[os.path.basename(filePath)] = {'type': 'vector', 'data': gdf}
    updateTOC()




def updateTOC():
    tocListWidget.clear()
    for layer_name, layer_data in layers.items():
        # Create a list widget item
        item = QListWidgetItem()

        # Create a custom widget to hold the checkbox, legend, and layer name
        widget = QWidget()
        layout = QHBoxLayout()

        # Create a checkbox to toggle layer visibility
        checkbox = QCheckBox(layer_name)
        checkbox.setChecked(True)
        checkbox.stateChanged.connect(lambda state, name=layer_name: toggleLayer(state, name))
        layout.addWidget(checkbox)

        # Add a color legend
        colorLabel = QLabel()
        colorLabel.setFixedSize(100, 20)  # Adjust size for better visibility

        if layer_data['type'] == 'raster':
            # Create a gradient pixmap for raster
            pixmap = QPixmap(colorLabel.size())
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            gradient = QLinearGradient(0, 0, colorLabel.width(), 0)
            gradient.setColorAt(0.0, Qt.red)
            gradient.setColorAt(0.33, Qt.yellow)
            gradient.setColorAt(0.66, Qt.green)
            gradient.setColorAt(1.0, Qt.blue)
            painter.fillRect(pixmap.rect(), QBrush(gradient))
            painter.end()
            colorLabel.setPixmap(pixmap)

        elif layer_data['type'] == 'vector':
            # Use a solid color for vector legend
            colorLabel.setStyleSheet("background-color: blue;")

        layout.addWidget(colorLabel)

        # Ensure alignment and spacing are neat
        layout.setAlignment(Qt.AlignLeft)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        widget.setLayout(layout)

        # Add the widget to the TOC list
        tocListWidget.addItem(item)
        tocListWidget.setItemWidget(item, widget)

    updateDisplay()



def showContextMenu(pos):
    contextMenu = QMenu(window)
    removeLayerAct = QAction('Remove Layer', window)
    removeLayerAct.triggered.connect(removeLayer)
    contextMenu.addAction(removeLayerAct)
    contextMenu.exec_(tocListWidget.mapToGlobal(pos))

def removeLayer():
    currentRow = tocListWidget.currentRow()
    if currentRow >= 0:
        item = tocListWidget.takeItem(currentRow)
        layerName = item.text()
        if layerName in layers:
            del layers[layerName]

        # Clear the map display
        updateDisplay()
        QMessageBox.information(window, 'Remove Layer', 'Layer removed successfully!')


def toggleLayer(state, layerName):
    updateDisplay()


def updateDisplay():
    ax = canvas.figure.gca()
    ax.clear()
    norm = Normalize()

    for item_index in range(tocListWidget.count() - 1, -1, -1):  # Iterate from topmost to bottom
        item = tocListWidget.item(item_index)
        widget = tocListWidget.itemWidget(item)
        checkbox = widget.findChild(QCheckBox)
        layer_name = checkbox.text()
        if checkbox.isChecked() and layer_name in layers:
            layer = layers[layer_name]
            if layer['type'] == 'raster':
                im = ax.imshow(layer['data'], cmap='Spectral', norm=norm)
                # Add color bar
                if not hasattr(canvas, 'cbar'):
                    canvas.cbar = canvas.figure.colorbar(im, ax=ax, orientation='vertical')
                else:
                    canvas.cbar.update_normal(im)
                canvas.cbar.set_label('Value')
            elif layer['type'] == 'vector':
                layer['data'].plot(ax=ax, edgecolor='blue', facecolor='none')
            break  # Display only the uppermost checked layer

    ax.set_aspect('equal')
    ax.axis('off')
    canvas.draw()



def navPan():
    if not hasattr(window, 'nav_toolbar'):
        window.nav_toolbar = NavigationToolbar2QT(canvas, window)
        window.addToolBar(window.nav_toolbar)
    if window.nav_toolbar.isVisible():
        window.nav_toolbar.hide()
    else:
        window.nav_toolbar.show()
    window.nav_toolbar.pan()
    canvas.draw()


def wheelEvent(event):
    ax = canvas.figure.gca()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    
    # Get the mouse position in data coordinates
    xdata = event.pos().x()
    ydata = event.pos().y()
    inv = ax.transData.inverted()
    xdata, ydata = inv.transform((xdata, ydata))
    
    # Calculate zoom factor
    zoom_factor = 0.1
    if event.angleDelta().y() > 0:
        scale_factor = 1 - zoom_factor
    else:
        scale_factor = 1 + zoom_factor
    
    # Adjust the limits based on the mouse position
    new_xlim = [xdata - (xdata - xlim[0]) * scale_factor, xdata + (xlim[1] - xdata) * scale_factor]
    new_ylim = [ydata - (ydata - ylim[0]) * scale_factor, ydata + (ylim[1] - ydata) * scale_factor]
    
    ax.set_xlim(new_xlim)
    ax.set_ylim(new_ylim)
    canvas.draw()

window.wheelEvent = wheelEvent



def zoomIn():
    ax = canvas.figure.gca()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    ax.set_xlim([xlim[0] + (xlim[1] - xlim[0]) * 0.1, xlim[1] - (xlim[1] - xlim[0]) * 0.1])
    ax.set_ylim([ylim[0] + (ylim[1] - ylim[0]) * 0.1, ylim[1] - (ylim[1] - ylim[0]) * 0.1])
    canvas.draw()

def zoomOut():
    ax = canvas.figure.gca()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    ax.set_xlim([xlim[0] - (xlim[1] - xlim[0]) * 0.1, xlim[1] + (xlim[1] - xlim[0]) * 0.1])
    ax.set_ylim([ylim[0] - (ylim[1] - ylim[0]) * 0.1, ylim[1] + (ylim[1] - ylim[0]) * 0.1])
    canvas.draw()






def bufferDialog():
    dialog = QDialog(window)
    dialog.setWindowTitle("Buffer Tool")
    layout = QFormLayout(dialog)

    # Input vector file
    inputLabel = QLabel("Input Vector File:")
    inputLineEdit = QLineEdit()
    inputBrowseButton = QPushButton("Browse")
    inputBrowseButton.clicked.connect(lambda: browseFile(inputLineEdit, 'Vector Files (*.shp)'))

    # Output file
    outputLabel = QLabel("Output File:")
    outputLineEdit = QLineEdit()
    outputBrowseButton = QPushButton("Browse")
    outputBrowseButton.clicked.connect(lambda: browseFile(outputLineEdit, 'Vector Files (*.shp)', save=True))

    # Buffer distance
    distanceLabel = QLabel("Buffer Distance:")
    distanceLineEdit = QLineEdit()

    # Add components to the dialog layout
    calculateButton = QPushButton("Calculate Buffer")
    calculateButton.clicked.connect(
        lambda: calculateBuffer(inputLineEdit.text(), outputLineEdit.text(), distanceLineEdit.text())
    )

    layout.addRow(inputLabel, inputLineEdit)
    layout.addRow("", inputBrowseButton)
    layout.addRow(outputLabel, outputLineEdit)
    layout.addRow("", outputBrowseButton)
    layout.addRow(distanceLabel, distanceLineEdit)
    layout.addRow("", calculateButton)

    dialog.setLayout(layout)
    dialog.exec_()


def calculateBuffer(inputPath, outputPath, distance):
    try:
        distance = float(distance)
        gdf = gpd.read_file(inputPath)
        gdf['geometry'] = gdf.buffer(distance)
        gdf.to_file(outputPath)
        QMessageBox.information(window, "Success", "Buffer created successfully!")
        loadVector(outputPath)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Buffer operation failed: {e}")


def clipDialog():
    dialog = QDialog(window)
    dialog.setWindowTitle("Clip Tool")
    layout = QFormLayout(dialog)

    # Input files
    inputLabel = QLabel("Input Vector File:")
    inputLineEdit = QLineEdit()
    inputBrowseButton = QPushButton("Browse")
    inputBrowseButton.clicked.connect(lambda: browseFile(inputLineEdit, 'Vector Files (*.shp)'))

    clipLabel = QLabel("Clip Layer File:")
    clipLineEdit = QLineEdit()
    clipBrowseButton = QPushButton("Browse")
    clipBrowseButton.clicked.connect(lambda: browseFile(clipLineEdit, 'Vector Files (*.shp)'))

    # Output file
    outputLabel = QLabel("Output File:")
    outputLineEdit = QLineEdit()
    outputBrowseButton = QPushButton("Browse")
    outputBrowseButton.clicked.connect(lambda: browseFile(outputLineEdit, 'Vector Files (*.shp)', save=True))

    calculateButton = QPushButton("Clip Layers")
    calculateButton.clicked.connect(
        lambda: calculateClip(inputLineEdit.text(), clipLineEdit.text(), outputLineEdit.text())
    )

    layout.addRow(inputLabel, inputLineEdit)
    layout.addRow("", inputBrowseButton)
    layout.addRow(clipLabel, clipLineEdit)
    layout.addRow("", clipBrowseButton)
    layout.addRow(outputLabel, outputLineEdit)
    layout.addRow("", outputBrowseButton)
    layout.addRow("", calculateButton)

    dialog.setLayout(layout)
    dialog.exec_()


def calculateClip(inputPath, clipPath, outputPath):
    try:
        input_gdf = gpd.read_file(inputPath)
        clip_gdf = gpd.read_file(clipPath)
        clipped_gdf = gpd.clip(input_gdf, clip_gdf)
        clipped_gdf.to_file(outputPath)
        QMessageBox.information(window, "Success", "Clip operation completed!")
        loadVector(outputPath)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Clip operation failed: {e}")


def intersectDialog():
    dialog = QDialog(window)
    dialog.setWindowTitle("Intersect Tool")
    layout = QFormLayout(dialog)

    # Input files
    inputLabel1 = QLabel("Input Layer 1:")
    inputLineEdit1 = QLineEdit()
    inputBrowseButton1 = QPushButton("Browse")
    inputBrowseButton1.clicked.connect(lambda: browseFile(inputLineEdit1, 'Vector Files (*.shp)'))

    inputLabel2 = QLabel("Input Layer 2:")
    inputLineEdit2 = QLineEdit()
    inputBrowseButton2 = QPushButton("Browse")
    inputBrowseButton2.clicked.connect(lambda: browseFile(inputLineEdit2, 'Vector Files (*.shp)'))

    # Output file
    outputLabel = QLabel("Output File:")
    outputLineEdit = QLineEdit()
    outputBrowseButton = QPushButton("Browse")
    outputBrowseButton.clicked.connect(lambda: browseFile(outputLineEdit, 'Vector Files (*.shp)', save=True))

    calculateButton = QPushButton("Calculate Intersection")
    calculateButton.clicked.connect(
        lambda: calculateIntersect(inputLineEdit1.text(), inputLineEdit2.text(), outputLineEdit.text())
    )

    layout.addRow(inputLabel1, inputLineEdit1)
    layout.addRow("", inputBrowseButton1)
    layout.addRow(inputLabel2, inputLineEdit2)
    layout.addRow("", inputBrowseButton2)
    layout.addRow(outputLabel, outputLineEdit)
    layout.addRow("", outputBrowseButton)
    layout.addRow("", calculateButton)

    dialog.setLayout(layout)
    dialog.exec_()


def calculateIntersect(inputPath1, inputPath2, outputPath):
    try:
        gdf1 = gpd.read_file(inputPath1)
        gdf2 = gpd.read_file(inputPath2)
        intersected_gdf = gpd.overlay(gdf1, gdf2, how="intersection")
        intersected_gdf.to_file(outputPath)
        QMessageBox.information(window, "Success", "Intersection operation completed!")
        loadVector(outputPath)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Intersection operation failed: {e}")


def ndviDialog():
    performRasterCalculation("NDVI", calculateNDVI)


def ndbiDialog():
    performRasterCalculation("NDBI", calculateNDBI)


def lstDialog():
    performRasterCalculation("LST", calculateLST)


def performRasterCalculation(toolName, calculationFunc):
    dialog = QDialog(window)
    dialog.setWindowTitle(f"{toolName} Tool")
    layout = QFormLayout(dialog)

    # Input raster file
    rasterLabel = QLabel("Input Raster File:")
    rasterLineEdit = QLineEdit()
    rasterBrowseButton = QPushButton("Browse")
    rasterBrowseButton.clicked.connect(lambda: browseFile(rasterLineEdit, 'Raster Files (*.tif *.tiff *.img)'))

    # Band inputs
    bandLabel1 = QLabel("Band 1:")
    bandLineEdit1 = QLineEdit()

    bandLabel2 = QLabel("Band 2:")
    bandLineEdit2 = QLineEdit()

    # Output file
    outputLabel = QLabel("Output File:")
    outputLineEdit = QLineEdit()
    outputBrowseButton = QPushButton("Browse")
    outputBrowseButton.clicked.connect(lambda: browseFile(outputLineEdit, 'Raster Files (*.tif *.tiff)', save=True))

    calculateButton = QPushButton(f"Calculate {toolName}")
    calculateButton.clicked.connect(
        lambda: calculationFunc(rasterLineEdit.text(), bandLineEdit1.text(), bandLineEdit2.text(), outputLineEdit.text())
    )

    layout.addRow(rasterLabel, rasterLineEdit)
    layout.addRow("", rasterBrowseButton)
    layout.addRow(bandLabel1, bandLineEdit1)
    layout.addRow(bandLabel2, bandLineEdit2)
    layout.addRow(outputLabel, outputLineEdit)
    layout.addRow("", outputBrowseButton)
    layout.addRow("", calculateButton)

    dialog.setLayout(layout)
    dialog.exec_()


def calculateNDVI(rasterFile, redBand, nirBand, outputFile):
    calculateRasterIndex(rasterFile, redBand, nirBand, outputFile, lambda nir, red: (nir - red) / (nir + red))


def calculateNDBI(rasterFile, swirBand, nirBand, outputFile):
    calculateRasterIndex(rasterFile, swirBand, nirBand, outputFile, lambda swir, nir: (swir - nir) / (swir + nir))


def calculateLST(rasterFile, thermalBand, _, outputFile):
    calculateRasterIndex(rasterFile, thermalBand, None, outputFile, lambda t, _: (t * 0.00341802 + 149)-273.15)


def rasterOverlayDialog():
    dialog = QDialog(window)
    dialog.setWindowTitle("Raster Overlay Tool")
    layout = QFormLayout(dialog)

    # Input raster files
    lstLabel = QLabel("Land Surface Temperature (LST) File:")
    lstLineEdit = QLineEdit()
    lstBrowseButton = QPushButton("Browse")
    lstBrowseButton.clicked.connect(lambda: browseFile(lstLineEdit, 'Raster Files (*.tif *.tiff *.img)'))

    ndviLabel = QLabel("Normalized Difference Vegetation Index (NDVI) File:")
    ndviLineEdit = QLineEdit()
    ndviBrowseButton = QPushButton("Browse")
    ndviBrowseButton.clicked.connect(lambda: browseFile(ndviLineEdit, 'Raster Files (*.tif *.tiff *.img)'))

    ndbiLabel = QLabel("Normalized Difference Built-up Index (NDBI) File:")
    ndbiLineEdit = QLineEdit()
    ndbiBrowseButton = QPushButton("Browse")
    ndbiBrowseButton.clicked.connect(lambda: browseFile(ndbiLineEdit, 'Raster Files (*.tif *.tiff *.img)'))

    # Output file
    outputLabel = QLabel("Output File:")
    outputLineEdit = QLineEdit()
    outputBrowseButton = QPushButton("Browse")
    outputBrowseButton.clicked.connect(lambda: browseFile(outputLineEdit, 'Raster Files (*.tif *.tiff)', save=True))

    calculateButton = QPushButton("Calculate Overlay")
    calculateButton.clicked.connect(
        lambda: calculateOverlay(lstLineEdit.text(), ndviLineEdit.text(), ndbiLineEdit.text(), outputLineEdit.text())
    )

    layout.addRow(lstLabel, lstLineEdit)
    layout.addRow("", lstBrowseButton)
    layout.addRow(ndviLabel, ndviLineEdit)
    layout.addRow("", ndviBrowseButton)
    layout.addRow(ndbiLabel, ndbiLineEdit)
    layout.addRow("", ndbiBrowseButton)
    layout.addRow(outputLabel, outputLineEdit)
    layout.addRow("", outputBrowseButton)
    layout.addRow("", calculateButton)

    dialog.setLayout(layout)
    dialog.exec_()


def calculateOverlay(lstFile, ndviFile, ndbiFile, outputFile):
    try:
        with rasterio.open(lstFile) as lst_src, rasterio.open(ndviFile) as ndvi_src, rasterio.open(ndbiFile) as ndbi_src:
            lst_data = lst_src.read(1).astype(np.float32)
            ndvi_data = ndvi_src.read(1).astype(np.float32)
            ndbi_data = ndbi_src.read(1).astype(np.float32)
            
            # Example UHI calculation (this is a placeholder, replace with actual calculation)
            uhi_data = lst_data - (ndvi_data + ndbi_data) / 2
            
            profile = lst_src.profile
            profile.update(dtype=rasterio.float32)
            
            with rasterio.open(outputFile, 'w', **profile) as dst:
                dst.write(uhi_data, 1)
        
        QMessageBox.information(window, "Success", f"UHI calculation completed: {outputFile}")
        loadRaster(outputFile)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"UHI calculation failed: {e}")

def calculateRasterIndex(rasterFile, band1, band2, outputFile, calculation):
    try:
        band1, band2 = int(band1), int(band2) if band2 else None
        with rasterio.open(rasterFile) as src:
            data1 = src.read(band1).astype(np.float32)
            data2 = src.read(band2).astype(np.float32) if band2 else None
            result = calculation(data1, data2)
            profile = src.profile
            profile.update(dtype=rasterio.float32)

            with rasterio.open(outputFile, 'w', **profile) as dst:
                dst.write(result, 1)

        QMessageBox.information(window, "Success", f"Calculation completed: {outputFile}")
        loadRaster(outputFile)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Calculation failed: {e}")


def browseFile(lineEdit, fileFilter, save=False):
    dialogFunc = QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
    filePath, _ = dialogFunc(window, "Select File", "", fileFilter)
    if filePath:
        lineEdit.setText(filePath)


def connectToDatabase():
    dialog = QDialog(window)
    dialog.setWindowTitle("Connect to Database")

    layout = QFormLayout(dialog)

    # Database connection fields
    hostLabel = QLabel("Host:")
    hostLineEdit = QLineEdit()
    layout.addRow(hostLabel, hostLineEdit)

    portLabel = QLabel("Port:")
    portLineEdit = QLineEdit()
    layout.addRow(portLabel, portLineEdit)

    dbLabel = QLabel("Database:")
    dbLineEdit = QLineEdit()
    layout.addRow(dbLabel, dbLineEdit)

    userLabel = QLabel("User:")
    userLineEdit = QLineEdit()
    layout.addRow(userLabel, userLineEdit)

    passLabel = QLabel("Password:")
    passLineEdit = QLineEdit()
    passLineEdit.setEchoMode(QLineEdit.Password)
    layout.addRow(passLabel, passLineEdit)

    # Connect button
    connectButton = QPushButton("Connect")
    connectButton.clicked.connect(lambda: connectDatabase(
        hostLineEdit.text(),
        portLineEdit.text(),
        dbLineEdit.text(),
        userLineEdit.text(),
        passLineEdit.text()
    ))
    layout.addRow("", connectButton)

    dialog.setLayout(layout)
    dialog.exec_()


def connectDatabase(host, port, database, user, password):
    try:
        global dbConnection
        dbConnection = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        QMessageBox.information(window, "Success", "Connected to the database successfully!")
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Failed to connect to the database:\n{e}")


def importFromDatabase():
    if not 'dbConnection' in globals() or dbConnection.closed:
        QMessageBox.warning(window, "Database Error", "Please connect to a database first!")
        return

    dialog = QDialog(window)
    dialog.setWindowTitle("Import from Database")

    layout = QFormLayout(dialog)

    # Table selection
    tableLabel = QLabel("Table Name:")
    tableLineEdit = QLineEdit()
    layout.addRow(tableLabel, tableLineEdit)

    # Import button
    importButton = QPushButton("Import")
    importButton.clicked.connect(lambda: loadDataFromDatabase(tableLineEdit.text()))
    layout.addRow("", importButton)

    dialog.setLayout(layout)
    dialog.exec_()


def loadDataFromDatabase(tableName):
    if not tableName:
        QMessageBox.warning(window, "Input Error", "Table name cannot be empty!")
        return

    try:
        query = f"SELECT * FROM {tableName}"
        gdf = gpd.read_postgis(query, dbConnection, geom_col="geom")
        layers[tableName] = {"type": "vector", "data": gdf}
        updateTOC()
        QMessageBox.information(window, "Success", f"Data imported from table: {tableName}")
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Failed to import data:\n{e}")



def showHelp():
    QMessageBox.information(window, "Help", "This is a simple GIS application. Use the File menu to open, save, or connect to a database. The Geoprocessing menu contains tools for buffer, clip, and intersect operations. The Toolbox menu contains tools for NDVI, NDBI,LST, Raster Overlay calculations.")



# Initialize and run the application
initUI()
sys.exit(app.exec_())
