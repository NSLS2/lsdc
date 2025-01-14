import sys
from qtpy.QtWidgets import (
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractScrollArea,
)
from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QTextOption
import csv
from pathlib import Path


def get_summary_widget(path: Path):
    """
    if path.suffix == ".csv":
        if path.exists():
            return CSVTableWidget(file_path=path)
        else:
            path = path.with_suffix(".txt")
    """
    path = path.with_suffix(".txt")
    if path.suffix == ".txt":
        return LogViewerWidget(path)
    raise Exception(f"Unknown type for summary: {path.suffix}")  

class LogViewerWidget(QWidget):
    def __init__(self, log_file, max_height=500, parent=None):
        super().__init__(parent)
        self.log_file = Path(log_file)
        self.initUI(max_height)

        self.last_position = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_log)
        self.timer.start(1000)  # Update every second

        self.auto_scroll = True  # Auto-scroll is enabled by default

    def initUI(self, max_height):
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setWordWrapMode(QTextOption.NoWrap)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        # Set the maximum height for the widget
        self.setMaximumHeight(max_height)

        # Connect the text_edit's scrollbar signal to check the position
        self.text_edit.verticalScrollBar().valueChanged.connect(
            self.check_scroll_position
        )

    def check_scroll_position(self):
        # Check if the scrollbar is at the bottom
        scroll_bar = self.text_edit.verticalScrollBar()
        if scroll_bar.value() == scroll_bar.maximum():
            self.auto_scroll = True
        else:
            self.auto_scroll = False

    def update_log(self):
        if self.log_file.exists():
            with self.log_file.open("r") as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()

                if new_lines:
                    # self.text_edit.append("".join(new_lines))
                    cursor = self.text_edit.textCursor()
                    cursor.movePosition(cursor.End)  # Move cursor to the end
                    cursor.insertText("".join(new_lines))  # Insert text directly
                    if self.auto_scroll:
                        self.text_edit.moveCursor(QTextEdit().textCursor().End)


class CSVTableWidget(QTableWidget):
    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        if not file_path:
            return
        self.file_path = Path(file_path)
        self.load_csv()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_csv)
        self.timer.start(10000)  # Update every 10 seconds

    def load_csv(self):
        """Load CSV file into the QTableWidget."""
        if not self.file_path.exists():
            print(f"{self.file_path} does not exist")
            return
        with self.file_path.open("r") as csvfile:
            reader = csv.reader(csvfile)
            data = list(reader)

        if not data:
            return

        # Set row and column count
        self.setRowCount(len(data) - 1)
        self.setColumnCount(len(data[0]))

        # Set the first row as the horizontal header
        self.setHorizontalHeaderLabels(data[0])

        # Populate the table with data
        for row_idx, row_data in enumerate(data[1:]):
            for col_idx, cell in enumerate(row_data):
                self.setItem(row_idx, col_idx, QTableWidgetItem(cell))

        # Freeze the header row
        # self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
