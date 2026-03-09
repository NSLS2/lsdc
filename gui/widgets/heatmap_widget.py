from qtpy.QtWidgets import (
    QSizePolicy,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1 import make_axes_locatable
from utils.raster import calculate_flattened_index, determine_raster_shape, get_score_vals
import numpy as np
from typing import Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from lsdcGui import ControlMain

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        self.colorbar = None


class HeatmapWidget(MplCanvas):
    def __init__(self, parent: "ControlMain", width=5, height=4, dpi=100, data=None, cell_results=None):
        super().__init__(parent, width, height, dpi)
        self.mpl_connect("button_press_event", self.on_click)
        self.mpl_connect("motion_notify_event", self.on_hover)
        self._parent = parent
        self.data = data
        self.cell_results = cell_results
        self.highlighted_patches = {}
        self.render_heatmap()

    def render_heatmap(self):
        if self.data is None:
            return

        # Create the heatmap
        cax = self.axes.imshow(self.data, cmap="inferno", origin="upper")

        y_ticks = np.arange(self.data.shape[0])
        x_ticks = np.arange(self.data.shape[1])

        # Label offset: adjust ticks to be between points
        self.axes.set_xticks(x_ticks)
        self.axes.set_yticks(y_ticks)

        self.axes.set_xlim([x_ticks[0] - 0.5, x_ticks[-1] + 0.5])
        self.axes.set_ylim([y_ticks[-1] + 0.5, y_ticks[0] - 0.5])

        divider = make_axes_locatable(self.axes)
        cax_cb = divider.append_axes(
            "right", size="5%", pad=0.05
        )  # Adjust size and padding as needed
        self.colorbar = self.figure.colorbar(cax, cax=cax_cb)

        # Create a text annotation for the tooltip, initially hidden
        self.tooltip = self.axes.text(
            -2.5,
            0.95,
            "",
            color="white",
            backgroundcolor="black",
            ha="center",
            va="center",
            fontsize=10,
            bbox=dict(facecolor="black", alpha=0.8),
        )
        self.tooltip.set_visible(False)

        # Create a rectangle for highlighting cells, initially hidden
        self.highlight = Rectangle(
            (0, 0), 1, 1, linewidth=2, edgecolor="white", facecolor="none"
        )
        self.axes.add_patch(self.highlight)
        self.highlight.set_visible(False)

        # Redraw the canvas
        self.draw()
        self.figure.tight_layout()

    def on_click(self, event):
        if self.data is None or event.inaxes is None:
            return
        x, y = int(round(event.xdata)), int(round(event.ydata))
        col, row = int(np.floor(x)), int(np.floor(y))
        if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
            value = self.data[row, col]
            if event.dblclick:
                self.highlight_patch(row, col)
            else:
                self.show_diffraction_image(row, col)

    def show_diffraction_image(self, row, col):
        if not self.cell_results:
            return
        flattened_index = calculate_flattened_index(row, col, self.data.shape[0], self.data.shape[1])
        cell_filename = self.cell_results[flattened_index].get("image")
        if not cell_filename:
            return
        self._parent.albulaInterface.open_file(cell_filename)


    def highlight_patch(self, row, col):
        if (row, col) in self.highlighted_patches:
            patch = self.highlighted_patches.pop((row, col))
            patch.remove()
        else:
            rect = Rectangle(
                (col - 0.5, row - 0.5),
                1,
                1,
                linewidth=2,
                edgecolor="green",
                facecolor="none"
            )
            self.axes.add_patch(rect)
            self.highlighted_patches[(row, col)] = rect
        self.draw_idle()  # Redraw the canvas
        

    def on_hover(self, event):
        """Display a tooltip with the intensity value at the mouse position."""
        if self.data is None:
            return

        matrix = self.data
        # Check if the mouse is over the axes
        if event.inaxes == self.axes:
            # Get the row and column indices
            #x, y = event.xdata, event.ydata
            x, y = int(round(event.xdata)), int(round(event.ydata))
            col, row = int(np.floor(x)), int(np.floor(y))

            # Check if the indices are within the bounds of the matrix
            if 0 <= row < matrix.shape[0] and 0 <= col < matrix.shape[1]:
                # Get the intensity of the current cell
                intensity = matrix[row, col]

                # Update the position and text of the tooltip
                # self.tooltip.set_position((col+5, row+5))
                self.tooltip.set_text(f"({row}, {col})\nSpot Count: {intensity:.2f}")
                self.tooltip.set_visible(True)

                # Update the position of the highlight rectangle
                self.highlight.set_bounds(col - 0.5, row - 0.5, 1, 1)
                self.highlight.set_visible(True)
            else:
                # Hide the tooltip and highlight if outside the matrix
                self.tooltip.set_visible(False)
                self.highlight.set_visible(False)
        else:
            # Hide the tooltip and highlight if the mouse is outside the axes
            self.tooltip.set_visible(False)
            self.highlight.set_visible(False)

        self.draw_idle()  # Redraw the canvas

    def highlight_cells(self, indices: "list[Tuple[float, float]]"):
        for (i, j) in indices:
            rect = Rectangle(
                (j - 0.5, i - 0.5),
                1,
                1,
                linewidth=2,
                edgecolor="green",
                facecolor="none"
            )
            self.axes.add_patch(rect)
            self.highlighted_patches[(i, j)] = rect
        self.draw_idle()

    def clear_highlights(self):
        for key in list(self.highlighted_patches):
            patch = self.highlighted_patches.pop(key)
            patch.remove()
        self.draw_idle()
