#! /usr/bin/env/python
'''
plugin.py

nose plugin to run tests in an extension library

Uses the _testext extension to load and run the test, via the runner helper
'''

import logging 
import os
from nose.plugins.base import Plugin
from nose.util import tolist
import re 
from datetime import datetime
from unittest import TestCase


log = logging.getLogger('nose.plugins')

class DynLibTestCase (TestCase):
	def __init__(self, libname, funcname):
		self.funcname = funcname
		self.libname = libname
		TestCase.__init__(self)
		self._testMethodDoc = funcname

	def runTest(self):
		print "\nDynLibTestCase:", self.libname, self.funcname
		import subprocess
		p = subprocess.Popen(["testext_wrapper", self.libname, self.funcname])
		p.wait()
		if p.returncode == 0:
			return True
		elif p.returncode == 1:
			return False
		elif p.returncode == 2:
			return None

class TestExt(Plugin):
	name = 'testext'
	regex = None 

	def options(self, parser, env=os.environ):
		parser.add_option(
			'--with-testext', action='store_true', dest='testext_enabled',
 			default=env.get('NOSE_TESTEXT'),
			help='Enable test discovery and execution in C extensions [NOSE_TESTEXT]'
		)
		parser.add_option(
			'--testext-regex', action='store', dest='testext_regex',
 			default=env.get('NOSE_TESTEXT_REGEX', "testext_.*"),
			help='Regular expression to match test functions [NOSE_TESTEXT_REGEX]'
		)

	def configure(self, options, conf):
		if not self.can_configure:
			return
		self.enabled = options.testext_enabled
		self.regex = options.testext_regex
		self.conf = conf

	def wantFile(self, filename):
		'''wantFile: we want all dynamic libraries (*.so.x.y.z)'''
		libre = r".*\.so(\.[0-9]+)*$"
		if re.match(libre, filename):
			return True
		else:
			return False

	def wantDirectory(self, dirname):
		'''wantDirectory: we want all directories'''
		return True

	def loadTestsFromFile(self, filename):
		import subprocess
		p = subprocess.Popen(['readelf', '-W', '-s', filename], stdout=subprocess.PIPE)
		syms, stderr = p.communicate()
	
		cases = []
		for s in syms.split('\n'):
			m = re.search(r'FUNC .* ([^ ]+)$', s)
			if m:
				if re.match(self.regex, m.group(1)):
					cases.append(DynLibTestCase(filename, m.group(1)))
		if cases == []:
			return False
		return cases
