# Copyright (c) 2006-2010, Jesse Liesch
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the author nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE IMPLIED
# DISCLAIMED. IN NO EVENT SHALL JESSE LIESCH BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from transaction import *

class BrokerageBase:
	'''Implements the base class for all brokerages.  The BrokerageBase
	class defines how a brokerage can download transactions, special
	cases for dealing with brokerage transaction bugs and contains other
	important information.'''

	def getName(self):
		'''Return the display name of this brokerage'''
		return ""
	
	def getUrl(self):
		'''Return the URL of this brokerage's OFX server or empty string if it does not support OFX'''
		return ""
	
	def getOrg(self):
		'''Return this brokerage's OFX ORG value or empty string if not applicable'''
		return ""
	
	def getFid(self):
		'''Return this brokerage's OFX FID value or empty string if not applicable'''
		return ""
	
	def getBrokerId(self):
		'''Return this brokerage's OFX BROKERID value or empty string if not applicable'''
		return ""
	
	def getNotes(self):
		'''Return a list of notes about this brokerage'''
		return []
	
	def massageStockInfo(self, stockInfo):
		'''Called when saving stockinfo, optinfo, etc.'''
		pass
	
	def preParseTransaction(self, trans):
		'''Called when converting raw OFX or file data into Transactions.  The trans parameter is a ParsedTransaction dictionary.  If not over-ridden then default parsing will be used.  Return False for default parsing.  Return True to skip the transaction.  The trans parameter may also be modified to make it better suited for regular parsing.'''
		return False
	
	def postProcessTransactions(self, transactions):
		'''Called after all transactions have been parsed.  The transactions parameter contains a list of all Icarra Transaction classes found in the file.'''
		pass

	def massageTransaction(self, trans):
		'''Called when a transaction is about to be saved.  The input to this function is an Icarra Transaction class.'''
		pass

