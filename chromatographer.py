# Copyright (c) 2020 David Kalliecharan <david@david.science>
# Copyright (c) 2020 Andrew George
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
==================
chromatographer.py
==================

This software controls a valve configuration for a chromatographer through
a NI DAQ card. The software takes a differential measurement from the output
of the chromatographer.

The design and implementation of this software is to be used as a reference
example for lab technologists and students for writing software to record data
using python and the nidaqmx interface.
"""

import nidaqmx
from nidaqmx.constants import TerminalConfiguration as termcfg
from numpy import arange, mean
import time

# Valve ID constants for bitwise write operations
VALVE_ALL_OFF = 0x00
VALVE_1       = 0x02
VALVE_2       = 0x04
VALVE_3       = 0x08
VALVE_4       = 0x10
VALVE_5       = 0x20
VALVE_6       = 0x40
VALVE_7       = 0x80
VALVE_ALL_ON = VALVE_1|VALVE_2|VALVE_3|VALVE_4|VALVE_5|VALVE_6|VALVE_7

DAQ_DEFAULT = "Dev1"

system = nidaqmx.system.System()


class Chromatographer:
    """ChromatographerWorker
    This class only collects data as defined by the operation schematic from
    Andrew George (Physics Technologist) at Dalhousie University.

    It is designed for commandline use and to be subclassed and included into a
    GUI, such as: Qt, GTK, Tkinter, etc...
    """
    # NOTE the Worker sends data through the signal's emit function
    stop_requested = False
    def __init__(self, daq_id, cycle_time, sample_window, sample_delta):
        # System Configuration for NI DAQs
        self.system = nidaqmx.system.System()

        # Configure DAQ to use analog input 1 and 9 for differential output as
        # per the user manual for the DAQ 6014: ai{i, i+8} for differential
        self.task_analog = nidaqmx.Task()
        self.task_analog.ai_channels.add_ai_voltage_chan("{dev}/ai1".format(dev=daq_id),
                                                         terminal_config=termcfg.DIFFERENTIAL)
        self.task_analog.start()

        # Use digital IO lined 0->7
        self.task_digital = nidaqmx.Task()
        self.task_digital.do_channels.add_do_chan('{dev}/port0/line0:7'.format(dev=daq_id))
        self.task_digital.start()

        self.cycle_time = cycle_time
        self.cycle_time_remaining = cycle_time

        self.sample_t = sample_window
        self.sample_dt = sample_delta

        if self.sample_dt >= self.sample_t:
            raise ValueError("sample_delta MUST be lower than sample_window")

    def __str__(self):
        return "Chromatographer Class"

    def close_tasks(self):
        """Stops and closes any defined analog and digital tasks"""
        print('Cleaning up DAQ tasks')
        self.task_digital.stop()
        self.task_digital.close()

        self.task_analog.stop()
        self.task_analog.close()

    def collect_data(self):
        """Collects data based on the operation schematic.
        (1) Wait cycle time duration (updates progress bar and timer)
        (2) Prime valves before mesaurements
        (3) Allow gas to flow in and record measurements accordingly
        (4) Reset valves to cycle state
        (5) Go to (1)
        """
        self.reset_to_cycle_state()
        while True:
            if self.stop_requested == True:
                break

            time.sleep(1)
            self.cycle_time_remaining -= 1 # 1 second
            self.send_time_remaining(self.cycle_time_remaining)
            if self.cycle_time_remaining > 0:
                continue

            self.prime_valves()
            for t in arange(0, self.sample_t, self.sample_dt):
                if self.stop_requested == True:
                    break
                # Average N samples per measurement
                signals = self.task_analog.read(number_of_samples_per_channel=10)
                self.send_data_ready(t, mean(signals))
                time.sleep(self.sample_dt)
            self.reset_to_cycle_state()
            self.send_finished()
            self.cycle_time_remaining = self.cycle_time
            self.send_time_remaining(self.cycle_time_remaining)
        # Reinitialize the state if user restarts this function
        self.stop_requested = False

    def prime_valves(self):
        """Prime the valves before taking readings
        As outlined in the operation schematic.
        """
        self.set_valve(VALVE_ALL_OFF)
        time.sleep(5)
        self.set_valve(VALVE_4)
        time.sleep(2)
        self.set_valve(VALVE_4|VALVE_6)
        time.sleep(5)
        self.set_valve(VALVE_4)
        time.sleep(2)
        self.set_valve(VALVE_2|VALVE_4)
        time.sleep(5)
        self.set_valve(VALVE_4)
        time.sleep(2)
        self.set_valve(VALVE_3|VALVE_5)
        time.sleep(5)

    def reset_to_cycle_state(self):
        """Reset all valves to off, except valve 4 to allow Ar to flow"""
        self.set_valve(VALVE_4)

    def open_valve(self, valves):
        """Open only the requested valves
        valves : 0x00-0xff

        Valves are opened by passing bits. By using hex values you can set
        multiple valves using constants with bitwise or/and operations. An
        example of this is:

        open_valve(VALVE_1|VALVE_2)

        Where VALVE_1 = 0x01 and VALVE_2 = 0x02.
        """
        valves_state = self.task_digital.read()
        new_valves_state = valves_state | valves
        self.task_digital.write([new_valves_state])

    def close_valve(self, valves):
        """Close only the requested valves
        valves : 0x00-0xff

        Valves are closed by passing bits. By using hex values you can set
        multiple valves using constants with bitwise or/and operations. An
        example of this is:

        close_valve(VALVE_1|VALVE_2)

        Where VALVE_1 = 0x01 and VALVE_2 = 0x02.
        """
        valves_state = self.task_digital.read()
        new_valves_state = valves_state & (~valves & 0xff)
        self.task_digital.write(new_valves_state)

    def set_valve(self, valves):
        """Set valves to be turned on.
        valves : 0x00-0xff

        Unlike open_valve and close_valve, set_valve opens the valves of
        interest, while closing the rest.
        """
        self.task_digital.write([valves])

    def stop(self):
        """Safely request stop for worker"""
        self.stop_requested = True

    def send_time_remaining(self, t):
        pass

    def send_data_ready(self, x, y):
        print(x, y)

    def send_finished(self):
        print("# Dataset finished")


if __name__ == '__main__':
    from argparse import ArgumentParser
    import datetime
    from sys import exit

    parser = ArgumentParser()
    parser.add_argument('-d', '--daq-device', type=str, default=DAQ_DEFAULT,
                        help="DAQ device")
    parser.add_argument('-l', '--list-devices', action="store_true",
                        help="Display available DAQ devices")

    group_cfg = parser.add_argument_group("Chromatographer configuration")
    group_cfg.add_argument('-c', '--cycle-time', type=int, default=300,
                           help="Cycle time in seconds")
    group_cfg.add_argument('-T', '--sample-window', type=int, default=30,
                           help="Sample window (t) in seconds")
    group_cfg.add_argument('-t', '--sample-delta', type=float,  default=0.5,
                           help="Sample interval (dt) in seconds")

    group_man = parser.add_argument_group("Manual valve control")
    group_man.add_argument('-o', '--open', action="store_true",
                           help="Open specified valve (-v or --valve).")
    group_man.add_argument('-s', '--shut', action="store_true",
                           help="shut specified valve (-v or --valve).")
    group_man.add_argument('-v', '--valve', type=int, default=0,
                           help="shut specified valve (-v or --valve).")

    args = parser.parse_args()

    if args.list_devices == True:
        for dev in system.devices.device_names:
            print(dev)
        exit()

    cycle_time = args.cycle_time
    sample_t = args.sample_window
    sample_dt = args.sample_delta
    daq_device = args.daq_device

    worker = Chromatographer(daq_device, cycle_time, sample_t, sample_dt)

    if (args.open == True) and (args.shut == True):
        print("!! CONFLICT: Only pass one valve control option at a time")
        exit(1)

    if args.valve == 1:
        valve = VALVE_1
    elif args.valve == 7:
        valve = VALVE_7
    elif args.valve != 0:
        print("!! WARN: Only valves are 1 and 7 are manually controlled.")
        exit(1)

    if args.open == True:
        worker.open_valve(valve)
    elif args.shut == True:
        worker.close_valve(valve)

    print("# Date :", datetime.date.today().ctime())
    print("# Sample window (t) :", sample_t)
    print("# Sample interval (dt) :", sample_dt)
    print("# Cycle time :", cycle_time)
    try:
          worker.collect_data()
    except Exception as err:
        print(err)
    worker.close_tasks()
