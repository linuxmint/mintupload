
# mintUpload
#	Clement Lefebvre <root@linuxmint.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2
# of the License.

try:
	import sys
	import urllib
	import ftplib
	import os
	import datetime
	import gettext
	import paramiko
	import pexpect
	import commands
	from user import home
	from configobj import ConfigObj
except:
	print "You do not have all the dependencies!"
	sys.exit(1)

# i18n
gettext.install("messages", "/usr/lib/linuxmint/mintUpload/locale")

class CustomError(Exception):
	'''All custom defined errors'''
	def __init__(self, detail):
		sys.stderr.write(os.linesep + self.__class__.__name__ + ': ' + detail + os.linesep*2)

class ConnectionError(CustomError):
	'''Raised when an error has occured with an external connection'''
	pass

class FilesizeError(CustomError):
	'''Raised when the file is too large or too small'''
	pass

