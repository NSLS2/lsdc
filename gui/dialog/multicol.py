from datetime import date
import logging
import typing

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

if typing.TYPE_CHECKING:
    from lsdcGui import ControlMain

from gui.widgets.heatmap_widget import HeatmapWidget
from utils.raster import determine_raster_shape, create_snake_array, peakfind_maxburn, calculate_flattened_index, get_score_vals, addMultiRequestLocation
import db_lib
import daq_utils

logger = logging.getLogger()

class MultiColDialog(QtWidgets.QDialog):

    def __init__(self, parent: "ControlMain", raster_req: dict, raster_result: dict):
        # Pass in the raster request and result for the widget to run a cell selection algorithm
        super().__init__(parent)
        self._parent = parent
        self.raster_req = raster_req
        self.raster_result = raster_result
        raster_def = raster_req["request_obj"]["rasterDef"]
        self.cell_results = raster_result["result_obj"]["rasterCellResults"]['resultObj']
        self.raster_map = raster_result["result_obj"]["rasterCellMap"]  
        score_vals = get_score_vals(self.cell_results, "spot_count_no_ice")
        self.direction, self.M, self.N = determine_raster_shape(raster_def)
        self.raster_array = create_snake_array(score_vals, self.direction, self.M, self.N)
        self.initUI(self.raster_array, self.cell_results)

    def initUI(self, data, cell_results):
        layout = QtWidgets.QGridLayout()
        self.heatmap_widget = HeatmapWidget(self._parent, data=data, cell_results=cell_results)
        threshold_label = QtWidgets.QLabel("Number of centers:")
        validator = QtGui.QIntValidator()
        self.threshold_edit = QtWidgets.QLineEdit("10")
        self.threshold_edit.setValidator(validator)
        self.calculate_centers_button = QtWidgets.QPushButton("Calculate centers")
        self.calculate_centers_button.clicked.connect(self.calculate_centers)
        self.clear_centers_button = QtWidgets.QPushButton("Clear Centers")
        self.clear_centers_button.clicked.connect(self.heatmap_widget.clear_highlights)
        
        wedge_label = QtWidgets.QLabel("Wedge:")
        self.wedge_edit = QtWidgets.QLineEdit()
        self.wedge_edit.setValidator(QtGui.QDoubleValidator())
        
        self.submit_centers_button = QtWidgets.QPushButton("Submit Centers")
        self.submit_centers_button.clicked.connect(self.submit_centers)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        layout.addWidget(self.heatmap_widget, 0, 0, 1, 4)
        layout.addWidget(threshold_label, 1, 0)
        layout.addWidget(self.threshold_edit, 1, 1)
        layout.addWidget(self.calculate_centers_button, 1, 2)
        layout.addWidget(self.clear_centers_button, 1, 3, 1, 1)

        layout.addWidget(wedge_label, 2, 0, 1, 1)
        # layout.addWidget(self.wedge_edit, 2, 1, 1, 1)

        layout.addWidget(self.submit_centers_button, 3, 0, 1, 1)
        layout.addWidget(self.cancel_button, 3, 3, 1, 1)
        self.setLayout(layout)

    def calculate_centers(self):
        self.heatmap_widget.clear_highlights()
        indices, array = peakfind_maxburn(self.raster_array, int(self.threshold_edit.text()))
        self.heatmap_widget.highlight_cells(indices)


    def submit_centers(self):
        indices = self.heatmap_widget.highlighted_patches.keys()
        for (x, y) in indices:
            flattened_index = calculate_flattened_index(x, y, self.M, self.N, self.direction)
            hitFile = self.cell_results[flattened_index]["cellMapKey"]
            hitCoords = self.raster_map[hitFile]
            parent_req_id = self.raster_result['result_obj']["parentReqID"]
            #current_omega = self._parent.gon.omega.get()
            self.addMultiRequestLocation(self.raster_result["request"], hitCoords, flattened_index, float(self._parent.osc_end_ledit.text()))
        self._parent.treeChanged_pv.put(1)
        self.accept()


    def addMultiRequestLocation(self, parentReqID, hitCoords, locIndex, wedge=None): #rough proto of what to pass here for details like how to organize data
        print(wedge)
        parentRequest = db_lib.getRequestByID(parentReqID)
        sampleID = parentRequest["sample"]

        logger.info(str(sampleID))
        logger.info(hitCoords)
        dataDirectory = parentRequest["request_obj"]['directory']+"multi_"+str(locIndex)
        runNum = parentRequest["request_obj"]['runNum']
        tempnewStratRequest = daq_utils.createDefaultRequest(sampleID)
        ss = parentRequest["request_obj"]["rasterDef"]["omega"]
        if "wedge" in parentRequest["request_obj"]:
            wedge = float(parentRequest["request_obj"]["wedge"])
        elif wedge is None:
            wedge = 10

        newReqObj = tempnewStratRequest["request_obj"]
        newReqObj["sweep_start"] = ss - wedge/2
        newReqObj["sweep_end"] = ss + wedge/2
        newReqObj["img_width"] = float(self._parent.osc_range_ledit.text())
        newReqObj["exposure_time"] = float(self._parent.exp_time_ledit.text())
        newReqObj["detDist"] = float(self._parent.detDistMotorEntry.getEntry().text())
        newReqObj["directory"] = dataDirectory  
        newReqObj["pos_x"] = hitCoords['x']
        newReqObj["pos_y"] = hitCoords['y']
        newReqObj["pos_z"] = hitCoords['z']
        newReqObj["fastDP"] = True
        newReqObj["fastEP"] = False
        newReqObj["dimple"] = False    
        newReqObj["xia2"] = False
        newReqObj["runNum"] = runNum
        newReqObj["parentReqID"] = parentReqID
        newReqObj["energy"] = self._parent.energy_pv.get()
        newReqObj["wavelength"] = daq_utils.energy2wave(newReqObj["energy"])
        print(newReqObj)
        newRequestUID = db_lib.addRequesttoSample(sampleID,newReqObj["protocol"],daq_utils.owner,newReqObj,priority=6000,proposalID=daq_utils.getProposalID())
