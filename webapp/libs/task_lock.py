import os
from webapp import app


class LockManager(object):

	def __init__(self, *args, **kwargs):
		self.lock_name = kwargs['lock_name']
		self.lock_dir = kwargs['lock_dir']

		if self.lock_dir[-1:] != '/':
			self.lock_dir += '/'

	@property
	def is_locked(self):
		if not os.path.isfile(self.filename):
			return False
		try:
			pid = self.read_file(self.filename)
			if not self.is_pid_of_instance(pid):
				self.delete_lockfile()
				return False
		except Exception as e:
			app.logger.warning('Exception when checking lock "{0}".'.format(str(e)))
		return True

	@property
	def filename(self):
		suffix = '.lock'
		return self.lock_dir + self.lock_name + suffix

	def is_pid_of_instance(self, pid):
		if not os.path.isdir('/proc/' + str(pid)):
			return False
		cmdline = self.read_file('/proc/' + str(pid) + '/cmdline')
		my_cmdline = self.read_file('/proc/' + str(os.getpid()) + '/cmdline')
		if cmdline != my_cmdline:
			return False
		return True

	def delete_lockfile(self):
		os.remove(self.filename)

	def read_file(self, filename):
		f = open(filename, 'r')
		content = f.read()
		f.close()
		return content

	def create_lock_file(self):
		if not os.path.isdir(self.lock_dir):
			os.makedirs(self.lock_dir)
		return open(self.filename, "w")

	def lock(self):
		try:
			f = self.create_lock_file()
			f.write(str(os.getpid()))
			f.close()
		except Exception as e:
			app.logger.warning('Exception when creating lock: "{0}".'.format(str(e)))
			return False
		return True

	def unlock(self):
		if os.path.isfile(self.filename):
			os.unlink(self.filename)

	def _run(self, task):
		try:
			task()
		# we ignore all exceptions because we don't want the lock to stay down
		except Exception as e:
			app.logger.error('Exception in running task: "{0}".'.format(str(e)))

	def run_once(self, task):
		if not self.is_locked and self.lock():
			self._run(task)
			self.unlock()
		else:
			app.logger.warning('Task {0} is locked.'.format(self.lock_name))
