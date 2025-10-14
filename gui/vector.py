import typing

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

import daq_utils

if typing.TYPE_CHECKING:
    from gui.control_main import ControlMain


class VectorMarkerSignals(QtCore.QObject):
    marker_pos_changed = QtCore.Signal(object)
    marker_dropped = QtCore.Signal(object)


class VectorMarker(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, *args, **kwargs) -> None:
        self.blue_color = QtCore.Qt.GlobalColor.blue
        brush = kwargs.pop("brush", QtGui.QBrush())
        pen = kwargs.pop("pen", QtGui.QPen(self.blue_color))
        self.parent: VectorWidget = kwargs.pop("parent", None)
        self.point_name = kwargs.pop("point_name", None)
        self.coords = kwargs.pop("coords")
        self.gonio_coords = kwargs.pop("gonio_coords")
        self.center_marker = kwargs.pop("center_marker")
        super().__init__(*args, **kwargs)
        self.setBrush(brush)
        self.setPen(pen)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(
            QtWidgets.QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.signals = VectorMarkerSignals()
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value) -> typing.Any:
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.signals.marker_pos_changed.emit(value)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        cursor = QtGui.QCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setCursor(cursor)
        self.signals.marker_dropped.emit(self)
        return super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event) -> None:
        cursor = QtGui.QCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setCursor(cursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.ArrowCursor))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        cursor = QtGui.QCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        self.setCursor(cursor)
        super().mousePressEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        rect = self.rect()
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black))
        if self.point_name == "vector_start":
            text = "S"
        else:
            text = "E"
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)


class VectorWidget(QtWidgets.QWidget):
    def __init__(
        self,
        main_window: "ControlMain",
        parent: "QtWidgets.QWidget | None" = None,
    ) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.vector_start: "None | VectorMarker" = None
        self.vector_end: "None | VectorMarker" = None
        self.vector_line: "None | QtWidgets.QGraphicsLineItem" = None
        self.blue_color = QtCore.Qt.GlobalColor.blue
        self.red_color = QtCore.Qt.GlobalColor.red

    def update_point(
        self,
        point: VectorMarker,
        pos_rbv: int,
        mot_id: str,
        center_marker: QtCore.QPointF,
    ) -> VectorMarker:
        """Updates a point on the screen

        Updates the position of a point (e.g. self.vector_start) drawn on the screen based on
        which motor was moved (motID) using gonio position (posRBV)
        """
        if point is None:
            return point
        centerMarkerOffsetX = point.center_marker.x() - center_marker.x()
        centerMarkerOffsetY = point.center_marker.y() - center_marker.y()
        startYY = point.coords["z"]
        startYX = point.coords["y"]
        startX = point.coords["x"]

        if mot_id == "omega":
            newY = self.main_window.calculateNewYCoordPos(startYX, startYY)
            point.setPos(point.x(), newY - centerMarkerOffsetY)
        if mot_id == "x":
            delta = startX - pos_rbv
            newX = float(self.main_window.screenXmicrons2pixels(delta))
            point.setPos(newX - centerMarkerOffsetX, point.y())
        if mot_id == "y" or mot_id == "z":
            newY = self.main_window.calculateNewYCoordPos(startYX, startYY)
            point.setPos(point.x(), newY - centerMarkerOffsetY)
        return point

    def update_vector(
        self,
        pos_rbv: int,
        mot_id: str,
        center_marker: QtCore.QPointF,
        offset: "tuple[int, int]",
    ) -> None:
        if self.vector_start is not None:
            self.vector_start = self.update_point(
                self.vector_start, pos_rbv, mot_id, center_marker
            )
        if self.vector_end is not None:
            self.vector_end = self.update_point(
                self.vector_end, pos_rbv, mot_id, center_marker
            )
        if (
            self.vector_start is not None
            and self.vector_end is not None
            and self.vector_line is not None
        ):
            self.vector_line.setLine(
                self.vector_start.x() + self.vector_start.center_marker.x() + offset[0],
                self.vector_start.y() + self.vector_start.center_marker.y() + offset[1],
                self.vector_end.x() + self.vector_start.center_marker.x() + offset[0],
                self.vector_end.y() + self.vector_start.center_marker.y() + offset[1],
            )

    def get_length(self) -> "tuple[int, int, int, np.floating[typing.Any] | float]":
        trans_total = 0.0
        x_vec = y_vec = z_vec = 0

        if self.vector_start and self.vector_end:
            vec_end = np.array(list(map(self.vector_end.coords.get, ("x", "y", "z"))))
            vec_start = np.array(
                list(map(self.vector_start.coords.get, ("x", "y", "z")))
            )

            vec_diff = vec_end - vec_start
            trans_total = np.linalg.norm(vec_diff)
            if daq_utils.beamline == "nyx":
                trans_total *= 1000

        return x_vec, y_vec, z_vec, trans_total

    def get_length_and_speed(
        self, osc_end: float, osc_range: float, exposure_time: float
    ) -> "tuple[int, int, int, np.floating[typing.Any] | float, np.floating[typing.Any] | float]":
        total_exposure_time: float = (osc_end / osc_range) * exposure_time
        x_vec, y_vec, z_vec, vector_length = self.get_length()
        speed = vector_length / total_exposure_time

        return x_vec, y_vec, z_vec, vector_length, speed

    def set_vector(
        self,
        scene: QtWidgets.QGraphicsScene,
        gonio_coords: "dict[str, typing.Any]",
        center: "tuple[float, float]",
        length=40,
    ) -> None:
        offset = int(length / 2)
        gonio_coords_start = {
            "x": gonio_coords["x"] - offset,
            "y": gonio_coords["y"],
            "z": gonio_coords["z"],
            "omega": gonio_coords["omega"],
        }
        gonio_coords_end = {
            "x": gonio_coords["x"] + offset,
            "y": gonio_coords["y"],
            "z": gonio_coords["z"],
            "omega": gonio_coords["omega"],
        }
        self.set_vector_point("vector_start", scene, gonio_coords_start, center)
        self.set_vector_point("vector_end", scene, gonio_coords_end, center)

    def set_vector_point(
        self,
        point_name: str,
        scene: QtWidgets.QGraphicsScene,
        gonio_coords: "dict[str, typing.Any]",
        center: "tuple[float, float]",
    ) -> None:
        point = getattr(self, point_name)
        if point:
            scene.removeItem(point)
            if self.vector_line:
                scene.removeItem(self.vector_line)
        if point_name == "vector_end":
            brush = QtGui.QBrush(self.red_color)
        else:
            brush = QtGui.QBrush(self.blue_color)
        point = self.setup_vector_object(
            gonio_coords,
            center,
            prev_vector_point=point,
            brush=brush,
            point_name=point_name,
        )
        setattr(self, point_name, point)
        scene.addItem(point)
        point.setZValue(2.0)
        if self.vector_start and self.vector_end:
            self.draw_vector(center, scene)

    def draw_vector(
        self, center: "tuple[float, float]", scene: QtWidgets.QGraphicsScene
    ) -> None:
        pen = QtGui.QPen(self.blue_color)

        if self.vector_start is not None and self.vector_end is not None:
            self.vector_line = scene.addLine(
                center[0] + self.vector_start.x(),
                center[1] + self.vector_start.y(),
                center[0] + self.vector_end.x(),
                center[1] + self.vector_end.y(),
                pen,
            )

    def setup_vector_object(
        self,
        gonio_coords: "dict[str, typing.Any]",
        center: "tuple[float, float]",
        prev_vector_point: "None | VectorMarker" = None,
        pen: "None | QtGui.QPen" = None,
        brush: "None | QtGui.QBrush" = None,
        point_name: "None | str" = None,
    ) -> VectorMarker:
        """Creates and returns a vector start or end point

        Places a start or end vector marker wherever the crosshair is located in
        the sample camera view and returns a dictionary of metadata related to that point

        Args:
          prev_vector_point: Dictionary of metadata related to a point being adjusted. For example,
              a previously placed vector_start point is moved, its old position is used to determine
              its new co-ordinates in 3D space
          gonio_coords: Dictionary of gonio coordinates. If not provided will retrieve current PV values
          pen: QPen object that defines the color of the point's outline
          brush: QBrush object that defines the color of the point's fill color
        Returns:
          A VectorMarker along with the following metadata
              "coords": A dictionary of tweaked x, y and z positions of the Goniometer
              "gonio_coords": A dictionary of x, y, z co-ordinates obtained from the Goniometer PVs
              "center_marker": Location of the center marker when this marker was placed
        """
        if not pen:
            pen = QtGui.QPen(self.blue_color)
        if not brush:
            brush = QtGui.QBrush(self.blue_color)
        markWidth = 10
        marker_x = center[0] - (markWidth / 2.0) - 1
        marker_y = center[1] - (markWidth / 2.0) - 1

        if prev_vector_point:
            vectorCoords = self.transform_vector_coords(
                prev_vector_point.coords, gonio_coords
            )
        else:
            vectorCoords = {
                k: v for k, v in gonio_coords.items() if k in ["x", "y", "z"]
            }

        vecMarker = VectorMarker(
            marker_x,
            marker_y,
            markWidth,
            markWidth,
            pen=pen,
            brush=brush,
            parent=self,
            point_name=point_name,
            coords=vectorCoords,
            gonio_coords=gonio_coords,
            center_marker=self.main_window.centerMarker,
        )
        vecMarker.signals.marker_dropped.connect(self.update_marker_position)
        vecMarker.signals.marker_pos_changed.connect(self.update_vector_position)
        return vecMarker

    def update_vector_position(self, value) -> None:
        if self.vector_line:
            self.main_window.scene.removeItem(self.vector_line)
            self.main_window.drawVector()

    def update_marker_position(self, point: VectorMarker) -> None:
        # First convert the distance moved by the point from pixels to microns
        micron_x = self.main_window.screenXPixels2microns(point.pos().x())
        micron_y = self.main_window.screenYPixels2microns(point.pos().y())
        omega = self.main_window.omegaRBV_pv.get()

        # Then translate the delta from microns in the lab co-ordinate system to gonio
        (
            gonio_offset_x,
            gonio_offset_y,
            gonio_offset_z,
            omega,
        ) = daq_utils.lab2gonio(micron_x, -micron_y, 0, omega)

        # Then add the delta to the current gonio co-ordinates
        gonio_coords = {
            "x": self.main_window.sampx_pv.get() + gonio_offset_x,
            "y": self.main_window.sampy_pv.get() + gonio_offset_y,
            "z": self.main_window.sampz_pv.get() + gonio_offset_z,
            "omega": omega,
        }
        vectorCoords = self.transform_vector_coords(point.coords, gonio_coords)
        point.coords = vectorCoords
        point.gonio_coords = gonio_coords

        # Update vector length and speed in the GUI after any node moves
        self.main_window.updateVectorLengthAndSpeed()

    def clear_vector(self, scene: QtWidgets.QGraphicsScene) -> None:
        if self.vector_start:
            scene.removeItem(self.vector_start)
            self.vector_start = None
        if self.vector_end:
            scene.removeItem(self.vector_end)
            self.vector_end = None
        if self.vector_line:
            scene.removeItem(self.vector_line)
            self.vector_line = None

    def transform_vector_coords(
        self, prev_coords: "dict[str, float]", current_raw_coords: "dict[str, float]"
    ) -> "dict[str, float]":
        """Updates y and z co-ordinates of vector points when they are moved

        This function tweaks the y and z co-ordinates such that when a vector start or
        end point is adjusted in the 2-D plane of the screen, it maintains the points' location
        in the 3rd dimension perpendicular to the screen

        Args:
          prev_coords: Dictionary with x,y and z co-ordinates of the previous location of the sample
          current_raw_coords: Dictionary with x, y and z co-ordinates of the sample derived from the goniometer
            PVs
          omega: Omega of the Goniometer (usually RBV)

        Returns:
          A dictionary mapping x, y and z to tweaked coordinates
        """

        # Transform z from prev point and y from current point to lab coordinate system
        _, _, zLabPrev, _ = daq_utils.gonio2lab(
            prev_coords["x"],
            prev_coords["y"],
            prev_coords["z"],
            current_raw_coords["omega"],
        )
        _, yLabCurrent, _, _ = daq_utils.gonio2lab(
            current_raw_coords["x"],
            current_raw_coords["y"],
            current_raw_coords["z"],
            current_raw_coords["omega"],
        )

        # Take y co-ordinate from current point and z-coordinate from prev point and transform back to gonio co-ordinates
        _, yTweakedCurrent, zTweakedCurrent, _ = daq_utils.lab2gonio(
            prev_coords["x"], yLabCurrent, zLabPrev, current_raw_coords["omega"]
        )
        return {
            "x": current_raw_coords["x"],
            "y": yTweakedCurrent,
            "z": zTweakedCurrent,
        }

    def hide_nodes(self):
        if self.vector_start:
            self.vector_start.setVisible(False)
        if self.vector_end:
            self.vector_end.setVisible(False)

    def show_nodes(self):
        if self.vector_start:
            self.vector_start.setVisible(True)
        if self.vector_end:
            self.vector_end.setVisible(True)
