# chromatographer/chromatographer-qt

These scripts are an reference example for designing labratory data collection software using python and the **nidaqmx** module provided from National Instruments. *Note that in the current iteration, this only supports Microsoft Windows operating systems*, future versions may include [PyDAQmx](https://pythonhosted.org/PyDAQmx/). These scripts control valves for a Chromatographer system and output measurement through differential analog output. 

This readme will disscuss some of the design descisions for labratory technologists and students wishing to design their own data collection software. This example shows a complete setup for separating code into a commandline and GUI interfaces---and by proxy---how to segregate code due to licensing concerns or conflicts.

I hope that the code and explanation provided is useful in your future lab endeavours.

[Preview](https://david.science/img/chromatographer-preview.png)


## Disclaimer

This is intended as a reference for technologists and students for designing lab software. Learning on how to code Python or Qt can be referenced from books to online tutorials outside of this project.


## Software required

* Anaconda 3
* Qt Creator
* NI-DAQmx from National Instruments
* python nidaqmx module `pip install nidaqmx`


## Chromatographer operation

The operation of this system is fairly straight forward. There are 7 valves to be controlled, labeled V1->V7. V1 and V7 respectively are to be controlled manually before operation for as per request in the design. The experiment for the chromatographer is designed to follow the following steps for operation:

1. Set only V4 open
2. Wait the duration of the `cycle_time`
3. Prime valves (i.e., sequence the valves states for the experiment)
4. Take differential analog readings over the `sample_window` at every interval given by `sample_delta`
5. Close all valves
6. Repeat

The basic operation of this experiment/equipment is quite simple and for a basic script to be written this is quite easy to do. However, the intention of the operation of this experiment is for convenience and for users not familiar with the underlying code.


## Design/Implementation considerations


### How to structure the code

There are many ways to approach this problem. One is to write a basic script that does exactly as described, and during the readings write to the screen or write to an output file. Extremely fast to get set up and going.

Another would be to implement a script that can take commandline arguments so you can dynamically change settings from experiment to experiment without altering the code, which is done in a more flexible way in `chromatographer.py`.  

The third option is to write the code intertwined with a graphical user interface (GUI). *This is the fastest solution for a GUI and is what most people would do for labratory software*. However, maintence of such code becomes challenging as time goes on, or new technologists inherit the code.

The final option is to write the software separated to have both a commandline version as well a GUI version. This segregation has several benefits, one the internal code can be tested without the GUI to ensure proper operation; the GUI can be written and tested separately. Doing this allows for a dramatic drop in debugging time during development. Also, the internal code can have a different license than that of the GUI (see section Licensing below). 

The `chromatographer.py` is written to work as a standalone application for commandline. Some function definitions may seem odd and unecessary, i.e., the `send_*` methods of `Chromatographer` class. However, these were necessary to for adding required hooks for dealing with the GUI, see the `ChromatorgapherQtWorker` class in `chromatorgapher-qt.py`.

In order to add the GUI hooks (signals/slots described in sections below) into the code, the `chromatorgapher.Chromatographer` class is subclassed into `chromatographer-qt.ChromatographerQtWorker`. A worker object is created with all of the signals and slots defined, then moved to it's own thread so that the GUI and the code defined in `collect_data` method can operate independently without locking up the GUI from the user. This is necessary if they want to cancel the operation or view dynamic updates from the plot.

The plot features in Qt are not part of *Qt Creator* software. A generic `QtWidgets.QWidget` is placed down, where a `matplotlib` figure and figure controls can be set into it's own layout and then set as a layout onto the generic QWidget. This is done in code as seen in the `init_ui()` method.

The `chromatographer.py` allows for GUI updates during the cycle time to update the progress bar of the cycle time. Not necessary, but a convenient feature for someone glancing at the software to see where it is at currently. 


### Qt5 Toolkit

Qt5 was chosen to design the GUI because of the vast amount of the GUI elements available, and for the GUI builder *Qt Creator* to graphically build elements and save a `*.ui`. Qt is also very versatile with languages and operating systems that it can run on. The file which can be imported into the code. Named objects have all their settings within the ui file and than can be called in code, so it is important to know what elements are named what. The python Qt library used in this example is PyQt5 where the opensource version is GPL v3 licensed. The official [Qt for Python](https://www.qt.io/qt-for-python) documentation uses PySide2 library (LGPL v3 licensed) for handling widgets and is a great resource for both PyQt5 and PySide2. PyQt5 was chosen out of convenience due to my development system only having access to PyQt5 at the time of this writing. if you are intending to write proprietary applications a license for Qt and PyQt5 can be purchased. Or you could write segregated code and conform to the LGPL v3 license for Qt and PySide2, which is also viable (and my preferred option).


#### Signals/Slots

This is jargon used in Qt to describe what operation/function/method to perform (slot) when an event is triggered (signal). Examples of events are: buttons being clicked or a widget that has a value changed by the user. Qt has built in signals and slots for widgets that Qt provides, but the user can define their own signals as instances from `QtCore.pyqtSignal` and slots using the decorator `@QtCore.pyqtSlot()`. There are a few examples in `chromatorgapher-qt.py`.


## Licenses

**If the code will never leave the labratory or the company, this isn't a concern**. *If the code is to be distributed publically, then this is something you must consider*.

This isn't meant to be a license war or what license you should use, but merely something to think about before blindly using code without understanding your rights. This is not meant to be an indepth understanding, but give you a *basic* grasp on licenses. *If you are actually concerned with this, then seek proper legal counsel*.

It isn't usually a concern to segregate code for labratory applications, as separate licenses may seem arbitrary. When developing software that may go commerical *after* lab work, this becomes a viable concern if you need/want to keep the details from clients or users. This is something quite overlooked by people using software without understanding the usage requirements from licenses.

For example, I prefer to use the license outlined by [OpenBSD](https://cvsweb.openbsd.org/src/share/misc/license.template?rev=HEAD), which is modeled after the ISC license. For code I am willing to share, all I care about is ensuring my name is acknowledged in the Copyright of the code. Other developers have more concerns on how their code is handled, and license their code appropriately for their concerns. Some other popular Licenses are: BSD 2-Clause, BSD 3-Clause, GPL v3, LGPL v3, MIT, and Apache License v2.0.

One concern is that the opensource version of PyQt5 is licensed under the GPL v3 which means any attached code becomes GPL v3 upon distribution (where a public github repository is considered distributing) otherwise this is a violation of the GPL v3 License; this is why I provide the `COPYING` file as required by the GPL v3. This is fine if you want to distribute your code as outlined by the GPL v3, but if you are not distributing your code then this is not required if it stays within the labratory or company.

By separating the code as I did in this project I am able to take the commandline version and create a new GUI using PySide2, and keep the distribution rights as I originally intended with my license as long as I adhere to the LGPL v3 requirements. I could also completely write the GUI in another toolkit like GTK or Tkinter. 
