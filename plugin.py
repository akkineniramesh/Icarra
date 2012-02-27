class PluginBase:
	'''PluginBase defines the base class of all Icarra plugins.  Every
	Icarra tool is a plugin including the standard Chart, Settings and
	Transaction tools.

	The Summary plugin (builtinPlugins/plugin_summary.py) is a good
	example of a simple plugin.'''

	def __init__(self):
		'''Plugins should not override this function'''
		pass
	
	def name(self):
		'''Return the display name of this plugin'''
		return '???'

	def icarraVersion(self):
		'''Return the required version of Icarra software for using this plugin'''
		return (0, 2, 0)

	def version(self):
		'''Return a 3-tuple of the plugin version.  This is only used for informational purposes.'''
		return (0, 0, 0)

	def forInvestment(self):
		'''Return True if this plugin is applicable to investment accounts.'''
		return True

	def forBank(self):
		'''Return True if this plugin is applicable to bank accounts.'''
		return True

	def initialize(self):
		'''Called on startup.  Called sequentially for each plugin.  Plugins should use this function instead of __init__ for initializing the plugin.'''
		pass

	def createWidget(self, parent):
		'''Called when the plugin should display its GUI controls.  Should return a QWidget or None.'''
		return None

	def finalize(self):
		'''Called when Icarra exits.  Called sequentially for each plugin.'''
		pass
