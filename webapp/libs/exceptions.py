# exception classes

class InvalidAddress(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

class InvalidURL(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

class InvalidCallbackURL(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

class OpenStackConfiguration(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

class CoinBaseAddressBuild(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)
