"""
# Module finder and loader for Python factors using polynomial-1.
"""
import os
import stat
import sys
import importlib.machinery

from os.path import dirname
from os.path import join
from os import stat as fs_stat

def ftype(path, fs_typemap = {stat.S_IFREG: 'data', stat.S_IFDIR: 'directory'}):
	try:
		s = fs_stat(path)
	except:
		return 'void'

	return fs_typemap.get(stat.S_IFMT(s.st_mode), 'other')

def compose_image_path(variants, default='void', groups=[["system", "architecture"], ["name"]]):
	"""
	# Create a variant path according to the given &groups and &variants.
	"""
	segments = []

	for g in groups[:-1]:
		fields = ([(variants.get(x) or default) for x in g])
		segment = '-'.join(fields)
		segments.append(segment)

	# Name must be '.' separated.
	fields = ([(variants.get(x) or default) for x in groups[-1]])
	segment = '.'.join(fields)
	segments.append(segment)

	return segments

class IntegralFinder(object):
	"""
	# Select an integral based on the configured variants querying the connected factor paths.
	"""

	suffixes = ['.py']
	ModuleSpec = importlib.machinery.ModuleSpec
	ExtensionFileLoader = importlib.machinery.ExtensionFileLoader

	class Loader(importlib.machinery.SourceFileLoader):
		"""
		# Loader for compiled Python integrals. Compiled modules are not checked
		# against the source unlike Python's builtin loader.
		"""
		_compile = staticmethod(importlib._bootstrap_external._compile_bytecode)

		def __init__(self, bytecode, fullname, path):
			self._bytecode = bytecode
			self._source = path
			super().__init__(fullname, path)

		def exec_module(self, module):
			module.__file__ = self._source
			module.__cache__ = self._bytecode

			spec = module.__spec__
			if spec.submodule_search_locations:
				module.__path__ = spec.submodule_search_locations

			super().exec_module(module)

		def get_code(self, fullname):
			# Factors being explicitly compiled, code objects
			# are stored directly without pycache headers.
			try:
				with open(self._bytecode, 'rb') as f:
					# It's the build system's job to make sure everything is updated,
					# so don't bother with headers used by Python's builtin caching system.
					bc = f.read()
			except FileNotFoundError:
				return super().get_code(fullname)

			return self._compile(bc, fullname, self._bytecode, source_path=self._source)

		def set_data(self, *args, **kw):
			raise NotImplementedError("integral modules may not be directly updated using the loader")

	def __init__(self,
			groups,
			python_bytecode_variants,
			extension_variants,
			integral_container_name='__f-int__'
		):
		"""
		# Initialize a finder instance for use with the given variants.
		"""
		self.index = dict()
		self.groups = groups
		self.integral_container_name = integral_container_name

		self.python_bytecode_variants = python_bytecode_variants
		self.extension_variants = extension_variants

		# These (following) properties are not the direct parameters of &IntegralFinder
		# as it is desired that the configuration of the finder to be introspectable.
		# There is some potential for selecting a usable finder out of meta_path
		# using the above fields. The below fields are the cache used by &find_spec.

		self._ext = self._init_segment(groups, extension_variants)
		self._pbc = self._init_segment(groups, python_bytecode_variants)

	@staticmethod
	def _init_segment(groups, variants):
		v = dict(variants)
		v['name'] = '{0}'

		# polynomial-1
		segments = (compose_image_path(v, groups=groups))
		final = segments[-1] + '.i'
		del segments[-1]

		assert '{0}' in final # &groups must have 'name' in the final path identifier.
		return segments, final, final.format

	def connect(self, route, *, roots=()):
		"""
		# Add the route to finder connecting its subdirectories for import purposes.

		# Similar to adding a filesystem path to Python's &sys.path.
		"""

		if not roots:
			with open(join(route, '.product', 'ROOTS')) as f:
				roots = f.read().split('\n')

		self.index.update((x, route) for x in roots if x not in self.index)
		return self

	def disconnect(self, route):
		"""
		# Remove a route from the finder's set eliminating any relevant index entries.
		"""

		keys = []

		for k, v in self.index:
			if v == route:
				keys.append(k)

		for k in keys:
			del self.index[k]

		return self

	@classmethod
	def invalidate_caches(self):
		pass

	def find(self, name):
		"""
		# Retrieve the product with a root that matches the start of the given &name.
		"""
		soa = name.find('.')
		if soa == -1:
			if name not in self.index:
				# Must be root package if there is no leading name.
				return None
			else:
				soa = len(name)

		# Accessible modules are expected to be anchored to the product directory.
		prefix = name[:soa]
		if prefix not in self.index:
			return None

		return self.index[prefix]

	def find_spec(self, name, path, target=None):
		"""
		# Using the &index, check for the presence of &name's initial package.
		# If found, the integrals contained by the connected directory will be
		# used to load either an extension module or a Python bytecode module.
		"""

		# Project Protocols aren't used as they may require recursive imports.

		pd = self.find(name)
		if pd is None:
			return None
		rlen = len(pd)

		ipath = name.split('.')
		route = join(pd, *ipath)
		parent = dirname(route)
		final = ipath[-1]

		typ = ftype(route)
		pkg = False

		if typ == 'void':
			# Check for `extensions` factor.
			cur = parent
			exts = join(cur, 'extensions')
			while ftype(exts) == 'void':
				cur = dirname(cur)
				exts = join(cur, 'extensions')
				if len(cur) <= rlen or cur == '/':
					# No extensions directory.
					break
			else:
				# Found an extensions directory.
				# Check for C-API module.

				xpath = route[len(cur)+1:]
				ints = join(parent, self.integral_container_name)
				rroute = join(exts, ints[len(cur)+1:])
				extfactor = join(exts, xpath)

				if ftype(extfactor) != 'void':
					# .extension entry is present
					leading, filename, fformat = self._ext
					path = join(rroute, *leading, fformat(final))

					l = self.ExtensionFileLoader(name, path)
					spec = self.ModuleSpec(name, l, origin=path, is_package=False)
					return spec

		if typ == 'directory':
			# Not an extension; path is selecting a directory.
			pkg = True
			pysrc = join(route, '__init__.py')
			module__path__ = route
			final = '__init__'
			idir = join(route, self.integral_container_name)

			if ftype(pysrc) == 'void':
				# Handle context enclosure case.
				ctx = join(route, 'context')
				if ftype(ctx) == 'void':
					return None

				module__path__ = route
				pysrc = join(ctx, 'root.py')
				final = 'root'
				idir = join(ctx, self.integral_container_name)

			origin = str(pysrc)
		else:
			# Regular Python module or nothing.
			idir = join(parent, self.integral_container_name)
			for x in self.suffixes:
				pysrc = route + x
				if ftype(pysrc) == 'data':
					break
			else:
				# No recognized sources.
				return None

			module__path__ = dirname(pysrc)
			origin = pysrc

		leading, filename, fformat = self._pbc
		cached = join(idir, *leading, fformat(final))

		l = self.Loader(cached, name, pysrc)
		spec = self.ModuleSpec(name, l, origin=origin, is_package=pkg)
		spec.cached = cached

		if pkg:
			spec.submodule_search_locations = [module__path__]

		return spec

	@classmethod
	def create(Class, intention, system, architecture):
		"""
		# Construct a standard loader selecting integrals with the given &intention.
		"""

		python_id = sys.implementation.name + ''.join(map(str, sys.version_info[:2]))
		python_id = python_id.replace('-', '')

		bc = {
			'system': system,
			'architecture': python_id,
			'intention': intention,
		}

		ext = {
			'system': system,
			'architecture': architecture,
			'intention': intention,
		}

		g = [['system','architecture'],['name','intention']]

		return Class(g, bc, ext)

	@classmethod
	def default(Class, intention='debug'):
		"""
		# Create the default finder using the environment.
		"""
		sys_id = os.environ.get('FCI_SYSTEM', '').strip()
		mach_id = os.environ.get('FCI_ARCHITECTURE', '').strip()
		u = os.uname()
		return Class.create(intention, sys_id or u.sysname.lower(), mach_id or u.machine)

def activate(intention='debug', paths=None):
	"""
	# Install loaders for the (envvar)`FACTORPATH` products.
	"""
	global Activated

	sfif = IntegralFinder.default(intention)
	Activated = sfif
	if paths is None:
		paths = os.environ.get('FACTORPATH', '').split(':')

	for x in paths:
		if not x:
			# Ignore empty fields.
			continue
		sfif.connect(x)

	sys.meta_path.insert(0, sfif)
