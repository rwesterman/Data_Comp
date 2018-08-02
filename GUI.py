import logging
import sys
import threading
import multiprocessing

import time

from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication, QWidget, QFrame, QGridLayout, QFileDialog, QCheckBox, QPushButton
from PyQt5.QtWidgets import QLabel, QMessageBox, QTextEdit
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5 import sip

import compile_data
import config

class App(QWidget):
    def __init__(self, log_q):
        super().__init__()
        self.log_q = log_q

        # Will be a QLabel object when set
        self.dirpath = ""

        self.threadlog = compile_data.LogThread(self.log_q)
        self.threadlog.log.connect(self.output_logs)

        # create a new thread to output in real time
        t = threading.Thread(target=self.loop_logger)
        t.start()

        # Initialize the text logger so that output is displayed when the GUI is run
        self.init_logger()

        # Set up grid layout. Size hint might not be necessary
        self.grid = QGridLayout()
        self.grid.sizeHint()
        self.left_frame = QFrame()

        self.blank = QLabel("")

        self.pow_vs_bw = QCheckBox("Power vs Bandwidth")
        self.temp_vs_bw = QCheckBox("NAND Temp vs Bandwidth")
        self.temp_vs_amb = QCheckBox("NAND Temp vs Ambient")

        self.folder_label = QLabel("Select the top-level folder where data is stored:")
        self.folder = QPushButton("Select Folder...")

        self.run = QPushButton("Compile Data and Create Plots")
        self.initUI()

        self.init_grid()

        self.folder.clicked.connect(self.openFolderDialog)

        self.pow_vs_bw.clicked.connect(self.update_checks)
        self.temp_vs_bw.clicked.connect(self.update_checks)
        self.temp_vs_amb.clicked.connect(self.update_checks)

        self.run.clicked.connect(self.start_run)

        self.show()

    def init_logger(self):
        # self.log_text_box = QTextEditLogger(self)
        self.text_edit = QTextEdit()
        # logging.getLogger().addHandler(self.log_text_box)
        # logging.getLogger().setLevel(logging.INFO)

    def init_grid(self):
        self.grid.setColumnMinimumWidth(10, 10)
        self.grid.setRowMinimumHeight(1, 1)
        self.grid.setVerticalSpacing(5)

        self.grid.addWidget(self.blank, 0, 1)
        self.grid.addWidget(self.folder_label, 0, 0)
        self.grid.addWidget(self.folder, 1, 0)

        self.grid.addWidget(QLabel("Select which plots to output from data:"), 2, 0)
        self.grid.addWidget(self.pow_vs_bw, 3, 0)
        self.grid.addWidget(self.temp_vs_bw, 4, 0)
        self.grid.addWidget(self.temp_vs_amb, 5, 0)

        self.grid.addWidget(self.run, 6, 0)

        # Create empty space in between input options and output log
        self.grid.addWidget(self.blank, 0, 1, 7, 1)

        self.grid.addWidget(QLabel("Output Log:"), 0, 2)
        self.grid.addWidget(self.text_edit, 1, 2, 6, 1)
        # self.grid.addWidget(self.log_text_box.widget, 1, 2, 6, 1)

        self.grid.setColumnStretch(0, 5)

        self.setLayout(self.grid)
        self.grid.setSizeConstraint(self.grid.SetFixedSize)

    def initUI(self):
        self.title = "8267 Thermal Data Compilation"
        self.left = 100
        self.top = 100
        self.width = 640
        self.height = 480

        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Default to all plots being checked
        self.pow_vs_bw.setChecked(True)
        self.temp_vs_bw.setChecked(True)
        self.temp_vs_amb.setChecked(True)

        self.folder.setChecked(False)

    def update_checks(self):
        """Updates self.tkwargs to the new value of checkboxes"""
        self.tkwargs = {"plot_power": self.pow_vs_bw.isChecked(), "plot_throttle": self.temp_vs_bw.isChecked(),
                   "plot_temps": self.temp_vs_amb.isChecked(), "dirpath": self.dirpath}

    def openFolderDialog(self):
        # figure out how to attach this to a button
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.dirpath = str(QFileDialog.getExistingDirectory(self, "Select Directory", options=options))
        if self.dirpath:
            # config.log_q.put("Top level folder:\n{}".format(self.dirpath))
            self.log_q.put("Top level folder:\n{}".format(self.dirpath))
            # logging.info("Top level folder:\n{}".format(self.dirpath))

    @pyqtSlot(str)
    def output_logs(self, msg):

        if msg == "Running..." or msg == "Finished!":
            msg = '<font color="blue">{}</font>'.format(msg)
        elif "ERROR" in msg.upper():
            msg = '<font color="red">{}</font>'.format(msg)
        else:
            msg = '<font color="black">{}</font>'.format(msg)

        # Move cursor to the end of the text block. This will prevent users from accidentally moving the cursor
        # self.widget.moveCursor(QTextCursor.End)
        self.text_edit.insertHtml(msg)
        # Add a newline after every output to make the wrapped text more readable
        self.text_edit.append("\n")

    def loop_logger(self):
        # Run this forever while main program is running. Should work?
        # loop flag is set from the main thread to determine when to stop looping for queue log
        config.dbglog.debug("Entering loop logger")

        # printonce = True
        looping = True
        while looping:
            time.sleep(0.1)
            # Get flag from thread_logger. This will return false when it receives None as a message
            looping = self.threadlog.thread_logger()
            # printonce = False
        print("loop has ended")

    def start_run(self):
        """Runs the script to merge data and plot based on user's selections"""
        # If the user hasn't selected a folder path, give them a warning box and don't run the script
        if not self.dirpath:
            QMessageBox.about(self, "Warning!", "You must select a directory path before running this program.")
            return
        #
        # self.tkwargs = {"plot_power": self.pow_vs_bw.isChecked(), "plot_throttle": self.temp_vs_bw.isChecked(),
        #            "plot_temps": self.temp_vs_amb.isChecked(), "dirpath": self.dirpath}

        # Create threading of main application so that updates are in real time
        # t = threading.Thread(target=compile_data.plot_data, kwargs=self.tkwargs)
        # t.start()
        # t.run()
        # t.join()
        # p = multiprocessing.Process(target=compile_data.plot_data, kwargs=self.tkwargs)
        # p.start()
        # p.run()
        compile_data.plot_data(self.log_q, self.pow_vs_bw.isChecked(), self.temp_vs_bw.isChecked(), self.temp_vs_amb.isChecked(), self.dirpath)

    def closeEvent(self, event):
        self.log_q.put(None)

class QTextEditLogger(logging.Handler):
    """This creates a logger to output text to a GUI"""

    def __init__(self, parent=None):
        super().__init__()

        # putting this in class allows parent
        if parent:
            self.widget = QTextEdit(parent)
        else:
            self.widget = QTextEdit()
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        if msg == "Running..." or msg == "Finished!":
            msg = '<font color="blue">{}</font>'.format(msg)
        elif "ERROR" in msg.upper():
            msg = '<font color="red">{}</font>'.format(msg)
        else:
            msg = '<font color="black">{}</font>'.format(msg)

        # Move cursor to the end of the text block. This will prevent users from accidentally moving the cursor
        self.widget.moveCursor(QTextCursor.End)
        self.widget.insertHtml(msg)
        # Add a newline after every output to make the wrapped text more readable
        self.widget.append("\n")

#
# def loop_logger(log_q):
#     # Run this forever while main program is running. Should work?
#     # loop flag is set from the main thread to determine when to stop looping for queue log
#     config.dbglog.debug("Entering loop logger")
#
#     # print("looping_logger q object {}".format(log_q))
#     logger = compile_data.LogThread(log_q)
#
#     # printonce = True
#     looping = True
#     while looping:
#         time.sleep(0.1)
#         # Get flag from thread_logger. This will return false when it receives None as a message
#         looping = logger.thread_logger()
#         # printonce = False
#     print("loop has ended")

def main():
    log_q = multiprocessing.Queue()

    app = QApplication(sys.argv)
    ex = App(log_q)
    return sys.exit(app.exec_())

if __name__ == '__main__':
    # t = threading.Thread(target=loop_logger)
    # t.start()
    # t.run()
    main()
    # config.loop_flag = False

    # main_t = threading.main_thread()
    # main_t.run()
