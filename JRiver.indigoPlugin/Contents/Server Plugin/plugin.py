#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Vaillant
# For Media Center from JRiver
#-------------------------------------------------------------------------------
import urllib2
from xml.dom import minidom
from xml.dom.minidom import parse
import shutil
import os
#-------------------------------------------------------------------------------
commands = {
'PlayPause':'10000',
'Play':'10001',
'Stop':'10002',
'Next':'10003',
'Previous':'10004',
'KeyUp':'Up',
'KeyDown':'Down',
'KeyLeft':'Left',
'KeyRight':'Right',
'KeyEnter':'Enter',
'ShuffleToggle':'10005&Parameter=0',
'ShuffleOff':'10005&Parameter=3',
'ShuffleOn':'10005&Parameter=4',
'FastForward':'10008&Parameter=5', # 5%
'Rewind':'10009&Parameter=5', # 5%
'SetZone':'10011&Parameter=', # nZoneIndex
'ToggleZoneForward':'10011&Parameter=-1',
'ToggleZoneBackwards':'10011&Parameter=-2',
'PlayCPLDBIndex':'10015&Parameter=',
'VolumeMuteToggle':'10017&Parameter=0',
'ClearPlaylist':'10049&Parameter=0', # 0 All Files
'VolumeMuteOn':'10017&Parameter=1', 
'VolumeMuteOff':'10017&Parameter=2',
'VolumeUp':'10018&Parameter=1',
'VolumeDown':'10019&Parameter=1',
'VolumeSet':'10020&Parameter=',
'PauseToggle':'10022&Parameter=-1',
'PauseOn':'10022&Parameter=1',
'PauseOff':'10022&Parameter=0',
'StandardView':'22000&Parameter=0',
'MiniView':'22000&Parameter=1',
'TheaterView':'22000&Parameter=2',
'CoverView':'22000&Parameter=4'}
################################################################################
class Plugin(indigo.PluginBase):
	############################################################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = pluginPrefs.get("showDebugInfo", False)
		self.debugLog(u'Initialization called.')
		self.address = ''
		self.polling = False
		self.seconds = 5
		self.token = ''
		self.data = ''
		self.connected = True
		self.serverList = []
		self.zoneList = []
		self.zoneIdList = []
		self.zoneIdListStatic = []
	############################################################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
		self.debugLog("Stopping plugin.")
	############################################################################
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		self.debugLog(u'Plugin configuration dialog window closed.')
		if userCancelled:
			self.debugLog(u'User preferences dialog cancelled.')
		if not userCancelled:
			self.debugLog(u'User preferences saved.')
			self.debug = valuesDict.get("showDebugInfo", False)
			if self.debug:
				indigo.server.log("Debug logging enabled.")
			else:
				indigo.server.log("Debug logging disabled.")
	############################################################################
	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u'Validating preferences config.')
		return True
	############################################################################
	def validateActionConfigUi(self, valuesDict, typeId, actionId):
		self.debugLog(u"Validating action config.")
		return True
	########################################
	# Used to control input from Devices.xml
	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		self.debugLog(u"Validating deviceConfigUi: typeId: %s  devId: %s" % (typeId, str(devId)))
		errorsDict = indigo.Dict()
		anError = False
		#-----------------------------------------------------------------------
		if typeId == u"server":
			if valuesDict['ip'] != "":
				pass
			else:
				errorsDict['ip'] = "Ip is missing"
				valuesDict['state'] = "no ip"
				self.errorLog(errorsDict['ip'])
				anError = True
			if valuesDict['port'] != "":
				pass
			else:
				errorsDict['port'] = "Port is missing"
				valuesDict['state'] = "no port"
				self.errorLog(errorsDict['port'])
				anError = True
			if valuesDict['token'] != "":
				pass
			else:
				errorsDict['token'] = "Token is missing"
				valuesDict['state'] = "no token"
				self.errorLog(errorsDict['token'])
				anError = True
			if valuesDict['seconds'] >= 0:
				pass
			else:
				errorsDict['token'] = "Seconds must be greater then 0"
				valuesDict['state'] = "change seconds"
				self.errorLog(errorsDict['change seconds'])
				anError = True
			if anError == True:
				return (False, valuesDict, errorsDict)
			else:
				return (True, valuesDict)
		#-----------------------------------------------------------------------
		if typeId == u"zone":
			return (True, valuesDict)
	############################################################################
	def deviceStartComm(self, dev):
		self.debugLog(u"DeviceStartComm called.")
		dev.stateListOrDisplayStateIdChanged()
		if dev.deviceTypeId == "server":
			if dev.id not in self.serverList:
				self.serverList.append(dev.id)
			self.polling = dev.pluginProps["polling"]
			self.address = str(dev.pluginProps["ip"]) + ":" + str(dev.pluginProps["port"])
			self.seconds = dev.pluginProps["seconds"]
			self.token = dev.pluginProps["token"]
			newProps = dev.pluginProps
			newProps['address'] = self.address
			dev.replacePluginPropsOnServer(newProps)
			dev.updateStateOnServer("state", value = "connecting", uiValue = "connecting")
			self.updateStateIcon(dev)
			self.alive(dev)
		if dev.deviceTypeId == "zone":
			if dev.id not in self.zoneList:
				self.zoneList.append(dev.id)
				self.zoneIdList.append(dev.states['zoneID'])
			dev.updateStateOnServer("state", value = "connecting", uiValue = "connecting")
			self.updateStateIcon(dev)
	############################################################################
	def deviceStopComm(self, dev):
		self.debugLog(u"DeviceStopComm called.")
		dev.updateStateOnServer("state", value = "unavailable", uiValue = "unavailable")
		self.updateStateIcon(dev)
		self.debugLog(u"Connection disabled.")
		if dev.id in self.serverList:
			self.serverList.remove(dev.id)
		if dev.id in self.zoneList:
			self.zoneList.remove(dev.id)
			self.zoneIdList.remove(dev.states['zoneID'])
	############################################################################
	def startup(self):
		self.debugLog(u"Startup called.")
		for dev in indigo.devices.itervalues('self.zone'):
			self.zoneIdListStatic.append(dev.states['zoneID'])
	############################################################################
	def shutdown(self):
		self.debugLog(u"Shutdown called.")
		for dev in indigo.devices.itervalues('self.zone'):
			self.zoneIdListStatic.remove(dev.states['zoneID'])
	########################################
	# Actions defined in Actions.xml:
	########################################
	def sendCommand(self, action):
		self.debugLog(u"Action sendCommand called...")
		zoneId = int(action.props["zoneSelect"])
		command = action.props.get('command', '')
		if (zoneId == '') or (command == ''):
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			command = commands.get(command)
			devzone = indigo.devices[zoneId]
			zoneID = str(devzone.states["zoneID"])
			self.debugLog(u"SendCommand called: send %s to zone %s (%s)." % (command, zoneID, self.address))
			try:
				url = 'http://%s/MCWS/v1/Control/MCC?Command=%s&Zone=%s&ZoneType=ID&Token=%s' % (self.address, command, zoneID, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def sendCommandCurrentZone(self, action):
		self.debugLog(u"Action sendCommandCurrentZone called...")
		command = action.props.get('command', '')
		if command == '':
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			command = commands.get(command)
			self.debugLog(u"SendCommandCurrentZone called: send %s to current zone (%s)." % (command, self.address))
			try:
				url = 'http://%s/MCWS/v1/Control/MCC?Command=%s&Zone=-1&ZoneType=ID&Token=%s' % (self.address, command, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def playFile(self, action):
		self.debugLog(u"Action playFile called...")
		zoneId = int(action.props["zoneSelect"])
		databaseKey = action.props.get('databaseKey', '')
		if (zoneId == '') or (databaseKey == ''):
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			#command = commands.get('PlayCPLDBIndex')
			devzone = indigo.devices[zoneId]
			zoneID = str(devzone.states["zoneID"])
			self.debugLog(u"SendCommand called: send %s to zone %s (%s)." % (databaseKey, zoneID, self.address))
			try:
				#url = 'http://%s/MCWS/v1/Control/MCC?Command=%s%s&Zone=%s&ZoneType=ID&Token=%s' % (self.address, command, databaseKey, zoneID, self.token)
 				url = 'http://%s/MCWS/v1/Playback/PlayByKey?Key=%s&Zone=%s&ZoneType=ID&Token=%s' % (self.address, databaseKey, zoneID, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def playPlaylist(self, action):
		self.debugLog(u"Action playPlaylist called...")
		zoneId = int(action.props["zoneSelect"])
		databaseID = action.props.get('databaseID', '')
		if (zoneId == '') or (databaseID == ''):
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			devzone = indigo.devices[zoneId]
			zoneID = str(devzone.states["zoneID"])
			self.debugLog(u"SendCommand called: send %s to zone %s (%s)." % (databaseID, zoneID, self.address))
			try:
 				url = 'http://%s/MCWS/v1/Playback/PlayPlaylist?ID=%s&Zone=%s&ZoneType=ID&Token=%s' % (self.address, databaseID, zoneID, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))	
	############################################################################
	def setCommandView(self, action):
		self.debugLog(u"Action setCommandView called...")
		command = action.props.get('command', '')
		if command == '':
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			command = commands.get(command)
			self.debugLog(u"setCommandView called: send %s to current zone (%s)." % (command, self.address))
			try:
				url = 'http://%s/MCWS/v1/Control/MCC?Command=%s&Zone=-1&ZoneType=ID&Token=%s' % (self.address, command, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def setZone(self, action):
		self.debugLog(u"Action setZone called...")
		zoneId = int(action.props["zoneSelect"])
		if (zoneId == ''):
			self.errorLog(u"SetZone action misconfigured, no key sent.")
		elif self.connected == True:
			devzone = indigo.devices[zoneId]
			zoneID = str(devzone.states["zoneID"])
			self.debugLog(u"SetZone called: zone is set to %s (%s)." % (zoneID, self.address))
			try:
				url = 'http://%s/MCWS/v1/Playback/SetZone?Zone=%s&ZoneType=ID?Token=%s' % (self.address, zoneID, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def sendKey(self, action):
		self.debugLog(u"Action sendKey called...")
		command = action.props.get('command', '')
		if command == '':
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			command = commands.get(command)
			self.debugLog(u"sendKey called: send %s to current zone (%s)." % (command, self.address))
			try:
				#url = 'http://%s/MCWS/v1/Control/MCC?Command=%s&Zone=-1&ZoneType=ID&Token=%s' % (self.address, command, self.token)
				url = 'http://%s/MCWS/v1/Control/Key?Key=%s&?Token=%s' % (self.address, command, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def toggleZone(self, action):
		self.debugLog(u"Action toggleZone called...")
		command = action.props.get('command', '')
		if command == '':
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			command = commands.get(command)
			self.debugLog(u"toggleZone called: send %s to current zone (%s)." % (command, self.address))
			try:
				url = 'http://%s/MCWS/v1/Control/MCC?Command=%s&Zone=-1&ZoneType=ID&Token=%s' % (self.address, command, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def setVolume(self, action):
		self.debugLog(u"Action setVolume called...")
		zoneId = int(action.props["zoneSelect"])
		volumePercentage = action.props.get('volumePercentage', '')
		if (zoneId == '') or (volumePercentage == ''):
			self.errorLog(u"Command action misconfigured, no key sent.")
		elif self.connected == True:
			devzone = indigo.devices[zoneId]
			zoneID = str(devzone.states["zoneID"])
			self.debugLog(u"SendCommand called: send %s to zone %s (%s)." % (volumePercentage, zoneID, self.address))
			try:
				url = 'http://%s/MCWS/v1/Control/MCC?Command=10020&Parameter=%s&Zone=%s&ZoneType=ID&Token=%s' % (self.address, volumePercentage, zoneID, self.token)
				urllib2.urlopen(url)
			except urllib2.HTTPError, e:
				self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
			except urllib2.URLError, e:
				self.errorLog(u'JRiver URLError - %s.' % unicode(e))
			except Exception, e:
				self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	############################################################################
	def copyArt(self, action):
		self.debugLog(u"Action copyArt called...")
		serverId = int(action.props["server"])
		size = str(action.props["size"])
		destinationMusic = str(action.props["destinationMusic"])
		destinationMovies = str(action.props["destinationMovies"])
		noArtworkFilename = str(action.props["noArtworkFilename"])
		if (serverId == '') or (destinationMusic == '') or (destinationMovies == '') or (size == ''):
			self.errorLog(u"copyArt action misconfigured, no key sent.")
		elif self.connected == True:
			devServer = indigo.devices[serverId]
			zoneID = str(devServer.states["currentZoneID"])
			fileKey = str(devServer.states["fileKey"])
			imageURL = str(devServer.states["imageURL"])
			self.debugLog(u"CopyArt called: zone %s (%s)." % (zoneID, self.address))
			if fileKey == '-1':
				if noArtworkFilename != '':
					try:
						shutil.copy(noArtworkFilename, destinationMusic)
						shutil.copy(noArtworkFilename, destinationMovies)
					except Exception, e:
						self.errorLog(u'JRiver Exception - %s.' % unicode(e))
			else:
				try:
					url = 'http://%s/%s&FileType=Key&Type=Thumbnail&ThumbnailSize=%s&Format=png' % (self.address, imageURL, size)
					f = open('image.png','wb')
					f.write(urllib2.urlopen(url).read())
					f.close()
					if devServer.states['album'] != '':
						shutil.copy(noArtworkFilename, destinationMovies)
						shutil.copy('image.png', destinationMusic)
					else:
						shutil.copy(noArtworkFilename, destinationMusic)
						shutil.copy('image.png', destinationMovies)
				except urllib2.HTTPError, e:
					self.errorLog(u'JRiver HTTPError - %s.' % unicode(e))
				except urllib2.URLError, e:
					self.errorLog(u'JRiver URLError - %s.' % unicode(e))
				except Exception, e:
					self.errorLog(u'JRiver Exception - %s.' % unicode(e))
	########################################
	# Modules:
	########################################
	def getXML(self, command):
		self.debugLog(u"Executing getXML...")
		self.connected = True
		try:
			url = 'http://%s/MCWS/v1/%s?Token=%s' % (self.address, command, self.token)
			f = urllib2.urlopen(url)
			self.data = minidom.parse(f)
		except urllib2.HTTPError, e:
			self.data = ''
			self.connected = False
			self.errorLog(u'JRiver HTTPError - %s' % unicode(e))
		except urllib2.URLError, e:
			self.data = ''
			self.connected = False
			self.errorLog(u'JRiver URLError - %s' % unicode(e))
		except Exception, e:
			self.data = ''
			self.connected = False
			self.errorLog(u'JRiver Exception - %s' % unicode(e))					
		return self.data
	############################################################################
	def zones(self, device):
		self.debugLog(u"Executing zones...")
		self.itemList = []
		self.itemDict = {}
		self.responseList = []
		self.responseDict = {}
		command = 'Playback/Zones'
		self.getXML(command)
		if self.connected == True:
			assert self.data.documentElement.tagName == "Response"
			self.responseList = self.data.getElementsByTagName('Response')
			self.itemList = self.data.getElementsByTagName('Item')
			for s in self.responseList:
				self.responseDict['Status'] = s.attributes['Status'].value
			if str(self.itemDict.get('Status', None)) != device.states['status']:
				device.updateStateOnServer('status', value = str(self.responseDict.get('Status', None)), uiValue = str(self.responseDict.get('Status', None)))					
			if str(self.responseDict.get('Status')) == 'OK':
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "ready", uiValue = "ready")
			else:
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
					self.errorLog(u"JRiver is not responding. Please check.")
			for s in self.itemList:
				self.itemDict[s.attributes['Name'].value] = s.childNodes[0].nodeValue
			if int(self.itemDict.get('NumberZones', None)) != device.states['numberZones']:
				device.updateStateOnServer("numberZones", value = int(self.itemDict.get('NumberZones', None)), uiValue = str(self.itemDict.get('NumberZones', None)))
			if int(self.itemDict.get('CurrentZoneID', None)) != device.states['currentZoneID']:
				device.updateStateOnServer("currentZoneID", value = int(self.itemDict.get('CurrentZoneID', None)), uiValue = str(self.itemDict.get('CurrentZoneID', None)))
			if int(self.itemDict.get('CurrentZoneIndex', None)) != device.states['currentZoneIndex']:
				device.updateStateOnServer("currentZoneIndex", value = int(self.itemDict.get('CurrentZoneIndex', None)), uiValue = str(self.itemDict.get('CurrentZoneIndex', None)))
			self.updateStateIcon(device)
			self.debugLog(u"Updated zones from JRiver.")
			self.checkNewzone(self.itemDict)
			for dev in indigo.devices.itervalues('self.zone'):
				if dev.id not in self.zoneList:
					if dev.configured and dev.enabled:
						self.deviceStartComm(indigo.devices[dev.id])
		else:
			pass
	############################################################################
	def currentZone(self, device):
		self.debugLog(u"Executing currentZone...")
		self.itemList = []
		self.itemDict = {}
		self.responseDict = {}
		command = 'Playback/Zones'
		self.getXML(command)
		if self.connected == True:
			assert self.data.documentElement.tagName == "Response"
			self.itemList = self.data.getElementsByTagName('Item')
			for s in self.itemList:
				self.itemDict[s.attributes['Name'].value] = s.childNodes[0].nodeValue
			if int(self.itemDict.get('CurrentZoneID', None)) != device.states['currentZoneID']:
				device.updateStateOnServer("currentZoneID", value = int(self.itemDict.get('CurrentZoneID', None)), uiValue = str(self.itemDict.get('CurrentZoneID', None)))
			self.debugLog(u"Updated currentZone from JRiver.")
		else:
			pass
	############################################################################
	def view(self, device):
		self.debugLog(u"Executing view...")
		self.itemList = []
		self.itemDict = {}
		self.responseList = []
		self.responseDict = {}
		command = 'UserInterface/Info'
		self.getXML(command)
		if self.connected == True:
			assert self.data.documentElement.tagName == "Response"
			self.responseList = self.data.getElementsByTagName('Response')
			self.itemList = self.data.getElementsByTagName('Item')
			for s in self.responseList:
				self.responseDict['Status'] = s.attributes['Status'].value
			if str(self.itemDict.get('Status', None)) != device.states['status']:
				device.updateStateOnServer('status', value = str(self.responseDict.get('Status', None)), uiValue = str(self.responseDict.get('Status', None)))					
			if str(self.responseDict.get('Status')) == 'OK':
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "ready", uiValue = "ready")
			else:
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
					self.errorLog(u"JRiver is not responding. Please check.")
			for s in self.itemList:
				self.itemDict[s.attributes['Name'].value] = s.childNodes[0].nodeValue
			if int(self.itemDict.get('Mode', None)) != device.states['viewMode']:
				device.updateStateOnServer("viewMode", value = int(self.itemDict.get('Mode', None)), uiValue = str(self.itemDict.get('Mode', None)))
			if int(self.itemDict.get('InternalMode', None)) != device.states['viewModeInternal']:
				device.updateStateOnServer("viewModeInternal", value = str(self.itemDict.get('InternalMode', None)), uiValue = str(self.itemDict.get('InternalMode', None)))
			self.updateStateIcon(device)
			self.debugLog(u"Updated view from JRiver.")
		else:
			pass
	############################################################################
	def checkNewzone(self, itemDict):
		for dev in indigo.devices.itervalues('self.zone'):
			if dev.states['zoneID'] not in self.zoneIdListStatic:
				self.zoneIdListStatic.append(dev.states['zoneID'])
		counter = int(itemDict.get('NumberZones')) - 1
		while counter > -1:
			_zoneID = int(itemDict.get(str('ZoneID' + str(counter))))
			_zoneName = str(itemDict.get(str('ZoneName' + str(counter))))
			if _zoneID not in self.zoneIdListStatic:
				devzone = indigo.device.create(protocol=indigo.kProtocol.Plugin, address = str(_zoneID), name = str('JRiver (' + str(_zoneID) + ') ' + _zoneName), pluginId = "com.vaillant.indigoplugin.JRiver", deviceTypeId = "zone")
				devzone.updateStateOnServer("zoneName", value = _zoneName, uiValue = _zoneName)
				devzone.updateStateOnServer("zoneID", value = _zoneID, uiValue = str(_zoneID))
				self.zoneIdListStatic.append(devzone.states['zoneID'])
			else:
				pass
			counter = counter - 1
	############################################################################
	def info(self, device):
		self.debugLog(u"Executing info for zone %s." % device.states['zoneName'])
		self.itemList = []
		self.itemDict = {}
		self.responseList = []
		self.responseDict = {}
		command = 'Playback/Info?Zone=%s&ZoneType=ID' % (device.states["zoneID"])
		self.getXML(command)
		if self.connected == True:
			for deviceId in self.serverList:
				devServer = indigo.devices[deviceId]
				if device.states['zoneID'] == devServer.states['currentZoneID']:
					updateServerInfo = True
				else:
					updateServerInfo = False
			assert self.data.documentElement.tagName == "Response"
			self.responseList = self.data.getElementsByTagName('Response')
			self.itemList = self.data.getElementsByTagName('Item')
			
			for s in self.responseList:
				self.responseDict['Status'] = s.attributes['Status'].value
			if str(self.itemDict.get('Status', None)) != device.states['status']:
				device.updateStateOnServer('status', value = str(self.responseDict.get('Status', None)), uiValue = str(self.responseDict.get('Status', None)))					
			if str(self.responseDict.get('Status')) == 'OK':
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "ready", uiValue = "ready")
			else:
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					dev.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
					self.errorLog(u"JRiver is not responding. Please check.")

			for s in self.itemList:
				self.itemDict[s.attributes['Name'].value] = s.childNodes[0].nodeValue

			if int(self.itemDict.get('FileKey', None)) != device.states['fileKey']:
				device.updateStateOnServer("fileKey", value = int(self.itemDict.get('FileKey', None)), uiValue = str(self.itemDict.get('FileKey', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('FileKey', None)) != devServer.states['fileKey']:
					devServer.updateStateOnServer("fileKey", value = int(self.itemDict.get('FileKey', None)), uiValue = str(self.itemDict.get('FileKey', None)))
			if int(self.itemDict.get('NextFileKey', None)) != device.states['nextFileKey']:
				device.updateStateOnServer("nextFileKey", value = int(self.itemDict.get('NextFileKey', None)), uiValue = str(self.itemDict.get('NextFileKey', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('NextFileKey', None)) != devServer.states['nextFileKey']:
					devServer.updateStateOnServer("nextFileKey", value = int(self.itemDict.get('NextFileKey', None)), uiValue = str(self.itemDict.get('NextFileKey', None)))
			if int(self.itemDict.get('PositionMS', None)) != device.states['positionMS']:
				device.updateStateOnServer("positionMS", value = int(self.itemDict.get('PositionMS', None)), uiValue = str(self.itemDict.get('PositionMS', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('PositionMS', None)) != devServer.states['positionMS']:
					devServer.updateStateOnServer("positionMS", value = int(self.itemDict.get('PositionMS', None)), uiValue = str(self.itemDict.get('PositionMS', None)))
			if int(self.itemDict.get('DurationMS', None)) != device.states['durationMS']:
				device.updateStateOnServer("durationMS", value = int(self.itemDict.get('DurationMS', None)), uiValue = str(self.itemDict.get('DurationMS', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('DurationMS', None)) != devServer.states['durationMS']:
					devServer.updateStateOnServer("durationMS", value = int(self.itemDict.get('DurationMS', None)), uiValue = str(self.itemDict.get('DurationMS', None)))
			if str(self.itemDict.get('ElapsedTimeDisplay', None)) != device.states['elapsedTimeDisplay']:
				device.updateStateOnServer("elapsedTimeDisplay", value = str(self.itemDict.get('ElapsedTimeDisplay', None)), uiValue = str(self.itemDict.get('ElapsedTimeDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('ElapsedTimeDisplay', None)) != devServer.states['elapsedTimeDisplay']:
					devServer.updateStateOnServer("elapsedTimeDisplay", value = str(self.itemDict.get('ElapsedTimeDisplay', None)), uiValue = str(self.itemDict.get('ElapsedTimeDisplay', None)))
			if str(self.itemDict.get('RemainingTimeDisplay', None)) != device.states['remainingTimeDisplay']:
				device.updateStateOnServer("remainingTimeDisplay", value = str(self.itemDict.get('RemainingTimeDisplay', None)), uiValue = str(self.itemDict.get('RemainingTimeDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('RemainingTimeDisplay', None)) != devServer.states['remainingTimeDisplay']:
					devServer.updateStateOnServer("remainingTimeDisplay", value = str(self.itemDict.get('RemainingTimeDisplay', None)), uiValue = str(self.itemDict.get('RemainingTimeDisplay', None)))
			if str(self.itemDict.get('TotalTimeDisplay', None)) != device.states['totalTimeDisplay']:
				device.updateStateOnServer("totalTimeDisplay", value = str(self.itemDict.get('TotalTimeDisplay', None)), uiValue = str(self.itemDict.get('TotalTimeDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('TotalTimeDisplay', None)) != devServer.states['totalTimeDisplay']:
					devServer.updateStateOnServer("totalTimeDisplay", value = str(self.itemDict.get('TotalTimeDisplay', None)), uiValue = str(self.itemDict.get('TotalTimeDisplay', None)))
			if str(self.itemDict.get('PositionDisplay', None)) != device.states['positionDisplay']:
				device.updateStateOnServer("positionDisplay", value = str(self.itemDict.get('PositionDisplay', None)), uiValue = str(self.itemDict.get('PositionDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('PositionDisplay', None)) != devServer.states['positionDisplay']:
					devServer.updateStateOnServer("positionDisplay", value = str(self.itemDict.get('PositionDisplay', None)), uiValue = str(self.itemDict.get('PositionDisplay', None)))
			if int(self.itemDict.get('PlayingNowPosition', None)) != device.states['playingNowPosition']:
				device.updateStateOnServer("playingNowPosition", value = int(self.itemDict.get('PlayingNowPosition', None)), uiValue = str(self.itemDict.get('PlayingNowPosition', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('PlayingNowPosition', None)) != devServer.states['playingNowPosition']:
					devServer.updateStateOnServer("playingNowPosition", value = int(self.itemDict.get('PlayingNowPosition', None)), uiValue = str(self.itemDict.get('PlayingNowPosition', None)))
			if int(self.itemDict.get('PlayingNowTracks', None)) != device.states['playingNowTracks']:
				device.updateStateOnServer("playingNowTracks", value = int(self.itemDict.get('PlayingNowTracks', None)), uiValue = str(self.itemDict.get('PlayingNowTracks', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('PlayingNowTracks', None)) != devServer.states['playingNowTracks']:
					devServer.updateStateOnServer("playingNowTracks", value = int(self.itemDict.get('PlayingNowTracks', None)), uiValue = str(self.itemDict.get('PlayingNowTracks', None)))
			if str(self.itemDict.get('PlayingNowPositionDisplay', None)) != device.states['playingNowPositionDisplay']:
				device.updateStateOnServer("playingNowPositionDisplay", value = str(self.itemDict.get('PlayingNowPositionDisplay', None)), uiValue = str(self.itemDict.get('PlayingNowPositionDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('PlayingNowPositionDisplay', None)) != devServer.states['playingNowPositionDisplay']:
					devServer.updateStateOnServer("playingNowPositionDisplay", value = str(self.itemDict.get('PlayingNowPositionDisplay', None)), uiValue = str(self.itemDict.get('PlayingNowPositionDisplay', None)))
			if int(self.itemDict.get('PlayingNowChangeCounter', None)) != device.states['playingNowChangeCounter']:
				device.updateStateOnServer("playingNowChangeCounter", value = int(self.itemDict.get('PlayingNowChangeCounter', None)), uiValue = str(self.itemDict.get('PlayingNowChangeCounter', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('PlayingNowChangeCounter', None)) != devServer.states['playingNowChangeCounter']:
					devServer.updateStateOnServer("playingNowChangeCounter", value = int(self.itemDict.get('PlayingNowChangeCounter', None)), uiValue = str(self.itemDict.get('PlayingNowChangeCounter', None)))
			if int(self.itemDict.get('Bitrate', None)) != device.states['bitrate']:
				device.updateStateOnServer("bitrate", value = int(self.itemDict.get('Bitrate', None)), uiValue = str(self.itemDict.get('Bitrate', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('Bitrate', None)) != devServer.states['bitrate']:
					devServer.updateStateOnServer("bitrate", value = int(self.itemDict.get('Bitrate', None)), uiValue = str(self.itemDict.get('Bitrate', None)))
			if int(self.itemDict.get('Bitdepth', None)) != device.states['bitdepth']:	
				device.updateStateOnServer("bitdepth", value = int(self.itemDict.get('Bitdepth', None)), uiValue = str(self.itemDict.get('Bitdepth', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('Bitdepth', None)) != devServer.states['bitdepth']:
					devServer.updateStateOnServer("bitdepth", value = int(self.itemDict.get('Bitdepth', None)), uiValue = str(self.itemDict.get('Bitdepth', None)))
			if int(self.itemDict.get('SampleRate', None)) != device.states['sampleRate']:
				device.updateStateOnServer("sampleRate", value = int(self.itemDict.get('SampleRate', None)), uiValue = str(self.itemDict.get('SampleRate', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('SampleRate', None)) != devServer.states['sampleRate']:
					devServer.updateStateOnServer("sampleRate", value = int(self.itemDict.get('SampleRate', None)), uiValue = str(self.itemDict.get('SampleRate', None)))
			if int(self.itemDict.get('Channels', None)) != device.states['channels']:	
				device.updateStateOnServer("channels", value = int(self.itemDict.get('Channels', None)), uiValue = str(self.itemDict.get('Channels', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('Channels', None)) != devServer.states['channels']:
					devServer.updateStateOnServer("channels", value = int(self.itemDict.get('Channels', None)), uiValue = str(self.itemDict.get('Channels', None)))
			if int(self.itemDict.get('Chapter', None)) != device.states['chapter']:	
				device.updateStateOnServer("chapter", value = int(self.itemDict.get('Chapter', None)), uiValue = str(self.itemDict.get('Chapter', None)))
			if updateServerInfo == True:
				if int(self.itemDict.get('Chapter', None)) != devServer.states['chapter']:
					devServer.updateStateOnServer("chapter", value = int(self.itemDict.get('Chapter', None)), uiValue = str(self.itemDict.get('Chapter', None)))
			if float(self.itemDict.get('Volume', None)) != device.states['volume']:
				device.updateStateOnServer("volume", value = float(self.itemDict.get('Volume', None)), uiValue = str(self.itemDict.get('Volume', None)))
			if updateServerInfo == True:
				if float(self.itemDict.get('Volume', None)) != devServer.states['volume']:
					devServer.updateStateOnServer("volume", value = float(self.itemDict.get('Volume', None)), uiValue = str(self.itemDict.get('Volume', None)))
			if str(self.itemDict.get('VolumeDisplay', None)) != device.states['volumeDisplay']:
				device.updateStateOnServer("volumeDisplay", value = str(self.itemDict.get('VolumeDisplay', None)), uiValue = str(self.itemDict.get('VolumeDisplay', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('VolumeDisplay', None)) != devServer.states['volumeDisplay']:
					devServer.updateStateOnServer("volumeDisplay", value = str(self.itemDict.get('VolumeDisplay', None)), uiValue = str(self.itemDict.get('VolumeDisplay', None)))
			if str(self.itemDict.get('ImageURL', None)) != device.states['imageURL']:
				device.updateStateOnServer("imageURL", value = str(self.itemDict.get('ImageURL', None)), uiValue = str(self.itemDict.get('ImageURL', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('ImageURL', None)) != devServer.states['imageURL']:
					devServer.updateStateOnServer("imageURL", value = str(self.itemDict.get('ImageURL', None)), uiValue = str(self.itemDict.get('ImageURL', None)))
			if str(self.itemDict.get('Artist', None)) != device.states['artist']:	
				if str(self.itemDict.get('Artist', None)) == 'None':
					device.updateStateOnServer("artist", value = '', uiValue = '')
				else:
					device.updateStateOnServer("artist", value = str(self.itemDict.get('Artist')), uiValue = str(self.itemDict.get('Artist', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('Artist', None)) != devServer.states['artist']:
					if str(self.itemDict.get('Artist', None)) == 'None':
						devServer.updateStateOnServer("artist", value = '', uiValue = '')
					else:
						devServer.updateStateOnServer("artist", value = str(self.itemDict.get('Artist')), uiValue = str(self.itemDict.get('Artist', None)))
			if str(self.itemDict.get('Album', None)) != device.states['album']:
				if str(self.itemDict.get('Album', None)) == 'None':
					device.updateStateOnServer("album", value = '', uiValue = '')
				else:
					device.updateStateOnServer("album", value = str(self.itemDict.get('Album', None)), uiValue = str(self.itemDict.get('Album', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('Album', None)) != devServer.states['album']:
					if str(self.itemDict.get('Album', None)) == 'None':
						devServer.updateStateOnServer("album", value = '', uiValue = '')
					else:
						devServer.updateStateOnServer("album", value = str(self.itemDict.get('Album', None)), uiValue = str(self.itemDict.get('Album', None)))
			if str(self.itemDict.get('Name', None)) != device.states['name']:
				if str(self.itemDict.get('Name', None)) == 'None':
					device.updateStateOnServer("name", value = '', uiValue = '')
				else:
					device.updateStateOnServer("name", value = str(self.itemDict.get('Name', None)), uiValue = str(self.itemDict.get('Name', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('Name', None)) != devServer.states['name']:
					if str(self.itemDict.get('Name', None)) == 'None':
						devServer.updateStateOnServer("name", value = '', uiValue = '')
					else:
						devServer.updateStateOnServer("name", value = str(self.itemDict.get('Name', None)), uiValue = str(self.itemDict.get('Name', None)))
			if str(self.itemDict.get('Status', None)) != device.states['zoneStatus']:
				device.updateStateOnServer("zoneStatus", value = str(self.itemDict.get('Status', None)), uiValue = str(self.itemDict.get('Status', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('Status', None)) != devServer.states['zoneStatus']:
					devServer.updateStateOnServer("zoneStatus", value = str(self.itemDict.get('Status', None)), uiValue = str(self.itemDict.get('Status', None)))
			if str(self.itemDict.get('LinkedZones', None)) != device.states['linkedZones']:	
				device.updateStateOnServer("linkedZones", value = str(self.itemDict.get('LinkedZones', None)), uiValue = str(self.itemDict.get('LinkedZones', None)))
			if int(self.itemDict.get('State', None)) != device.states['zoneState']:	
				device.updateStateOnServer("zoneState", value = int(self.itemDict.get('State', None)), uiValue = str(self.itemDict.get('State', None)))
			if updateServerInfo == True:
				if str(self.itemDict.get('State', None)) != devServer.states['zoneState']:
					devServer.updateStateOnServer("zoneState", value = str(self.itemDict.get('State', None)), uiValue = str(self.itemDict.get('State', None)))
			if int(self.itemDict.get('ZoneID', None)) != device.states['zoneID']:	
				device.updateStateOnServer("zoneID", value = int(self.itemDict.get('ZoneID', None)), uiValue = str(self.itemDict.get('ZoneID', None)))
			self.updateStateIcon(device)
		else:
			pass
	############################################################################
	def alive(self, device):
		self.debugLog(u"Executing alive...")
		self.itemList = []
		self.itemDict = {}
		self.responseList = []
		self.responseDict = {}
		command = 'Alive'
		self.getXML(command)
		if self.connected == True:
			assert self.data.documentElement.tagName == "Response"
			self.responseList = self.data.getElementsByTagName('Response')
			for s in self.responseList:
				self.responseDict['Status'] = s.attributes['Status'].value
			if str(self.responseDict.get('Status')) == 'OK':
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "ready", uiValue = "ready")
					self.debugLog(u"Connected to JRiver.")
			else:
				if str(self.itemDict.get('Status', None)) != device.states['status']:
					device.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
					device.updateStateOnServer("status", value = "error", uiValue = "error")
					self.errorLog(u"JRiver is not responding. Please check.")
					self.debugLog(u"Connection failed.")
		else:
			if device.states['state'] != 'no comm.':
				device.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
				device.updateStateOnServer("status", value = "error", uiValue = "error")
			for dev in indigo.devices.itervalues('self.zone'):
				if dev.states['state'] != 'no comm.':
					dev.updateStateOnServer("state", value = "no comm.", uiValue = "no comm.")
					self.updateStateIcon(dev)
			self.errorLog(u"JRiver is not responding. Please check.")
			self.debugLog(u"Connection failed.")
		self.updateStateIcon(device)
	############################################################################
	def updateStateIcon(self, device):
		self.debugLog(u"Executing updateStateIcon.")
		if device.states['state'] == 'no polling':
			device.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
		if device.states['state'] == 'no comm.':
			device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
		if device.states['state'] == 'connecting':
			device.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
		if device.states['state'] == 'unavailable':
			device.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
		if device.states['state'] == 'ready' and device.deviceTypeId == "server":
			device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
		if device.states['state'] == 'ready' and device.deviceTypeId == "zone":
			if device.states['zoneState'] == 0:
				device.updateStateImageOnServer(indigo.kStateImageSel.AvStopped)
			elif device.states['zoneState'] == 1:
				device.updateStateImageOnServer(indigo.kStateImageSel.AvPaused)
			elif device.states['zoneState'] == 2:
				device.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)
	############################################################################
	def runConcurrentThread(self):
		self.debugLog(u'RunConcurrentThread initiated.')
		pollingCounter = 0
		noPollingCounter = 0
		aliveCounter = 0
		zoneCounter = 0
		currentZoneCounter = 0
		notConnectedCounter = 15
		try:
			while True:
				if self.connected == True:
					#-----------------------------------------------------------
					if aliveCounter == 0:
						aliveCounter = 60
						for deviceId in self.serverList:
							self.debugLog(u'Checking connection...')
							self.alive(indigo.devices[deviceId])
					else:
						aliveCounter = aliveCounter - 1
					#-----------------------------------------------------------
					if zoneCounter == 0:
						zoneCounter = 60
						for deviceId in self.serverList:
							self.debugLog(u'Updating zones...')
							self.zones(indigo.devices[deviceId])
							self.view(indigo.devices[deviceId])
					else:
						zoneCounter = zoneCounter - 1
					#-----------------------------------------------------------
					if self.polling == True:
						if currentZoneCounter == 0:
							currentZoneCounter = int(self.seconds)
							for deviceId in self.serverList:
								try:
									self.debugLog(u'Updating servers...')
									self.currentZone(indigo.devices[deviceId])
									self.view(indigo.devices[deviceId])
								except Exception, e:
									self.errorLog(u'JRiver Exception - %s.' % unicode(e))
						else:
							currentZoneCounter = currentZoneCounter - 1
						if pollingCounter == 0:
							pollingCounter = int(self.seconds)
							for deviceId in self.zoneList:
								try:
									self.debugLog(u'Updating zones...')
									self.info(indigo.devices[deviceId])
								except Exception, e:
									if indigo.devices[deviceId].states['status'] != 'error':
										indigo.devices[deviceId].updateStateOnServer("status", value = "error", uiValue = "error")
									self.deviceStopComm(indigo.devices[deviceId])
									self.debugLog(u'JRiver zone %s is missing. Automatic check enabled.' % str((indigo.devices[deviceId].states['zoneID'])))
						else:
							pollingCounter = pollingCounter - 1
					else:
						if noPollingCounter == 0:
							noPollingCounter = 60
							for dev in indigo.devices.itervalues('self.zone'):
								if dev.configured and dev.enabled:
									if dev.states['state'] != 'no polling':
										dev.updateStateOnServer("state", value = "no polling", uiValue = "no polling")
										self.updateStateIcon(dev)
						else:
							noPollingCounter = noPollingCounter - 1
					#-----------------------------------------------------------
				else:
					if notConnectedCounter == 0:
						notConnectedCounter = 60
						for deviceId in self.serverList:
							try:
								self.debugLog(u'Checking connection...')
								self.alive(indigo.devices[deviceId])
							except Exception, e:
								self.errorLog(u'JRiver server is missing. Please check.')
					else:
						notConnectedCounter = notConnectedCounter - 1
				self.sleep(1)		
		except self.StopThread:
			self.debugLog(u'Stop thread called.')
			pass
	############################################################################
	def stopConcurrentThread(self):
		self.stopThread = True
	############################################################################
	def serverUpdateInfo(self, devzone):
		for deviceId in self.serverList:
			devServer = indigo.devices[deviceId]
			if devzone.states['zoneID'] == devServer.states['currentZoneID']:
				updateServerInfo = True
			else:
				updateServerInfo = False
		return (updateServerInfo, devServer)