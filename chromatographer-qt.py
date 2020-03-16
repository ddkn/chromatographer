# Copyright (c) 2020 David Kalliecharan <david@david.science>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
====================
chromatography-qt.py
====================

This software provides a PyQt5 user interface to the chromatograhper.py
script. This code is intended for lab technologists and students as a
reference example to develop their own GUI data collection software for
laboratory use.

NOTE, the PyQt5 library is licensed under the terms of the GNU General Public
License as published by the Free Software Foundation version 3 of the License.
Code distributed with the open source version of PyQt5 is subject to the
License restrictions outlined in the included COPYING file. That includes this
file.
"""

import chromatographer as cg
import datetime
from functools import partial
import nidaqmx
from numpy import arange, diff
import matplotlib.animation as animation
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets, is_pyqt5
if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt4agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from PyQt5 import uic
import os.path
import time
import sys


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Conversions
MIN_TO_SEC=60

class ChromatographerQt(QtWidgets.QMainWindow):
    """ChromatographerQt
    This acts as a user interface for controlling the ChromatographerQt.
    """
    valve1_open = False
    valve7_open = False
    def __init__(self):
        super(ChromatographerQt, self).__init__()

        self.init_ui()
        self.init_plot()
        self.init_worker()

        # Show the GUI
        self.show()
        return None

    def __str__(self):
        return "ChromatographerQt class"

    def init_ui(self):
        """Set up user interface for.workerects outside of Qt Creator"""
        # Interface.workerect definitions are within the chromatographer.ui file
        uic.loadUi('chromatographer.ui', self)
        self.setWindowTitle("Chromatographer")

        self.errorMessage = QtWidgets.QErrorMessage()

        # Populate available DAQ Devices for selection
        try:
            self.comboDAQDev.addItems(cg.system.devices.device_names)
        except nidaqmx.DaqError as err_msg:
            print(err_msg)
            print("Exiting.")
            sys.exit(1)
        except Exception as err_msg:
            print(err_msg)
            print("Exiting.")
            sys.exit(1)

        plotlayout = QtWidgets.QVBoxLayout()
        self.figure = Figure(tight_layout=True)

        # Sizing policy for Matplotlib FigureCanvas isn't in Qt Creator
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                  QtWidgets.QSizePolicy.Minimum,)
        plotlayout.addWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        plotlayout.addWidget(self.toolbar)
        self.graph.setLayout(plotlayout)

        # Connect Slots to Signals for events
        self.btnStartStop.released.connect(self.start_stop)
        # Using partial to pass a Slot a value, reducing repetitive code
        self.btnV1.clicked.connect(partial(self.toggle_valve, 1))
        self.btnV7.clicked.connect(partial(self.toggle_valve, 7))
        self.btnOutputFile.clicked.connect(self.set_output_file)

        # Group valve buttons, labels and state for ease of programming
        self.valve = {
                1 : {'btn'     : self.btnV1,
                     'lbl'     : self.lblV1State,
                     'is_open' : self.valve1_open,},
                7 : {'btn'     : self.btnV7,
                     'lbl'     : self.lblV7State,
                     'is_open' : self.valve7_open,},
        }

    def init_plot(self):
        """Initialize plot area with one plot"""
        self.xdata, self.ydata = [0], [0]
        self.ax = self.canvas.figure.subplots()
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Signal (V)')
        self.ax.figure.canvas.draw()

    def init_worker(self):
        """Define worker class and move to thread to interface with GUI"""
        print("Configuring worker for data collection")
        daq_dev = self.get_selected_daq_device()
        cycle_t = self.get_cycle_time()
        sample_t = self.get_sample_window()
        sample_dt = self.get_sample_delta()

        # If worker is present close DAQ tasks befer reinitializing
        worker_instance = getattr(self, "worker", None)
        if worker_instance is not None:
            self.worker.close_tasks()

        self.worker = ChromatographerQtWorker(daq_dev,
                                              cycle_t, sample_t,
                                              sample_dt)
        self.worker.data_ready.connect(self.update_plot)

        self.worker.time_remaining.connect(self.update_cycle_time)
        self.worker.finished.connect(self.toggle_controls)
        self.worker.finished.connect(self.save_data)

        self.thread = QtCore.QThread()
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.thread.quit)
        self.thread.started.connect(self.worker.collect_data)

    def update_plot(self, x, y):
        """Update plot area with new values
        x : sample time (seconds)
        y : signal (voltage)
        """
        self.xdata.append(x)
        self.ydata.append(y)

        self.ax.cla()
        self.ax.autoscale(False, axis='x')
        self.ax.autoscale(True, axis='y')

        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Signal (V)')
        self.ax.set_xlim(0, self.spinSampleWindow.value())

        self.ax.plot(self.xdata, self.ydata, 'o--')
        self.ax.grid()
        self.ax.figure.canvas.draw()
        return None

    def save_data(self):
        """Save the current sample dataset and clear values"""
        print("Saving dataset to", self.get_output_file())
        with open(self.get_output_file(), 'a') as f:
            for x, y in zip(self.xdata, self.ydata):
                f.write("{index},{x},{y}\n".format(index=self.data_id,
                                                   x=x, y=y))
        self.data_id += 1
        self.xdata = []
        self.ydata = []

    def update_cycle_time(self, t):
        """Cycle time progress updater
        t: time remaining (seconds)
        """
        t_cycle = self.get_cycle_time()
        # Convert cycle_remain to percentage
        cycle_remain = int(((t_cycle - t)/t_cycle)*100)
        self.progressCycleRemain.setValue(cycle_remain)
        self.lcdCycleRemain.display(int(t/MIN_TO_SEC))

    def set_output_file(self):
        """Slot to set the output file"""
        filename = QtWidgets.QFileDialog.getSaveFileName(self, "Select output file")
        print(filename)
        self.lineOutputFile.setText(filename[0])

    def start_stop(self):
        """Start or stop the data collection using a threaded worker"""
        if self.thread.isRunning() == True:
            self.worker.stop()
            print("Stopping data collection")
            self.thread.terminate()
            self.thread.wait()
            self.btnStartStop.setText("START")
        else:
            header  = "# Date : {date}\n"
            header += "# Sample window (t) : {t} sec\n"
            header += "# Sample interval (dt) : {dt} sec\n"
            header += "# Cycle Time : {ct} min\n"
            header += "#\n"
            header += "# id, time (s), signal (V)\n"
            try:
                with open(self.get_output_file(), 'a') as f:
                    f.write(header.format(date=datetime.date.today().ctime(),
                                          t=self.get_sample_window(),
                                          dt=self.get_sample_delta(),
                                          ct=self.get_cycle_time()))
            except FileNotFoundError:
                self.errorMessage.showMessage("Please select an output file!")
                return
            self.btnStartStop.setText("STOP")
            # Initial dataset id set to zero for output file
            self.data_id = 0
            self.init_worker()
            self.thread.start()
            print("Starting data collection")
        self.toggle_controls()
        return

    def toggle_valve(self, valve_id):
        """Toggle the state of valve X"""
        if self.thread.isRunning() == True:
            print("WARN: Feature disabled during experiment")
            return

        if valve_id == 1:
            valve_io = cg.VALVE_1
        elif valve_id == 7:
            valve_io = cg.VALVE_7

        if self.valve[valve_id]['is_open'] == False:
            print("Opening V{}".format(valve_id), valve_io)
            self.valve[valve_id]['is_open'] = True
            self.worker.open_valve(valve_io)
            self.valve[valve_id]['lbl'].setText("V{}: Opened".format(valve_id))
            self.valve[valve_id]['btn'].setText("CLOSE")
        else:
            print("Closing V{}".format(valve_id), valve_io)
            self.valve[valve_id]['is_open'] = False
            self.worker.close_valve(valve_io)
            self.valve[valve_id]['lbl'].setText("V{}: Closed".format(valve_id))
            self.valve[valve_id]['btn'].setText("OPEN")
        return

    def toggle_controls(self):
        """Toggles the UI controls depending on data collection"""
        # Small delay to ensure thread cleans up properly
        time.sleep(0.1)
        state = False if self.thread.isRunning() == True else True
        self.grpManual.setEnabled(state)
        self.grpSettings.setEnabled(state)
        self.grpCycleRemain.setEnabled(not state)

    def get_cycle_time(self):
        """Get the cycle time convert to seconds"""
        return self.spinCycleTime.value()*MIN_TO_SEC

    def get_sample_window(self):
        """Get the sample window time in seconds"""
        return self.spinSampleWindow.value()

    def get_sample_delta(self):
        """Get the sample interval in seconds"""
        return self.spinSampleDelta.value()

    def get_output_file(self):
        """Get the output file"""
        return self.lineOutputFile.text()

    def get_selected_daq_device(self):
        return self.comboDAQDev.currentText()


class ChromatographerQtWorker(cg.Chromatographer, QtCore.QObject):
    """ChromatographerQtWorker
    This subclass of chromatographer.Chromatographer class adds the necessary
    Qt signals and slots for interfacing with the UI.
    """
    # NOTE the Worker sends data through the signal's emit function
    time_remaining = QtCore.Signal(float)
    data_ready     = QtCore.Signal(float, float)
    finished       = QtCore.Signal()
    stop_requested = False
    def __init__(self, daq_id, cycle_time, sample_window, sample_delta):
        super(QtCore.QObject, self).__init__()
        super(ChromatographerQtWorker, self).__init__(daq_id, cycle_time,
                                                      sample_window,
                                                      sample_delta)

    @QtCore.pyqtSlot()
    def collect_data(self):
        super().collect_data()

    def send_time_remaining(self, t):
        self.time_remaining.emit(t)

    def send_data_ready(self, x, y):
        self.data_ready.emit(x, y)

    def send_finished(self):
        self.finished.emit()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    icon_path = os.path.join(ROOT_DIR, "icon.svg")
    app.setWindowIcon(QtGui.QIcon(icon_path))

    window = ChromatographerQt()
    app.exec_()
