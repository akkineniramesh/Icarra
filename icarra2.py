'''Copyright (c) 2006-2010, Jesse Liesch
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the author nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE IMPLIED
DISCLAIMED. IN NO EVENT SHALL JESSE LIESCH BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

This is the main module for the Icarra investment software.  The most
important files/modules are:

appGlobal.py: Implements several helper functions such as returning the
	active application (and thus the current portfolio and stock data
	classes).

transaction.py: Implements the Transction class.  Transactions are the heart
	of any portfolio.  All holdings and returns are computed directly from a
	portfolio's transactions.  Transactions are typically imported from an
	OFX or broker-specific CSV file.

portfolio.py: Implements the Portfolio class.  The Portfolio class contains
	the portfolio's transactions and returns as well as a number of other
	useful functions.  The portfolio class is the most important class for
	accessing portfolio data.

stockData.py: Implements the StockData class.  Used by the portfolio class
	and other modules to retrieve stock quotes, dividends and splits.

plugin.py: Defines the Plugin base class.  All Icarra tools are plugins.

brokerage.py: Defines the Brokerage base class.  This class defines how
	transactions are automatically imported via OFX and any additional
	broker-specific behavior.

editGrid.py: implements the EditGrid class.  Used to display table data.

'''

import sys
import os
import uuid
import time
import datetime
import mutex
import traceback
import locale

locale.setlocale(locale.LC_ALL, "")

# Check that all required components are available
try:
	from PyQt4.QtCore import *
	from PyQt4.QtGui import *
	from PyQt4.QtWebKit import *
	from PyQt4.QtNetwork import *
except:
	print "Icarra requires PyQt version 4.4 or higher"
	sys.exit(-1)

try:
	import keyring
except:
	# Ignore missing keyring, not critical
	pass

try:
	import sgmlop 
except:
	print "Icarra requires the sgmlop library"
	sys.exit(-1)

try:
	import json
	import jsonrpc
except:
	print "Icarra requires the jsonrpc library"
	sys.exit(-1)

try:
	import feedparser
except:
	print "Icarra requires the feedparser library"
	sys.exit(-1)

# For chart director
if sys.platform.startswith("darwin"):
	sys.path.append("lib/darwin")
if sys.platform.startswith("win"):
	if not hasattr(sys, "frozen"):
		sys.path.append(os.path.join(sys.path[0], "lib\win32"))
if sys.platform.startswith("linux"):
	sys.path.append("lib/linux32")

from editGrid import *
from prefs import *
from portfolio import *
from stockData import *
from statusUpdate import *
from pluginManager import *
from helpFrame import *
from aboutDialog import *
from splashScreenFrame import *
from newPortfolioFrame import *
import newVersionFrame
from ofxDebugFrame import *
from prefsFrame import *
import tutorial

import appGlobal
import autoUpdater

# For dependencies when building standalone apps
import plugin
import feedparser
import chartWidget
import webbrowser
import icarraWebBrowser

class ToolSelectorDelegate(QItemDelegate):
	'''Increase the height of each tool in the tool selector by 10 pixels'''
	def __init__(self, parent):
		QItemDelegate.__init__(self, parent)
		self.myHint = False
	
	def sizeHint(self, option, index):
		if self.myHint:
			return self.myHint
		
		# Increase height by 10
		self.myHint = QItemDelegate.sizeHint(self, option, index)
		self.myHint.setHeight(self.myHint.height() + 10)
		return self.myHint

class ToolSelector(QListView):
	''''ToolSelector implements the tool selection box found on the left-hand side of the main Icarra window.'''
	def __init__(self, parent = None):
		QWidget.__init__(self, parent)

		self.tools = []
		self.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.setSelectionMode(QListView.SingleSelection)
		self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding))

		self.setSpacing(0)
		self.selectorDelegate = ToolSelectorDelegate(self)
		self.setItemDelegate(self.selectorDelegate)

		if appGlobal.getApp().isOSX:
			font = self.font()
			font.setPointSize(13)
			font.setBold(True)
			self.setFont(font)

			self.setStyleSheet("QListView::item { color: #444444; background: white; border: 1px solid white; } QListView::item:selected:active { background: #d8d8ff; border: 1px solid gray; }")
		elif appGlobal.getApp().isWindows:
			font = self.font()
			font.setBold(True)
			self.setFont(font)

			self.setStyleSheet("QListView::item { color: #444444; background: white; } QListView::item:selected { background: #d8d8ff; }")
		else:
			self.setStyleSheet("QListView::item { color: #444444; background: white; } QListView::item:selected{ background: #d8d8ff; }")
	
	def rebuild(self):
		'''Search for all available plugins and add them to the tool selector.'''
		self.tools = []
		for plugin in getApp().plugins.getPlugins():
			if appGlobal.getApp().portfolio.isBank() and plugin.forBank():
				self.addTool(plugin.name())
			elif not appGlobal.getApp().portfolio.isBank() and plugin.forInvestment():
				self.addTool(plugin.name())
		self.finishAdd()
	
	def addTool(self, name):
		'''Add a tool to the tool selector.'''
		self.tools.append(name)
	
	def finishAdd(self):
		'''Finish rebuilding tool selector.  Call this function when all tools hae been added.'''
		self.myModel = QStringListModel(self.tools)
		self.setModel(self.myModel)
		self.connect(self.selectionModel(), SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), self.newSelection)
	
	def newSelection(self, old, new):
		'''Slot for selectionChanged'''
		row = self.selectedIndexes()[0].row()
		self.loadTool(self.tools[row])
	
	def selectTool(self, name):
		'''Select a tool by plug in name, changing the active selection.  Qt will eventually call loadTool on the selected tool.'''
		try:
			index = self.model().index(self.tools.index(name))
		except:
			if not "Summary" in self.tools:
				raise Exception("Could not find builtinPlugins directory")
			index = self.model().index(self.tools.index("Summary"))
		self.selectionModel().setCurrentIndex(index, QItemSelectionModel.ClearAndSelect)
	
	def getSelectedTool(self):
		'''Return the active tool (plugin name)'''
		return self.tools[self.selectionModel().currentIndex().row()]
	
	def loadTool(self, tool):
		'''Loads a new tool (plugin name) and may rebuild the portfolio if it is dirty'''
		# Check for rebuilding portfolio if it's dirty
		# Don't rebuild if background rebuilding is enabled
		app = appGlobal.getApp()
		app.main.setCursor(Qt.WaitCursor)
		if app.portfolio.portPrefs.getDirty() and not tool in ["Transactions", "Settings", "News"] and not app.prefs.getBackgroundRebuild():
			p =  app.portfolio

			# Only show update window if app is started
			if app.started:
				update = StatusUpdate(app.main, modal = False, closeOnFinish = True)

				update.setStatus("Rebuilding " + p.name)
				update.setSubTask(100)
			else:
				update = False

			p.rebuildPositionHistory(app.stockData, update)
			if update:
				update.finishSubTask("Finished rebuilding " + p.name)

		app.prefs.setLastTab(tool)
		app.tool = app.plugins.getPlugin(tool)
	
		# Remove old tool
		if app.toolWidget:
			app.toolWidget.deleteLater()
			app.main.toolLayout.removeWidget(app.toolWidget)

		# Add new tool
		try:
			app.toolWidget = app.tool.createWidget(app.main)
		except Exception, inst:
			app.toolWidget = QLabel("Error while loading plugin: %s\n%s" % (inst, "".join(traceback.format_exc())))
		if app.toolWidget:
			app.main.toolLayout.addWidget(app.toolWidget)
		app.main.splitter.setSizes([200, app.prefs.getWidth() - 200])
		app.main.setCursor(Qt.ArrowCursor)
		app.checkThreadSafeError()

class MainWindow(QMainWindow):
	def __init__(self):
		QMainWindow.__init__(self)
	
	def render(self):
		'''Initialize the main window.  Create all widgets.'''
		self.setWindowTitle('Icarra 2')
		self.setMinimumSize(QSize(400, 300))
		
		central = QWidget(self)
		vbox = QVBoxLayout(central)
		vbox.setMargin(0)
		vbox.setSpacing(0)
		self.setCentralWidget(central)
		
		# Create splitter
		self.splitter = QSplitter()
		self.splitter.setContentsMargins(10, 10, 10, 10)
		vbox.addWidget(self.splitter)
		#self.setCentralWidget(self.splitter)
		
		# Create menus
		self.fileMenu = QMenu("File")
		self.menuBar().addMenu(self.fileMenu)

		exit = QAction("Exit", self)
		exit.setMenuRole(QAction.QuitRole)
		exit.setShortcut("Ctrl+Q")
		exit.setStatusTip("Exit Icarra2")
		self.fileMenu.addAction(exit)
		self.connect(exit, SIGNAL("triggered()"), self.exit)

		about = QAction("About...", self)
		about.setMenuRole(QAction.AboutRole)
		about.setStatusTip("About Icarra2")
		self.fileMenu.addAction(about)
		self.connect(about, SIGNAL("triggered()"), self.about)

		prefsMenu = QAction("Preferences...", self)
		prefsMenu.setMenuRole(QAction.PreferencesRole)
		prefsMenu.setStatusTip("Preferences")
		self.fileMenu.addAction(prefsMenu)
		self.connect(prefsMenu, SIGNAL("triggered()"), self.preferences)

		help = QAction("Help...", self)
		help.setMenuRole(QAction.ApplicationSpecificRole)
		help.setStatusTip("Icarra Help")
		self.fileMenu.addAction(help)
		self.connect(help, SIGNAL("triggered()"), self.help)

		# Create tool selector
		self.ts = ToolSelector()
		self.splitter.addWidget(self.ts)
		
		# Create tool holder
		self.toolHolder = QWidget(self.splitter)
		self.toolLayout = QVBoxLayout(self.toolHolder)
		self.toolLayout.setMargin(0)

		self.resize(prefs.getWidth(), prefs.getHeight())
	
	def resizeEvent(self, event):
		'''resizeEvent slot.  Save main window width and height.'''
		w = self.size().width()
		h = self.size().height()
		if w != prefs.getWidth() or h != prefs.getHeight():
			prefs.setSize(w, h)

	def exit(self):
		'''Safely shut down Icarra'''
		# Stop downloading data, rebuilding portfolios
		# There may be a small delay while the current task completes
		autoUpdater.stop(join = False)
		
		# Wait for background task to complete (if any)
		app = appGlobal.getApp()
		task = app.getBigTask()
		if task:
			startWait = datetime.datetime.now()
			status = StatusUpdate(self, closeOnFinish = True)
			status.setStatus("Waiting while we finish " + task + "...", 10)
			status.appYield()
			while task or not autoUpdater.finished():
				time.sleep(1)
				seconds = (datetime.datetime.now() - startWait).seconds
				status.setStatus(level = 100 - 90 / math.sqrt(seconds))
				status.appYield()
				task = app.getBigTask()
			status.setFinished()
		
		QCoreApplication.exit()

	def closeEvent(self, event):
		'''closeEvent slot.  Safely shut down.'''
		self.exit()
	
	def about(self):
		about = AboutDialog(self)
	
	def help(self):
		help = HelpFrame()

	def preferences(self):
		p = PrefsFrame(self)

global prefs
prefs = Prefs()

class Icarra2(QApplication):
	def __init__(self, *args):
		global prefs
		self.started = False

		self.isOSX = sys.platform.startswith("darwin")
		self.isWindows = sys.platform.startswith("win")
		self.isLinux = sys.platform.startswith("linux")

		QApplication.__init__(self, *args)
		self.setApplicationName('Icarra2')
		self.setQuitOnLastWindowClosed(False)

		# Set locale one more time, QT may override it
		locale.setlocale(locale.LC_ALL, "")

		# Set global app and path
		if hasattr(sys, "frozen"):
			appPath = os.path.dirname(sys.argv[0])
		else:
			appPath = os.path.abspath(os.path.dirname(sys.argv[0]))
		appGlobal.setApp(self, appPath)
		
		# For thread safe errors
		self.errorMutex = threading.Lock()
		self.errorList = []
		
		# For checking tables
		self.checkTableMutex = threading.Lock()
		
		# For starting and ending big tasks
		self.bigTask = False
		self.bigTaskCondition = threading.Condition()
		
		# The current statusUpdate dialog, if any
		self.statusUpdate = False
		
		# Initialize members
		self.prefs = prefs
		self.stockData = StockData()
		self.ofxDebugFrame = False
		self.portfolio = False
		self.tool = False
		self.toolWidget = False
		
		# If we notified the user that we failed to connect to the icarra server
		self.notifieldFailConnected = False

		self.positiveColor = QColor(0, 153, 0)
		self.negativeColor = QColor(204, 0, 0)
		self.alternateRowColor = QColor(216, 216, 255)

		# Make sure benchmarks have been created
		checkBenchmarks(prefs)
		
		# Dictionary of portfolios used for rebuilding portfolio menu
		# So we don't have to open portfolios every time
		# Key is portfolio name, value is portfolio type ("benchmark", "bank", "brokerage", "combined")
		self.buildPortfolioMenuNames()
		
		# Nothing else if regression
		if "--regression" in args[0] or "--broker-info" in args[0] or "--rebuild" in args[0] or "--import" in args[0]:
			return

		self.plugins = PluginManager()
		
		timesRun = prefs.getTimesRun()
		splashTime = datetime.datetime.now()
		if timesRun > 0:
			# Start updater now so we can get stock data
			autoUpdater.start(self.stockData, self.prefs)

			self.splash = SplashScreenFrame()
		else:
			self.createSamplePortfolio()
			
			# Set all stocks as not having been downloaded
			# This is important incase the startup process failed
			self.stockData.db.query("update stockInfo set lastDownload='1900-01-01 00:00:00'")

			# Start after creating sample portfolio
			autoUpdater.start(self.stockData, self.prefs)

			# Load initial data, make sure we got it
			self.splash = SplashScreenFrame(firstTime = True)
			if not self.splash.running:
				autoUpdater.stop()
				self.splash.close()
				self.started = False
				message = QMessageBox(QMessageBox.Critical, "Connection error", "Unable to connect to the Icarra web server.  Please check your internet connection and try again.", flags = Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowStaysOnTopHint)
				message.exec_()
				return

		self.main = MainWindow()
		self.processEvents()

		self.main.render()
		self.processEvents()
		
		self.rebuildPortfoliosMenu()

		self.loadPortfolio(prefs.getLastPortfolio())
		self.processEvents()

		if self.prefs.getOfxDebug():
			self.startOfxDebug()

		if self.splash and timesRun == 0:
			self.splash.progress.setValue(100)

		self.checkVersion()

		self.processEvents()

		# Wait up to 2 seconds before hiding splash screen
		elapsedMs = (datetime.datetime.now() - splashTime).microseconds / 1000
		if self.splash and elapsedMs < 3000:
			self.timer = QTimer()
			interval = 3000 - elapsedMs
			self.timer.setInterval(interval)
			self.timer.setSingleShot(True)
			self.connect(self.timer, SIGNAL("timeout()"), self.hideSplash)
			self.timer.start()
		else:
			self.hideSplash()
		
		# Start timer to check for failed connected
		self.failTimer = QTimer()
		self.failTimer.setInterval(3000)
		self.connect(self.failTimer, SIGNAL("timeout()"), self.checkFailTimer)
		self.failTimer.start()

		self.prefs.incTimesRun()
		appGlobal.getApp().started = True
			
	def checkIntro(self):
		'''Check for showing the tutorial introduction'''
		tutorial.check(tutorial.intro)

	def createSamplePortfolio(self):
		'''Create a sample portfolio of AAPL and XOM stock'''
		# Check that not already created
		if prefs.hasPortfolio("Sample Portfolio"):
			return
		
		prefs.addPortfolio("Sample Portfolio")
		prefs.setLastTab("Summary")
		prefs.setLastPortfolio("Sample Portfolio")
		p = Portfolio("Sample Portfolio")
		p.db.beginTransaction()

		t = Transaction(1, "__CASH__", datetime.datetime(2008, 1, 2), Transaction.deposit, amount = 20000)
		t.save(p.db)

		t = Transaction(2, "AAPL", datetime.datetime(2008, 1, 2), Transaction.buy, amount = 10000, shares = 50, pricePerShare = 200, fee = 0)
		t.save(p.db)

		shares = 107.52688172043
		t = Transaction(3, "XOM", datetime.datetime(2008, 1, 2), Transaction.buy, amount = 10000, shares = shares, pricePerShare = 93, fee = 0)
		t.save(p.db)

		t = Transaction(4, "XOM", datetime.datetime(2008, 2, 7), Transaction.dividend, amount = shares * 0.35)
		t.save(p.db)

		t = Transaction(5, "XOM", datetime.datetime(2008, 3, 9), Transaction.dividend, amount = shares * 0.4)
		t.save(p.db)

		t = Transaction(6, "XOM", datetime.datetime(2008, 8, 11), Transaction.dividend, amount = shares * 0.4)
		t.save(p.db)

		t = Transaction(7, "XOM", datetime.datetime(2008, 11, 7), Transaction.dividend, amount = shares * 0.4)
		t.save(p.db)

		t = Transaction(8, "XOM", datetime.datetime(2009, 3, 11), Transaction.dividend, amount = shares * 0.42)
		t.save(p.db)

		t = Transaction(9, "XOM", datetime.datetime(2009, 8, 11), Transaction.dividend, amount = shares * 0.42)
		t.save(p.db)

		t = Transaction(10, "XOM", datetime.datetime(2009, 11, 9), Transaction.dividend, amount = shares * 0.42)
		t.save(p.db)

		t = Transaction(11, "XOM", datetime.datetime(2010, 2, 8), Transaction.dividend, amount = shares * 0.42)
		t.save(p.db)

		t = Transaction(12, "XOM", datetime.datetime(2010, 3, 11), Transaction.dividend, amount = shares * 0.44)
		t.save(p.db)

		t = Transaction(13, "XOM", datetime.datetime(2010, 8, 11), Transaction.dividend, amount = shares * 0.44)
		t.save(p.db)

		t = Transaction(14, "XOM", datetime.datetime(2010, 11, 9), Transaction.dividend, amount = shares * 0.44)
		t.save(p.db)

		p.db.commitTransaction()
	
	def hideSplash(self):
		'''Finish initializing the main app.  Hide the splash screen, show the main window.'''
		if self.splash:
			self.splash.close()
		self.main.show()
		self.main.raise_()
		
		# Set timer for tutorial
		# Wait a little while to give everything a chance to display
		self.tutorialTimer = QTimer()
		self.tutorialTimer.setInterval(500)
		self.tutorialTimer.setSingleShot(True)
		self.connect(self.tutorialTimer, SIGNAL("timeout()"), self.checkIntro)
		self.tutorialTimer.start()
	
	def beginBigTask(self, description, status = False):
		'''Begin a new big task.  This function may be called by any thread at any time.
		
		A big task is something that should stop another thread from performing another big task.  Examples include downloading stock data, rebuilding portfolios and importing transactions.
		
		'''
		# Get the bigTask mutex
		# Check if we're currently doing anything big
		# If so, wait for it to finish
		self.bigTaskCondition.acquire()
		while self.bigTask:
			if status:
				status.setStatus('Waiting while we finish ' + self.bigTask + '...')
			self.bigTaskCondition.wait(1)
		self.bigTask = description
		self.bigTaskCondition.release()
	
	def endBigTask(self):
		'''End a big task.  This function may be called by any thread at any time.'''
		# We're no longer doing anything big
		# Wake up anyone who is waiting
		self.bigTaskCondition.acquire()
		self.bigTask = False
		self.bigTaskCondition.notify()
		self.bigTaskCondition.release()

	def getBigTask(self):
		'''Return the current big task, or False if no big task.'''
		self.bigTaskCondition.acquire()
		task = self.bigTask
		self.bigTaskCondition.release()
		return task

	def checkFailTimer(self):
		'''Check if we failed to connect to the Icarra server'''
		if appGlobal.getFailConnected() and not self.notifieldFailConnected:
			self.notifieldFailConnected = True
			
			QMessageBox(QMessageBox.Critical, "Could not connect", "Icarra could not connect to the stock data server.  You may continue using Icarra but new stock data will not be downloaded until Icarra has been restarted.").exec_()

	def loadPortfolio(self, name):
		'''Load a portfolio'''
		global prefs
		prefs.setLastPortfolio(name)
				
		# Remove old portfolio
		if self.portfolio:
			del self.portfolio
			self.portfolio = False

		# Set title and check/uncheck menus
		self.main.setWindowTitle('Icarra - ' + name)
		for a in self.portfoliosMenu.actions():
			a.setChecked(a.text().replace("&&", "&") == name)

		try:
			try:
				self.portfolio = Portfolio(name)
			except:
				self.portfolio = Portfolio("S&P 500")
			self.portfolio.readFromDb()
	
			self.main.ts.rebuild()

			# Load tool
			self.main.ts.selectTool(prefs.getLastTab())
			
			# Enable or disable Import Transactions menu
			if self.portfolio.isBrokerage() and not self.portfolio.isBank():
				self.importTransactionsAction.setEnabled(True)
			else:
				self.importTransactionsAction.setEnabled(False)
		except Exception, e:
			self.toolWidget = QLabel("Error while loading plugin: %s\n%s" % (e, "".join(traceback.format_exc())))
			self.main.toolLayout.addWidget(self.toolWidget)
		
		self.rebuildPortfoliosMenu(load = True)
	
	def selectPortfolio(self, t):
		'''Select an item from the portfolio menu'''
		# Check for new portfolio using shortcut
		if t.shortcut() == "CTRL+N":
			d = NewPortfolio(self.main)
			d.exec_()
		elif t.shortcut() == "CTRL+I":
			# Import, ignore here, handled by other slot
			pass
		elif t.shortcut() == "CTRL+R":
			# Rebuild, ignore here, handled by other slot
			pass
		elif t == self.deleteAction:
			# Delete portfolio, handled by other slot
			pass
		else:
			name = str(t.text())
			name = name.replace("&&", "&")
			self.loadPortfolio(name)

	def importTransactions(self):
		'''Import transaction slot, import transactions for the current portfolio'''
		brokerage = self.plugins.getBrokerage(self.portfolio.brokerage)
		if not brokerage:
			print "no brokerage"

		self.plugins.getPlugin("Transactions").doImport()
	
	def deletePortfolio(self):
		'''Show the portfolio delete dialog and possibly delete the portfolio'''

		class DeletePortfolioDialog(QDialog):
			def __init__(self, parent):
				QDialog.__init__(self, parent)
				self.setWindowTitle("Delete Portfolio")
				self.doDelete = False
				
				vbox = QVBoxLayout(self)
				
				vbox.addWidget(QLabel("Delete this portfolio?  Are you sure?"))
				vbox.addSpacing(10)
		
				vbox.addWidget(QLabel("Type \"delete\" into the text box:"))
				self.line = QLineEdit()
				self.connect(self.line, SIGNAL("textChanged(QString)"), self.lineChanged)
				vbox.addWidget(self.line)
				vbox.addSpacing(5)

				hor = QHBoxLayout()
				hor.addStretch(1000)
				vbox.addLayout(hor)
				
				cancel = QPushButton("Cancel")
				cancel.setDefault(True)
				hor.addWidget(cancel)
				self.connect(cancel, SIGNAL("clicked()"), SLOT("reject()"))
		
				self.delete = QPushButton("Delete")
				self.delete.setDisabled(True)
				hor.addWidget(self.delete)
				self.connect(self.delete, SIGNAL("clicked()"), self.onDelete)
		
				self.exec_()
			
			def lineChanged(self, text):
				if str(text).lower() == "delete":
					self.delete.setEnabled(True)
				else:
					self.delete.setEnabled(False)
			
			def onDelete(self):
				self.doDelete = True
				self.close()
		
		delete = DeletePortfolioDialog(self.main)
		if delete.doDelete:
			self.portfolio.delete(self.prefs)
			del self.portfolioMenuNames[self.portfolio.name]
			self.loadPortfolio("S&P 500")
			self.rebuildPortfoliosMenu()

	def rebuildPortfolio(self):
		'''Rebuild the active portfolio'''
		
		p =  self.portfolio
		update = StatusUpdate(app.main, modal = False)
		
		update.setStatus("Rebuilding " + p.name)

		update.setSubTask(100)
		p.rebuildPositionHistory(app.stockData, update)
		update.finishSubTask("Finished rebuilding " + p.name)
	
	def buildPortfolioMenuNames(self):
		'''Cache the names of all portfolios'''
		self.portfolioMenuNames = {}
		for name in prefs.getPortfolios():
			p = Portfolio(name)
			if not p:
				continue

			if p.isBenchmark():
				self.portfolioMenuNames[name] = "benchmark"
			else:
				self.portfolioMenuNames[name] = "other"
			

	def rebuildPortfoliosMenu(self, load = True):
		'''Rebuild the portfolios menu.  Called at startup and when adding/deleting/renaming a portfolio.'''
		global prefs
		
		# Add or clear menu
		if "portfoliosMenu" in dir(self):
			self.portfoliosMenu.clear()
		else:
			self.portfoliosMenu = QMenu("Portfolio", self.main)
			self.connect(self.portfoliosMenu, SIGNAL("triggered(QAction*)"), self.selectPortfolio)
			self.main.menuBar().addMenu(self.portfoliosMenu)
		
		n = QAction("New Portfolio", self.main)
		n.setShortcut("CTRL+N")
		self.portfoliosMenu.addAction(n)

		self.deleteAction = QAction("Delete Portfolio", self.main)
		if self.portfolio and self.portfolio.name == "S&P 500":
			self.deleteAction.setDisabled(True)
		self.portfoliosMenu.addAction(self.deleteAction)
		self.connect(self.deleteAction, SIGNAL("triggered()"), self.deletePortfolio)

		self.importTransactionsAction = QAction("Import Transactions", self.main)
		self.importTransactionsAction.setShortcut("CTRL+I")
		if self.portfolio and not self.portfolio.isBrokerage():
			self.importTransactionsAction.setEnabled(False)
		self.portfoliosMenu.addAction(self.importTransactionsAction)
		self.connect(self.importTransactionsAction, SIGNAL("triggered()"), self.importTransactions)

		reb = QAction("Rebuild Portfolio", self.main)
		reb.setShortcut("CTRL+R")
		self.portfoliosMenu.addAction(reb)
		self.portfoliosMenu.addSeparator()
		self.connect(reb, SIGNAL("triggered()"), self.rebuildPortfolio)
		
		benchmarks = []
		addedPort = False
		self.portfolioActions = {}
		for name in sorted(self.portfolioMenuNames.keys()):
			self.portfolioActions[name] = QAction(name, self)

			a = QAction(name.replace("&", "&&"), self.main)
			a.setCheckable(True)
			if self.portfolioMenuNames[name] == "benchmark":
				benchmarks.append(a)
			else:
				self.portfoliosMenu.addAction(a)
				addedPort = True
			if name == prefs.getLastPortfolio():
				a.setChecked(True)
		if addedPort and len(benchmarks) > 0:
			self.portfoliosMenu.addSeparator()
		for a in benchmarks:
			self.portfoliosMenu.addAction(a)

	def getUniqueId(self):
		'''Get a unique identifier for each application instance'''
		# Create uniqueId
		id = self.prefs.getUniqueId()
		if id == "":
			id = str(uuid.uuid4())
			self.prefs.setUniqueId(id)
		return id

	def checkVersion(self):
		'''Check for new Icarra versions.  The latest version is retrieved when downloading stock data.'''
		(newMajor, newMinor, newRelease) = self.prefs.getLatestVersion()
		if newMajor > appGlobal.gMajorVersion or (newMajor == appGlobal.gMajorVersion and newMinor > appGlobal.gMinorVersion) or (newMajor == appGlobal.gMajorVersion and newMinor == appGlobal.gMinorVersion and newRelease > appGlobal.gRelease):
			# Remind once per week
			if datetime.datetime.now() < appGlobal.getApp().prefs.getLastVersionReminder() + datetime.timedelta(days = 7):
				return
	
			# Check if skipped
			(skipMajor, skipMinor, skipRelease) = self.prefs.getIgnoreVersion()
			if newMajor != skipMajor or newMinor != skipMinor or newRelease != skipRelease:
				d = newVersionFrame.NewVersion(newMajor, newMinor, newRelease)

	def startOfxDebug(self):
		'''Open the OFX debugging window and allow OFX data to be logged.'''
		if self.ofxDebugFrame:
			return

		self.ofxDebugFrame = OfxDebugFrame()
	
	def stopOfxDebug(self):
		'''Close the OFX debugging window and stop allowing OFX data to be logged.'''
		if not self.ofxDebugFrame:
			return

		self.ofxDebugFrame.close()
		self.ofxDebugFrame = False

	def addThreadSafeError(self, area, error):
		'''Display an error.  May be called from a separate thread.'''
		self.errorMutex.acquire()
		print "THREAD ERRROR:", area, error
		self.errorList.append((area, error))
		self.errorMutex.release()
	
	def checkThreadSafeError(self):
		'''Check for thread safe errors.  Called when a new tool is loaded.'''
		self.errorMutex.acquire()
		for (area, error) in self.errorList:
			message = QMessageBox(QMessageBox.Critical, area, error).exec_()
		self.errorList = []
		self.errorMutex.release()

if __name__ == '__main__':
	if "--broker-info" in sys.argv:
		app = Icarra2(sys.argv)
	
		print "<h2>Notes</h2>"
		for b in app.plugins.getBrokerages():
			if b.getNotes():
				print b.getName()
				print "<ul>"
				for n in b.getNotes():
					print "<li>", n, "</li>"
				print "</ul>"
			else:
				print "<p>", b.getName(), "</p>"
		print "<p>Is your brokerage not supported?  Contact us in the forum &mdash; we would love to help!</p>"
		app.exit()
		sys.exit()
	
	if "--regression" in sys.argv:
		import traceback
		app = Icarra2(sys.argv)
		
		try:
			import regression
			regression.run(sys.argv)
		except Exception, e:
			print "Error running regression:"
			print traceback.format_exc()
		
		app.exit()
		sys.exit()
	
	if "--rebuild" in sys.argv:
		import traceback
		app = Icarra2(sys.argv)
		
		try:
			p = Portfolio(sys.argv[2])
			app.portfolio = p
			p.rebuildPositionHistory(app.stockData)
		except Exception, e:
			print "Error running regression:"
			print traceback.format_exc()
		
		app.exit()
		sys.exit()
	
	if "--import" in sys.argv:
		f = open(sys.argv[2], "r")
		if not f:
			print "Could not open", sys.argv[2]
			sys.exit()
		data = f.read()
		
		for format in getFileFormats():
			if format.Guess(data):
				print "Is", format
				(numNew, numOld, newTickers) = format.StartParse(data, False, False)
				print "New: %d, Old: %d, Tickers: %s" % (numNew, numOld, newTickers)
				sys.exit(0)
		print "Did not guess", sys.argv[2]
	
	# Launch and run app
	# If exception, stop autoUpdater thread and re-raise exception
	try:
		app = Icarra2(sys.argv)
		if app.started:
			app.exec_()
		else:
			app.quit()
	except:
		autoUpdater.stop()
		raise
