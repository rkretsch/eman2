#!/usr/bin/env python
#
# Author: Steven Ludtke  3/4/2011
# Copyright (c) 2011- Baylor College of Medicine
#
# This software is issued under a joint BSD/GNU license. You may use the
# source code in this file under either license. However, note that the
# complete EMAN2 and SPARX software packages have some GPL dependencies,
# so you are responsible for compliance with the licenses of these packages
# if you opt to use BSD licensing. The warranty disclaimer below holds
# in either instance.
#
# This complete copyright notice must be included in any revised version of the
# source code. Additional authorship citations may be added, but existing
# author citations must be preserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston MA 02111-1307 USA
#

from past.utils import old_div
from builtins import range
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer

import sys
import os
import weakref
import threading

from EMAN2 import *
from eman2_gui.emapplication import get_application, EMApp
from eman2_gui.emimage2d import EMImage2DWidget
from eman2_gui.emplot2d import EMPlot2DWidget
from eman2_gui.emimagemx import EMImageMXWidget
from eman2_gui.emscene3d import EMScene3D
from eman2_gui.emdataitem3d import EMDataItem3D, EMIsosurface, EMSliceItem3D
from eman2_gui.emshape import EMShape
from eman2_gui.valslider import *
import traceback

def main():
	progname = os.path.basename(sys.argv[0])
	usage = """prog [options] <image file>

	Provides a GUI interface for applying a sequence of processors to an image, stack of images or a volume."""

	parser = EMArgumentParser(usage=usage,version=EMANVERSION)

#	parser.add_argument("--boxsize","-B",type=int,help="Box size in pixels",default=64)
#	parser.add_argument("--shrink",type=int,help="Shrink factor for full-frame view, default=0 (auto)",default=0)
	parser.add_argument("--apix",type=float,help="Override the A/pix value stored in the file header",default=0.0)
#	parser.add_argument("--force2d",action="store_true",help="Display 3-D data as 2-D slices",default=False)
	parser.add_argument("--safemode",action="store_true",help="Safe mode without the timer...",default=False)
	parser.add_argument("--ppid", type=int, help="Set the PID of the parent process, used for cross platform PPID",default=-1)
	parser.add_argument("--idx", type=int, help="index for an image in a stack",default=-1)
	parser.add_argument("--verbose", "-v", dest="verbose", action="store", metavar="n", type=int, default=0, help="verbose level [0-9], higher number means higher level of verboseness")

	(options, args) = parser.parse_args()

	if len(args) != 1: parser.error("You must specify a single data file on the command-line.")
	if not file_exists(args[0]): parser.error("%s does not exist" %args[0])
#	if options.boxsize < 2: parser.error("The boxsize you specified is too small")
#	# The program will not run very rapidly at such large box sizes anyhow
#	if options.boxsize > 2048: parser.error("The boxsize you specified is too large.\nCurrently there is a hard coded max which is 2048.\nPlease contact developers if this is a problem.")

#	logid=E2init(sys.argv,options.ppid)

	app = EMApp()
	pix_init()
	control=EMFilterTool(datafile=args[0],apix=options.apix,force2d=False,verbose=options.verbose, safemode=options.safemode, idx=options.idx)
#	control=EMFilterTool(datafile=args[0],apix=options.apix,force2d=options.force2d,verbose=options.verbose)
	control.show()
	try: control.raise_()
	except: pass

	app.execute()
#	E2end(logid)

def filtchange(name,value):
	return {}

class EMProcessorWidget(QtWidgets.QWidget):
	"""A single processor with parameters"""
	upPress = QtCore.pyqtSignal(int)
	downPress = QtCore.pyqtSignal(int)
	plusPress = QtCore.pyqtSignal(int)
	minusPress = QtCore.pyqtSignal(int)
	processorChanged = QtCore.pyqtSignal(int)

	plist=dump_processors_list()

	# Sorted list of the stuff before the first '.'
	cats=set([i.split(".")[0] for i in list(plist.keys())])
	cats=list(cats)
	cats.sort()

	# For some parameters we will try to assign sensible default values and ranges. This information should probably be a part
	# of the processor objects themselves, but isn't at present.
	# (start enabled, range, default value, change callback)
	parmdefault= {
		"cutoff_abs":(1,(0,.5),.1,filtchange),
		"cutoff_freq":(0,(0,1.0),None,filtchange),
		"cutoff_pixels":(0,(0,128),None,filtchange),
		"cutoff_resolv":(0,(0,1.0),None,filtchange),
		"sigma":(0,(0,3.0),.5,None),
		"apix":(0,(0.2,10.0),2.0,None)
	}

	def __init__(self,parent=None,tag=None):
		app=QtWidgets.qApp

		QtWidgets.QWidget.__init__(self,parent)
		self.gbl = QtWidgets.QGridLayout(self)
		self.gbl.setColumnStretch(0,0)
		self.gbl.setColumnStretch(1,0)
		self.gbl.setColumnStretch(2,1)
		self.gbl.setColumnStretch(3,3)

		# Enable checkbox
		self.wenable=QtWidgets.QCheckBox(self)
		self.wenable.setChecked(False)			# disable new processors by default to permit their values to be set
		self.gbl.addWidget(self.wenable,0,1)

		# List of processor categories
		self.wcat=QtWidgets.QComboBox(self)
		self.wcat.addItem("")
		for i in self.cats: self.wcat.addItem(i)
#		self.wcat.setCurrentindex(self.wcat.findText("processor"))
		self.gbl.addWidget(self.wcat,0,2)

		# List of processor subcategories
		self.wsubcat=QtWidgets.QComboBox(self)
		self.gbl.addWidget(self.wsubcat,0,3)
#		self.update_subcat()

		#button grid
		self.gbl2=QtWidgets.QGridLayout()
		self.gbl.addLayout(self.gbl2,0,0,1,1)
		if get_platform().lower()=="darwin": self.gbl2.setSpacing(10)
		else: self.gbl2.setSpacing(1)

#		self.gbl2.setColumnStretch(0,1)
#		self.gbl2.setColumnStretch(1,1)

#		self.wup = QtWidgets.QPushButton(app.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp),"")
		self.wup = QtWidgets.QPushButton(pix_up,"",self)
		self.wup.setMaximumSize(QtCore.QSize(17, 17))
#		self.wup.setSizePolicy(QtWidgets.QSizePolicy.Fixed,QtWidgets.QSizePolicy.Fixed)
		self.gbl2.addWidget(self.wup,0,0)

		self.wdown = QtWidgets.QPushButton(pix_down,"",self)
		self.wdown.setMaximumSize(QtCore.QSize(17, 17))
		self.gbl2.addWidget(self.wdown,1,0)

		self.wplus = QtWidgets.QPushButton(pix_plus,"",self)
		self.wplus.setMaximumSize(QtCore.QSize(17, 17))
		self.gbl2.addWidget(self.wplus,1,1)

		self.wminus= QtWidgets.QPushButton(pix_minus,"",self)
		self.wminus.setMaximumSize(QtCore.QSize(17, 17))
		self.gbl2.addWidget(self.wminus,0,1)


		self.wcat.currentIndexChanged[int].connect(self.eventCatSel)
		self.wsubcat.currentIndexChanged[int].connect(self.eventSubcatSel)
		self.wup.clicked[bool].connect(self.butUp)
		self.wdown.clicked[bool].connect(self.butDown)
		self.wplus.clicked[bool].connect(self.butPlus)
		self.wminus.clicked[bool].connect(self.butminus)
		self.wenable.clicked[bool].connect(self.updateFilt)

		self.parmw=[]

		self.setTag(tag)
#		print "Alloc processor ",self.tag

#	def __del__(self):
#		print "Free processor ",self.tag
#		QtWidgets.QWidget.__del__(self)

	def __getstate__(self):
		"used when pickling"
		proc=self.processorName()
		if proc not in self.plist : return None		# invalid processor selection
		if self.wenable.isChecked() : proc=(proc,True)		# disabled, so we return None
		else: proc=(proc,False)

		parms={}
		for w in self.parmw:
			parms[w.getLabel()]=(w.getValue(),w.getEnabled())

		return (proc,parms)

# TODO - incomplete
	def __setstate__(self,state):
		"used when unpickling"
		self.init()
		if state==None : return

		proc,parms=state
		proc,enabled=proc

		try: proc_cat,proc_scat=proc.split(".",1)
		except:
			proc_cat=proc
			proc_scat="---"

		self.wcat.setCurrentIndex(self.wcat.findText(proc_cat))
		self.wsubcat.setCurrentIndex(self.wsubcat.findText(proc_scat))

	def getAsProc(self):
		"Returns the currently defined processor as a --process string for use in commands"

		if not self.wenable.isChecked() : return ""

		proc=self.processorName()
		if proc not in self.plist : return ""		# invalid processor selection

		enabled=[]
		for w in self.parmw:
			if w.getEnabled() : enabled.append("%s=%s"%(w.getLabel(),str(w.getValue())))

		return "--process=%s:%s "%(self.processorName(),":".join(enabled))

	def getAsText(self):
		"Returns the currently defined processor as a 3 line string for persistence"

		proc=self.processorName()
		if proc not in self.plist : return None		# invalid processor selection

		if self.wenable.isChecked() : ret="#$ enabled\n"
		else: ret="#$ disabled\n"

		enabled=[]
		disabled=[]
		for w in self.parmw:
			if w.getEnabled() : enabled.append("%s=%s"%(w.getLabel(),str(w.getValue())))
			else : disabled.append("%s=%s"%(w.getLabel(),str(w.getValue())))

		ret+="# %s\n--process=%s:%s\n\n"%(":".join(disabled),self.processorName(),":".join(enabled))

		return ret


	def setFromText(self,text):
		"""Sets the GUI from the text written to disk for persistent storage
		text should contain a 3-tuple of lines
		#$ enabled or disabled
		# name=value name=value ...
		--process=processor:name=value:name=value:..."""

#		print "set"

		if len(text)!=3 :
			raise Exception("setFromText requires 3-tuple of strings")
		if text[0][0]!="#" or text[1][0]!="#" or text[2][0]!="-" :
			raise Exception("Problem unpacking '%s' from file"%text)

		disabled=parsemodopt("X:"+text[1][1:].strip())[1]			# dictionary of disabled values
		proc,enabled=parsemodopt(text[2].split("=",1)[1])	# dictionary of enabled values

		try: proc_cat,proc_scat=proc.split(".",1)
		except:
			proc_cat=proc
			proc_scat="---"

		self.wcat.setCurrentIndex(self.wcat.findText(proc_cat))
#		self.eventCatSel(0)
		self.wsubcat.setCurrentIndex(self.wsubcat.findText(proc_scat))
#		self.eventSubcatSel(0)


		for w in self.parmw:
			lbl=w.getLabel()
			if lbl in enabled:
				w.setValue(enabled[lbl])
				w.setEnabled(1)
			elif lbl in disabled:
				w.setValue(disabled[lbl])
				w.setEnabled(0)

		if "enabled" in text[0] : self.wenable.setChecked(True)
		else : self.wenable.setChecked(False)

#		print proc_cat,proc_scat,enabled,disabled
		return

	def setTag(self,tag):
		self.tag=tag

	def butUp(self):
		self.upPress.emit(self.tag)

	def butDown(self):
		self.downPress.emit(self.tag)

	def butPlus(self):
		self.plusPress.emit(self.tag)

	def butminus(self):
		self.minusPress.emit(self.tag)


	def eventCatSel(self,idx):
		"Called when the user selects a processor category"
		cat=str(self.wcat.currentText())
		#print "catsel ",cat
		#traceback.print_stack(limit=2)
		scats=['.'.join(i.split('.',1)[1:]) for i in self.plist if i.split(".")[0]==cat]
		scats.sort()
		for i in range(len(scats)):
			if scats[i]=="" : scats[i]="---"
		self.wsubcat.clear()
		self.wsubcat.addItem("")
		if len(scats)>0 : self.wsubcat.addItems(scats)

	def eventSubcatSel(self,idx):
		"Called when the user selects a processor subcategory. Updates the parameter widget set."
		proc=self.processorName()
		#print "subcatsel ",proc
		#traceback.print_stack(limit=2)

		try: parms=self.plist[proc]
		except: parms=["Please select a processor"]

		self.wsubcat.setToolTip(parms[0])

		# Remove old parameter widgets
		for w in self.parmw:
			self.gbl.removeWidget(w)
			w.close()				# get it off the screen
			w.setParent(None)		# do this before we can actually delete the widget
			del(w)					# finally, get it deleted (may not take effect until parmw=[] below

		# Iterate over the parameters
		# parms[i] - name of the parameter
		# parms[i+1] - type of parameter
		# parms[i+2] - helpstring for parameter
		self.parmw=[]
		self.ninput=0
		for i in range(1,len(parms),3):
			self.ninput+=1
			try: dflt=self.parmdefault[parms[i]]		# contains (start enabled, range, default value, change callback)
			except: dflt=(1,(0,5.0),None,None)			# default parameter settings if we don't have anything predefined

			if parms[i+1] in ("FLOAT","INT"):
				self.parmw.append(ValSlider(self,dflt[1],parms[i],dflt[2],100,dflt[0]))
				if parms[i+1]=="INT" :
					self.parmw[-1].setIntonly(1)
	#			self.parmw[-1].hboxlayout.setContentsMargins ( 11.0,5.0,5.0,5.0 )
			elif parms[i+1]=="BOOL" :
				self.parmw.append(CheckBox(self,parms[i],dflt[2],100,dflt[0]))

			elif parms[i+1]=="STRING" :
				self.parmw.append(StringBox(self,parms[i],dflt[2],100,dflt[0]))

			elif parms[i+1]=="TRANSFORM" :
				self.parmw.append(StringBox(self,parms[i],dflt[2],100,dflt[0]))

			elif parms[i+1]=="EMDATA" :
				self.parmw.append(StringBox(self,parms[i],dflt[2],100,dflt[0]))

			elif parms[i+1]=="FLOATARRAY" :
				self.parmw.append(StringBox(self,parms[i],dflt[2],100,dflt[0]))

			elif parms[i+1]=="XYDATA" :
				self.parmw.append(StringBox(self,parms[i],dflt[2],100,dflt[0]))

			else: print("Unknown parameter type",parms[i+1],parms)

			self.parmw[-1].setToolTip(parms[i+2])
			self.gbl.addWidget(self.parmw[-1],self.ninput,1,1,4)
			self.parmw[-1].valueChanged.connect(self.updateFilt)
			self.parmw[-1].enableChanged.connect(self.updateFilt)

		self.updateFilt()

	def updateFilt(self,val=None):
		"Called whenever the processor changes"
		#if self.wenable.isChecked() :
		self.processorChanged.emit(self.tag)

	def processorName(self):
		"Returns the name of the currently selected processor"
		cat=str(self.wcat.currentText())
		scat=str(self.wsubcat.currentText())
		if scat=="" :  return cat
		else : return cat+"."+scat

	def processorParms(self):
		"Returns the currently defined processor as (name,dict) or None if not set to a valid state"
		if not self.wenable.isChecked() : return None		# disabled, so we return None

		proc=self.processorName()
		if proc not in self.plist : return None		# invalid processor selection


		parms={}
		for w in self.parmw:
			if w.getEnabled() : parms[w.getLabel()]=w.getValue()

		return (proc,parms)

class EMFilterTool(QtWidgets.QMainWindow):
	"""This class represents the EMFilterTool application instance.  """
	module_closed = QtCore.pyqtSignal()

	def __init__(self,datafile=None,apix=0.0,force2d=False,verbose=0, safemode=False, idx=-1):
		QtWidgets.QMainWindow.__init__(self)

		app=QtWidgets.qApp
		self.apix=apix
		self.force2d=force2d
		self.dataidx=idx
		self.safemode=safemode
		self.setWindowTitle("e2filtertool.py")

		# Menu Bar
		self.mfile=self.menuBar().addMenu("File")
#		self.mfile_save_processor=self.mfile.addAction("Save Processor Param")
		self.mfile_save_stack=self.mfile.addAction("Save Processed Stack")
		self.mfile_save_map=self.mfile.addAction("Save Processed Map")
		self.mfile_quit=self.mfile.addAction("Quit")

		self.mview=self.menuBar().addMenu("View")
		self.mview_new_2dwin=self.mview.addAction("Add 2D View")
		self.mview_new_3dwin=self.mview.addAction("Add 3D View")
		self.mview_new_plotwin=self.mview.addAction("Add Plot View")

		self.setCentralWidget(QtWidgets.QWidget())
		self.vblm = QtWidgets.QVBoxLayout(self.centralWidget())		# The contents of the main window

		# List of processor sets
		self.wsetname=QtWidgets.QComboBox()
		self.wsetname.setEditable(True)
		psetnames=[i.split("_",1)[1][:-4].replace("_"," ") for i in os.listdir(".") if i[:11]=="filtertool_"]
		try: psetnames.remove("default")  # remove default if it exists
		except: pass
		psetnames.insert(0,"default")     # add it back at the top of the list
		for i in psetnames : self.wsetname.addItem(i)
		self.vblm.addWidget(self.wsetname)
		
		if safemode:
			self.button_doprocess = QtWidgets.QPushButton("Process")
			self.vblm.addWidget(self.button_doprocess)
			self.button_doprocess.clicked.connect(self.on_doprocess)
			

		# scrollarea for processor widget
		self.processorsa=QtWidgets.QScrollArea()
		self.vblm.addWidget(self.processorsa)

		# Actual widget contianing processors being scrolled
		self.processorpanel=QtWidgets.QWidget()
		self.processorsa.setWidget(self.processorpanel)
		self.processorsa.setWidgetResizable(True)
		self.vbl = QtWidgets.QVBoxLayout(self.processorpanel)

		self.processorlist=[]
		self.addProcessor()

		# file menu
#		QtCore.QObject.connect(self.mfile_save_processor,QtCore.SIGNAL("triggered(bool)")  ,self.menu_file_save_processor  )
		self.mfile_save_stack.triggered[bool].connect(self.menu_file_save_stack)
		self.mfile_save_map.triggered[bool].connect(self.menu_file_save_map)
		self.mfile_quit.triggered[bool].connect(self.menu_file_quit)
		self.mview_new_3dwin.triggered[bool].connect(self.menu_add_3dwin)
		self.mview_new_2dwin.triggered[bool].connect(self.menu_add_2dwin)
		self.mview_new_plotwin.triggered[bool].connect(self.menu_add_plotwin)

		self.wsetname.currentIndexChanged[int].connect(self.setChange)


		self.viewer=None			# viewer window for data
		self.processors=[]			# list of processor specifications (name,dict)
		self.origdata=[]
		self.filtdata=[]
		self.nx=0
		self.ny=0
		self.nz=0
		self.busy=False		# used to prevent multiple updates during restore
		self.oldset=None	# currently selected processor set name

		if datafile!=None : self.setData(datafile)

		self.needupdate=1
		self.needredisp=0
		self.lastredisp=1
		self.procthread=None
		self.errors=None		# used to communicate errors back from the reprocessing thread

		self.restore_processorset("default")
		if safemode==False:

			self.timer=QTimer()
			self.timer.timeout.connect(self.timeOut)
			self.timer.start(100)
		else:
			for p in self.processorlist:
				p.wenable.setChecked(False)
			self.on_doprocess()
			
		E2loadappwin("e2filtertool","main",self)

#		QtCore.QObject.connect(self.boxesviewer,QtCore.SIGNAL("mx_image_selected"),self.img_selected)

	def menu_add_3dwin(self):
		if self.viewer==None: return
		self.viewer.append(EMScene3D())
		self.sgdata = EMDataItem3D(test_image_3d(3), transform=Transform())
		self.viewer[-1].insertNewNode('Data', self.sgdata, parentnode=self.viewer[-1])
		isosurface = EMIsosurface(self.sgdata, transform=Transform())
		self.viewer[-1].insertNewNode("Iso", isosurface, parentnode=self.sgdata)
		volslice = EMSliceItem3D(self.sgdata, transform=Transform())
		self.viewer[-1].insertNewNode("Slice", volslice, parentnode=self.sgdata)
		self.viewer[-1].show()
		self.needupdate=1
	
	def menu_add_2dwin(self):
		if self.viewer==None: return
		self.viewer.append(EMImage2DWidget())
		self.viewer[-1].show()
		self.needupdate=1
	
	def menu_add_plotwin(self):
		if self.viewer==None: return
		self.viewer.append(EMPlot2DWidget())
		self.viewer[-1].show()
		self.needupdate=1

	def setChange(self,line):
		"""When the user selects a new set or hits enter after a new name"""
		#print "setchange ",line
		newset=str(self.wsetname.currentText())

		if newset==self.oldset : return

		self.save_current_processorset(self.oldset)
		self.restore_processorset(newset)

	def addProcessor(self,after=-1):
		#print "addProc ",after,len(self.processorlist)
		after+=1
		if after==0 : after=len(self.processorlist)
		epw=EMProcessorWidget(self.processorpanel,tag=after)
		self.processorlist.insert(after,epw)
		self.vbl.insertWidget(after,epw)
		epw.upPress.connect(self.on_upPress)
		epw.downPress.connect(self.on_downPress)
		epw.plusPress.connect(self.on_plusPress)
		epw.minusPress.connect(self.on_minusPress)
		epw.processorChanged.connect(self.procChange)

		# Make sure all the tags are correct
		for i in range(len(self.processorlist)): self.processorlist[i].setTag(i)

	def delProcessor(self,idx):
		#print "delProc ",idx,len(self.processorlist)
		self.vbl.removeWidget(self.processorlist[idx])
		self.processorlist[idx].close()
		del self.processorlist[idx]

		# Make sure all the tags are correct
		for i in range(len(self.processorlist)): self.processorlist[i].setTag(i)

	def swapProcessors(self,tag):
		"This swaps 2 adjacent processors, tag and tag+1"
		w=self.processorlist[tag]
		self.processorlist[tag-1],self.processorlist[tag]=self.processorlist[tag],self.processorlist[tag-1]
		self.vbl.removeWidget(w)
		self.vbl.insertWidget(tag-1,w)

		# Make sure all the tags are correct
		for i in range(len(self.processorlist)): self.processorlist[i].setTag(i)

	def on_upPress(self,tag):
		if tag==0 : return
		self.swapProcessors(tag)

	def on_downPress(self,tag):
		if tag==len(self.processorlist)-1 : return

		self.swapProcessors(tag+1)

	def on_plusPress(self,tag):
		self.addProcessor(tag)

	def on_minusPress(self,tag):
		if len(self.processorlist)==1 : return		# Can't delete the last processor
		self.delProcessor(tag)
		
	def on_doprocess(self):
		try:
			self.reprocess()
		except:
			traceback.print_exc()
			print("processing abort")
		self.redisplay()

	def timeOut(self):
		if self.busy : return

		# Spawn a thread to reprocess the data
		if self.needupdate and (self.procthread==None or not self.procthread.is_alive()):
			self.procthread=threading.Thread(target=self.reprocess)
			self.procthread.start()

		if self.errors:
			QtWidgets.QMessageBox.warning(None,"Error","The following processors encountered errors during processing of 1 or more images:"+"\n".join(self.errors))
			self.errors=None

		# When reprocessing is done, we want to redisplay from the main thread
		if self.needredisp :
			self.needredisp=0
			if self.viewer!=None:
				for v in self.viewer: 
					v.show()
					if isinstance(v,EMImageMXWidget):
						v.set_data(self.procdata)
					elif isinstance(v,EMImage2DWidget):
						if self.procdata[0]["nz"]>1 :
							v.set_data(self.procdata[0])
						else : v.set_data(self.procdata)
					elif isinstance(v,EMScene3D):
						self.sgdata.setData(self.procdata[0])
						v.updateSG()
					elif isinstance(v,EMPlot2DWidget):
						fft=self.procdata[0].do_fft()
						pspec=fft.calc_radial_dist(old_div(self.ny,2),0.0,1.0,1)
						v.set_data((self.pspecs,self.pspecorig),"Orginal",True,True,color=1)
						v.set_data((self.pspecs,pspec),"Processed",color=2)

	def procChange(self,tag):
#		print "change"
		self.needupdate=1
		
	def redisplay(self):
		self.needredisp=0
		if self.viewer!=None:
			for v in self.viewer: 
				v.show()
				if isinstance(v,EMImageMXWidget):
					v.set_data(self.procdata)
				elif isinstance(v,EMImage2DWidget):
					if self.procdata[0]["nz"]>1 :
						v.set_data(self.procdata[0])
					else : v.set_data(self.procdata)
				elif isinstance(v,EMScene3D):
					self.sgdata.setData(self.procdata[0])
					v.updateSG()
				elif isinstance(v,EMPlot2DWidget):
					fft=self.procdata[0].do_fft()
					pspec=fft.calc_radial_dist(old_div(self.ny,2),0.0,1.0,1)
					v.set_data((self.pspecs,self.pspecorig),"Orginal",True,True,color=1)
					v.set_data((self.pspecs,pspec),"Processed",color=2)

	def reprocess(self):
		"Called when something about a processor changes (or when the data changes)"

		if self.busy: return
	
		# if all processors are disabled, we return without any update
		#for p in self.processorlist:
			#if p.processorParms()!=None : break
		#else: return
	
		self.needupdate=0		# we set this immediately so we reprocess again if an update happens while we're processing
		# we fully process before putting it back into self.procdata
		tmp=[im.copy() for im in self.origdata]

		needred=0
		errors=[]
		for p in self.processorlist:
			if self.needupdate : return		# abort if another update is triggered
			pp=p.processorParms()				# processor parameters
			if pp==None: continue				# disabled processor
			proc=Processors.get(pp[0],pp[1])	# the actual processor object
#			print pp

			errflag=False
			if pp[0] in outplaceprocs:
				errflag=False
				try:
					tmp=[proc.process(im) for im in tmp]
				except:
					errflag=True
			else:
				for im in tmp:
					if self.needupdate : return		# abort if another update is triggered
					try: proc.process_inplace(im)
					except: 
						errflag=True
						break
				
			if errflag: errors.append(str(pp))
			needred=1					# if all processors are disabled, we don't want a redisplay
			self.lastredisp=1

		if len(errors)>0 :
			self.errors=errors
		else: self.procdata=tmp

		self.needredisp=max(needred,self.lastredisp)
		self.lastredisp=needred
		self.procthread=None					# This is a reference to ourselves (the thread doing the processing). we reset it ourselves before returning

	def setData(self,data):
		if data==None :
			self.data=None
			return

		elif isinstance(data,str) :
			self.datafile=data
			self.nimg=EMUtil.get_image_count(data)
			
			if self.dataidx>=0 and self.dataidx<self.nimg:
				ii=self.dataidx
				self.nimg=1
			else:
				ii=0
			
			hdr=EMData(data,0,1)

			self.origdata=EMData(data,ii)

			if self.origdata["nz"]==1:
				if self.nimg>20 and hdr["ny"]>512:
					self.origdata=EMData.read_images(data,list(range(0,self.nimg,self.nimg//20)))		# read regularly separated images from the file totalling ~20
				elif self.nimg>100:
					self.origdata=EMData.read_images(data,list(range(0,self.nimg,self.nimg//100)))		# read regularly separated images from the file					
				elif self.nimg>1 :
					self.origdata=EMData.read_images(data,list(range(self.nimg)))
				else: self.origdata=[self.origdata]
			else :
				self.origdata=[self.origdata]

		else :
			self.datafile=None
			if isinstance(data,EMData) : self.origdata=[data]
			else : self.origdata=data

		self.nx=self.origdata[0]["nx"]
		self.ny=self.origdata[0]["ny"]
		self.nz=self.origdata[0]["nz"]
		if self.apix<=0.0 : self.apix=self.origdata[0]["apix_x"]
		EMProcessorWidget.parmdefault["apix"]=(0,(0.2,10.0),self.apix,None)

		origfft=self.origdata[0].do_fft()
		self.pspecorig=origfft.calc_radial_dist(old_div(self.ny,2),0.0,1.0,1)
		ds=old_div(1.0,(self.apix*self.ny))
		self.pspecs=[ds*i for i in range(len(self.pspecorig))]


		if self.viewer!=None : 
			for v in self.viewer: v.close()
			
		if self.nz==1 or self.force2d or (self.nx>320 and self.safemode==False):
			if len(self.origdata)>1 :
				self.viewer=[EMImageMXWidget()]
				self.mfile_save_stack.setEnabled(True)
			else :
				self.viewer=[EMImage2DWidget()]
				self.mfile_save_stack.setEnabled(False)
		else :
			self.mfile_save_stack.setEnabled(False)
			self.viewer = [EMScene3D()]
			self.sgdata = EMDataItem3D(test_image_3d(3), transform=Transform())
			self.viewer[0].insertNewNode('Data', self.sgdata, parentnode=self.viewer[0])
			isosurface = EMIsosurface(self.sgdata, transform=Transform())
			self.viewer[0].insertNewNode("Iso", isosurface, parentnode=self.sgdata)
			volslice = EMSliceItem3D(self.sgdata, transform=Transform())
			self.viewer[0].insertNewNode("Slice", volslice, parentnode=self.sgdata)

		if self.nz>1 : self.mfile_save_map.setEnabled(True)
		else : self.mfile_save_map.setEnabled(False)

		E2loadappwin("e2filtertool","image",self.viewer[0].qt_parent)
		if self.origdata[0].has_attr("source_path"):
			winname=str(self.origdata[0]["source_path"])
		else:
			winname="FilterTool"
		self.viewer[0].setWindowTitle(winname)

		self.procChange(-1)

	def save_current_processorset(self,name):
		"""Saves the current processor and parameters to a text file"""
#		print "saveset ",name

		try: out=open("filtertool_%s.txt"%(name.replace(" ","_")),"w")	# overwrite the current contents
		except:
			traceback.print_exc()
			print("No permission to store processorset info")
			return

		out.write("# This file contains the parameters for the processor set named\n# %s\n# Each of the --process lines below is in the correct syntax for use with e2proc2d.py or e2proc3d.py.\n# Use the full set sequentially in a single command to replicate the processor set\n\n"%name)

		for filt in self.processorlist:
			ftext=filt.getAsText()
			if ftext!=None : out.write(ftext)

		out.close()

	def restore_processorset(self,name):
		"""This restores a processorset that has been written to a text file"""
		# Erase all existing processors
#		print "loadset ",name

		self.oldset=name

		self.busy=True
		while len(self.processorlist)>0 : self.delProcessor(0)

		# Open the file
		try: infile=open("filtertool_%s.txt"%(name.replace(" ","_")),"r")
		except:
			self.addProcessor()
			self.busy=False
			return		# file can't be read, must be a new set (or we'll assume that)

		while 1:
			l=infile.readline()
			if l=="" : break
			if l[:2]=="#$" :								# This indicates the start of a new processor
				l=[l.strip(),infile.readline().strip(),infile.readline().strip()]
				self.addProcessor()
				self.processorlist[-1].setFromText(l)

		if len(self.processorlist)==0 : self.addProcessor()

		self.busy=False
		self.needupdate=1

	def menu_file_save_processor(self):
		"Saves the processor in a usable form to a text file"
		#out=file("processor.txt","a")
		#out.write("Below you will find the processor options in sequence. They can be passed together in order\nas options to a single e2proc2d.py or e2proc3d.py command to achieve the\nsame results as in e2filtertool.py\n")
		#for p in self.processorlist:
			#pp=p.processorParms()				# processor parameters
			#if pp==None : continue
			#out.write("--process=%s"%pp[0])
			#for k in pp[1]:
				#out.write(":%s=%s"%(k,str(pp[1][k])))
			#out.write("\n")
		#out.write("\n")
		#out.close()

		#QtWidgets.QMessageBox.warning(None,"Saved","The processor parameters have been added to the end of 'processor.txt'")

		self.save_current_processorset(str(self.wsetname.currentText()))

	def menu_file_save_stack(self):
		"Processes the entire current stack, and saves as a new name"

		name=QtWidgets.QInputDialog.getText(None,"Enter Filename","Enter an output filename for the entire processed particle stack (not just the displayed images).")
		if not name[1] : return		# canceled

		allfilt=" ".join([i.getAsProc() for i in self.processorlist])

		n=EMUtil.get_image_count(self.datafile)
		progressdialog=QtWidgets.QProgressDialog("Processing Images","Abort",0,n,self)
		progressdialog.setMinimumDuration(1000)

		e=E2init(["e2proc2d.py",self.datafile,str(name[0]),allfilt])	# we don't actually run this program, since we couldn't have a progress dialog easo;y then

		pp=[i.processorParms() for i in self.processorlist]

		for i in range(n):
			im=EMData(self.datafile,i)
			QtWidgets.qApp.processEvents()
			for p in pp: 
				if p[0] in outplaceprocs:
					im=im.process(p[0],p[1])
				else: im.process_inplace(p[0],p[1])
			im.write_image(str(name[0]),i)
			progressdialog.setValue(i+1)
			if progressdialog.wasCanceled() :
				print("Processing Cancelled")
				break

		progressdialog.setValue(n)

		E2end(e)

	def menu_file_save_map(self):
		"saves the current processored map"

		if len(self.procdata)==1 and self.procdata[0]["nz"]>1 :
			try: os.unlink("processed_map.hdf")
			except : pass
			self.procdata[0].write_image("processed_map.hdf",0)
			QtWidgets.QMessageBox.warning(None,"Saved","The processed map has been saved as processed_map.hdf")
		else :
			try: os.unlink("processed_images.hdf")
			except: pass
			for i in self.procdata: i.write_image("processed_images.hdf",-1)
			QtWidgets.QMessageBox.warning(None,"Saved","The processed image(s) has been saved as processed_images.hdf. WARNING: this will include only be a subset of the images in a large image stack. To process the full stack, use e2proc2d.py with the options in filtertool_<filtername>.txt")

	def menu_file_quit(self):
		self.close()

	def closeEvent(self,event):
		E2saveappwin("e2filtertool","main",self)
		self.save_current_processorset(str(self.wsetname.currentText()))

#		print "Exiting"
		if self.viewer!=None :
			E2saveappwin("e2filtertool","image",self.viewer[0].qt_parent)
			for v in self.viewer:
				v.close()
		event.accept()
		#self.app().close_specific(self)
		self.module_closed.emit() # this signal is important when e2ctf is being used by a program running its own event loop

	#def closeEvent(self,event):
		#self.target().done()


pix_plus=None
pix_up=None
pix_down=None
pix_minus=None

def pix_init():
	global pix_plus,pix_minus,pix_up,pix_down

	pix_plus=QtGui.QIcon(QtGui.QPixmap(["15 15 3 1",
	" 	c None",
	".	c black",
	"X	c grey",
	"               ",
	"               ",
	"               ",
	"               ",
	"       .       ",
	"       .X      ",
	"       .X      ",
	"    .......    ",
	"     XX.XXXX   ",
	"       .X      ",
	"       .X      ",
	"        X      ",
	"               ",
	"               ",
	"               "
	]))

	pix_up=QtGui.QIcon(QtGui.QPixmap(["15 15 3 1",
	" 	c None",
	".	c black",
	"X	c grey",
	"               ",
	"               ",
	"               ",
	"       .       ",
	"      ...      ",
	"     .....     ",
	"    .......    ",
	"    XXX.XXXX   ",
	"       .X      ",
	"       .X      ",
	"       .X      ",
	"       .X      ",
	"        X      ",
	"               ",
	"               "
	]))

	pix_down=QtGui.QIcon(QtGui.QPixmap(["15 15 3 1",
	" 	c None",
	".	c black",
	"X	c grey",
	"               ",
	"               ",
	"               ",
	"       .       ",
	"       .X      ",
	"       .X      ",
	"       .X      ",
	"       .X      ",
	"    .......    ",
	"     .....X    ",
	"      ...X     ",
	"       .X      ",
	"               ",
	"               ",
	"               "
	]))

	pix_minus=QtGui.QIcon(QtGui.QPixmap(["15 15 3 1",
	" 	c None",
	".	c black",
	"X	c grey",
	"               ",
	"               ",
	"               ",
	"               ",
	"               ",
	"               ",
	"               ",
	"    .......    ",
	"     XXXXXXX   ",
	"               ",
	"               ",
	"               ",
	"               ",
	"               ",
	"               "
	]))

if __name__ == "__main__":
	main()



