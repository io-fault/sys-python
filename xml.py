"""
# XML serialization for Python factors.
"""

import sys
import os
import os.path
import inspect
import functools
import itertools
import hashlib
import types
import lzma
import codecs
import contextlib
import importlib
import typing
import pickle

from ..system import libfactor
from ..routes import library as libroutes
from ..xml import library as libxml
from ..xml import python as xep
from ..text import library as libtext
from ..factors import tools

from ..development import xml as devxml

serialization = xep.Serialization() # currently only utf-8 is used.

# If pkg_resources is available, use it to identify explicit namespace packages.
try:
	import pkg_resources
	def is_namespace(path):
		return path in pkg_resources._namespace_packages

	def pkg_distribution(loader):
		return pkg_resources.Distribution.from_filename(loader.archive)
except ImportError:
	# no namespace concept without pkg_resources
	def is_namespace(path):
		return False

	def pkg_distribution(loader):
		return None

class Context(object):
	"""
	# Delineation extraction context for Python.

	# Manages the XML serialization Context and Cursor extracting
	# the fragments of a module.
	"""

	class_ignore = {
		'__doc__',     # Extracted explicitly.
		'__weakref__', # Runtime specific information.
		'__dict__',    # Class content.
		'__module__',  # Supplied by context.

		# Exception subclasses will have these attributes.
		'__cause__',
		'__context__',
		'__suppress_context__',
		'__traceback__',
	}

	method_order = (
		'__init__',
		'__new__',
		'__call__',
	)

	@staticmethod
	def module_context(route:libroutes.Import):
		"""
		# Given an import route, return the context package
		# and the project module.
		"""
		floor = route.floor()
		if floor is None:
			return None, route
		else:
			context = floor.container

			if not context:
				# route is likely
				return None, floor
			else:
				return context, floor

	def __init__(self, route):
		# initialize the package context
		# used for identifying project local references.
		self.route = route
		self.context, self.root = self.module_context(route)
		self.prefix = self.canonical((self.context or self.root).fullname)
		self.stack = []
		self.parameters = {}

	@contextlib.contextmanager
	def cursor(self, name, obj):
		self.stack += (name, obj)
		try:
			yield
		finally:
			del self.stack[-1]

	def is_class_method(self, obj:object,
			getfullargspec=inspect.getfullargspec,
			checks = (
				inspect.ismethod,
				inspect.isbuiltin,
				inspect.isfunction,
				inspect.ismethoddescriptor,
			)
		):
		"""
		# Determine if the given object is a class method.
		"""
		try:
			getfullargspec(obj)
		except TypeError:
			return False

		return any(x(obj) for x in checks)

	def is_class_property(self, obj:object,
			checks = (
				inspect.isgetsetdescriptor,
				inspect.isdatadescriptor,
			)
		):
		"""
		# Determine if the given object is a property.
		# Get-Set Descriptors are also identified as properties.
		"""
		return any(x(obj) for x in checks)

	def is_module(self, obj:object):
		"""
		# Overrideable interface to &inspect.ismodule.
		"""
		return inspect.ismodule(obj)

	def is_module_class(self, module:types.ModuleType, obj:object, isclass=inspect.isclass):
		"""
		# The given object is a plainly defined class that belongs to the module.
		"""
		return isclass(obj) and module.__name__ == obj.__module__

	def is_module_function(self,
			module:types.ModuleType,
			obj:object,
			isroutine=inspect.isroutine
		):
		"""
		# The given object is a plainly defined function that belongs to the module.
		"""
		subject = getattr(obj, '__wrapped__', obj)
		return isroutine(subject) and module.__name__ == subject.__module__

	def docstr(self, obj:object, getattr=getattr):
		"""
		# Variant of &inspect.getdoc that favors tab-indentations.
		"""
		rawdocs = getattr(obj, '__doc__', None)
		if rawdocs is None:
			return None

		lines = rawdocs.split('\n')

		# first non-empty line is used to identify
		# the indentation level of the entire string.
		for fl in lines:
			if fl.strip():
				break

		if fl.startswith('\t'):
			indentation = len(fl) - len(fl.lstrip('\t'))
			plines = tools.strip_notation_prefix([x[indentation:] for x in lines])
			return '\n'.join(plines)
		else:
			# assume no indentation and likely single line
			plines = tools.strip_notation_prefix(lines)
			return '\n'.join(plines)

	if hasattr(inspect, 'signature'):
		signature_kind_mapping = {
			inspect.Parameter.POSITIONAL_ONLY: 'positional',
			inspect.Parameter.POSITIONAL_OR_KEYWORD: None, # "default"
			inspect.Parameter.KEYWORD_ONLY: 'keyword',
			inspect.Parameter.VAR_POSITIONAL: 'variable',
			inspect.Parameter.VAR_KEYWORD: 'keywords',
		}

		def signature(self, obj:object, getsig=inspect.signature):
			"""
			# Overridable accessor to &inspect.getfullargspec.
			"""
			return getsig(obj)
	else:
		def signature(self, obj:object, getsig=inspect.getfullargspec):
			"""
			# Overridable accessor to &inspect.getfullargspec.
			"""
			sig = getsig(obj)

	def addressable(self, obj:object, getmodule=inspect.getmodule):
		"""
		# Whether the object is independently addressable.
		# Specifically, it is a module or inspect.getmodule() not return None
		# *and* can `obj` be found within the module's objects.

		# The last condition is used to prevent broken links.
		"""
		return self.is_module(obj) or getmodule(obj) is not None

	@functools.lru_cache(64)
	def canonical(self, name:str, Import=libroutes.Import.from_fullname):
		"""
		# Given an arbitrary module name, rewrite it to use the canonical
		# name defined by the package set (package of Python packages).

		# If there is no canonical package name, return &name exactly.
		"""
		return libfactor.canonical_name(Import(name))

	def address(self, obj:object, getmodule=inspect.getmodule):
		"""
		# Return the address of the given object; &None if unknown.
		"""

		if self.is_module(obj):
			# object is a module.
			module = obj
			path = (self.canonical(module.__name__), None)
		else:
			module = getmodule(obj)
			objname = getattr(obj, '__name__', None)
			path = (self.canonical(module.__name__), objname)

		return path

	def origin(self, obj:object):
		"""
		# Decide the module's origin; local to the documentation site, Python's
		# site-packages (distutils), or a Python builtin.
		"""
		module, path = self.address(obj)

		if module == self.prefix or module.startswith(self.prefix+'.'):
			pkgtype = 'context'
		else:
			m = libroutes.Import.from_fullname(module).module()
			if 'site-packages' in getattr(m, '__file__', ''):
				# *normally* distutils; likely from pypi
				pkgtype = 'distutils'
			else:
				pkgtype = 'builtin'

		return pkgtype, module, path

	@functools.lru_cache(32)
	def project(self, module:types.ModuleType, _get_route = libroutes.Import.from_fullname):
		"""
		# Return the project information about a particular module.

		# Returns `None` if a builtin, an unregistered package, or package without a project
		# module relative to the floor.
		"""
		route = _get_route(module.__name__)

		project = None
		if hasattr(module, '__loader__'):
			d = None
			try:
				d = pkg_distribution(module.__loader__)
			except (AttributeError, ImportError):
				# try Route.project() as there is no pkg_distribution
				pass
			finally:
				if d is not None:
					return {
						'name': d.project_name,
						'version': d.version,
					}

		return getattr(route.project(), '__dict__', None)

	def d_object(self, name, obj):
		yield from serialization.prefixed(name,
			serialization.switch('d:').object(obj),
		)

	def d_parameter(self, parameter):
		if parameter.annotation is not parameter.empty:
			yield from self.d_object('annotation', parameter.annotation)

		if parameter.default is not parameter.empty:
			yield from self.d_object('default', parameter.default)

	def d_signature_arguments(self, signature, km = {}):
		if signature.return_annotation is not signature.empty:
			yield from self.d_object('return', signature.return_annotation)

		for p, i in zip(signature.parameters.values(), range(len(signature.parameters))):
			yield from libxml.element('parameter',
				self.d_parameter(p),
				('identifier', p.name),
				('index', str(i)),
				# type will not exist if it's a positiona-or-keyword.
				('type', self.signature_kind_mapping[p.kind]),
			)

	def d_call_signature(self, obj, root=None):
		global itertools

		try:
			sig = self.signature(obj)
		except ValueError as err:
			# unsupported callable
			s = serialization.switch('d:')
			yield from s.error(err, obj, set())
		else:
			yield from self.d_signature_arguments(sig)

	def d_type(self, obj):
		# type reference
		typ, module, path = self.origin(obj)
		yield from libxml.element('reference', (),
			('source', typ),
			('factor', module),
			('name', path)
		)

	def d_doc(self, obj, prefix):
		doc = self.docstr(obj)
		if doc is not None:
			if False:
				yield from libxml.element('doc', libxml.escape_element_string(doc),
					('xml:space', 'preserve')
				)
			else:
				yield from libxml.element('doc',
					libtext.XML.transform('txt:', doc, identify=prefix.__add__),
				)

	def d_import(self, context_module, imported, *path):
		mn = imported.__name__
		try:
			cname = self.canonical(mn)
		except Exception as exc:
			# XXX: Associate exception with import element.
			cname = mn

		return libxml.element("import", None,
			('xml:id', '.'.join(path)),
			('identifier', path[-1]),
			('name', cname),
		)

	def d_source_range(self, obj):
		try:
			lines, lineno = inspect.getsourcelines(obj)
			end = lineno + len(lines)

			return libxml.element('source', None,
				('unit', 'line'),
				('start', str(lineno)),
				('stop', str(end-1)),
			)
		except (TypeError, SyntaxError, OSError):
			return libxml.empty('source')

	def d_function(self, method, qname, ignored={
				object.__new__.__doc__,
				object.__init__.__doc__,
			}
		):
		subject = getattr(method, '__wrapped__', method)
		is_wrapped = subject is not method

		yield from self.d_source_range(subject)
		if self.docstr(subject) not in ignored:
			yield from self.d_doc(subject, qname+'.')
		yield from self.d_call_signature(subject, method)

	def d_class_content(self, module, obj, name, *path,
			chain=itertools.chain.from_iterable
		):
		yield from self.d_source_range(obj)
		yield from self.d_doc(obj, name+'.')

		yield from libxml.element('bases',
			chain(map(self.d_type, obj.__bases__)),
		)

		yield from libxml.element('order',
			chain(map(self.d_type, inspect.getmro(obj))),
		)

		aliases = []
		class_dict = obj.__dict__
		class_names = list(class_dict.keys())
		class_names.sort()

		for k in sorted(dir(obj)):
			qn = '.'.join(path + (k,))

			if k in self.class_ignore:
				continue

			try:
				v = getattr(obj, k)
			except AttributeError as err:
				# XXX: needs tests
				s = serialization.switch('d:')
				yield from s.error(err, obj, set())

			if self.is_class_method(v):
				if v.__name__.split('.')[-1] != k:
					# it's an alias to another method.
					aliases.append((qn, k, v))
					continue
				if k not in class_names:
					# not in the immediate class' dictionary? ignore.
					continue

				# Identify the method type.
				if isinstance(v, classmethod) or k == '__new__':
					mtype = 'class'
				elif isinstance(v, staticmethod):
					mtype = 'static'
				else:
					# regular method
					mtype = None

				with self.cursor(k, v):
					yield from libxml.element('method', self.d_function(v, qn),
						('xml:id', qn),
						('identifier', k),
						('type', mtype),
					)
			elif self.is_class_property(v):
				local = True
				vclass = getattr(v, '__objclass__', None)
				if vclass is None:
					# likely a property
					if k not in class_names:
						local = False
				else:
					if vclass is not obj:
						local = False

				if local:
					with self.cursor(k, v):
						pfunc = getattr(v, 'fget', None)
						yield from libxml.element(
							'property', chain([
								self.d_source_range(pfunc) if pfunc is not None else (),
								self.d_doc(v, qn+'.'),
							]),
							('xml:id', qn),
							('identifier', k),
						)
			elif self.is_module(v):
				# handled the same way as module imports
				with self.cursor(k, v):
					yield from self.d_import(module, v, qn)
			elif isinstance(v, type):
				# XXX: Nested classes are not being properly represented.
				# Visually, they should appear as siblings in the formatted representation,
				# but nested physically.
				if v.__module__ == module and v.__qualname__.startswith(obj.__qualname__+'.'):
					# Nested Class; must be within.
					yield from self.d_class(module, x, path + (x.__qualname__,))
				else:
					# perceive as class data
					pass
			else:
				# data
				pass

		for qn, k, v in aliases:
			with self.cursor(k, v):
				yield from libxml.element('alias', None,
					('xml:id', qn),
					('identifier', k),
					('address', v.__name__),
				)

	def d_class(self, module, obj, *path):
		name = '.'.join(path)
		with self.cursor(path[-1], path[-1]):
			yield from libxml.element('class',
				self.d_class_content(module, obj, name, *path),
				('xml:id', name),
				('identifier', path[-1]),
			)

	def d_context(self, package, project, getattr=getattr):
		# XXX: rename to project (project/@name, project/@context)
		if package and project:
			pkg = package.module()
			prj = project.module()
			yield from libxml.element('context', (),
				('context', self.prefix),
				('path', self.canonical(pkg.__name__)),
				('system.path', os.path.dirname(pkg.__file__)),
				('project', getattr(prj, 'name', None)),
				('identity', getattr(prj, 'identity', None)),
				('icon', getattr(prj, 'icon', None)),
				('fork', getattr(prj, 'fork', None)),
				('contact', getattr(prj, 'contact', None)),
				('controller', getattr(prj, 'controller', None)),
				('abstract', getattr(prj, 'abstract', '')),
			)

	def d_module(self, factor_type, route, module, compressed=False):
		lc = 0
		ir = route
		sources = [libroutes.File.from_absolute(module.__file__)]

		for route in sources:
			if compressed:
				with route.open('rb') as src:
					h = hashlib.sha512()
					x = lzma.LZMACompressor(format=lzma.FORMAT_ALONE)
					cs = bytearray()

					data = src.read(512)
					lc += data.count(b'\n')
					h.update(data)
					cs += x.compress(data)
					while len(data) == 512:
						data = src.read(512)
						h.update(data)
						cs += x.compress(data)

					hash = h.hexdigest()
					cs += x.flush()
			else:
				if route.exists():
					with route.open('rb') as src:
						cs = src.read()
						lc = cs.count(b'\n')
						hash = hashlib.sha512(cs).hexdigest()
				else:
					hash = ""
					cs = b""
					lc = 0

			yield from libxml.element('source',
				itertools.chain(
					libxml.element('hash',
						libxml.escape_element_string(hash),
						('type', 'sha512'),
						('format', 'hex'),
					),
					libxml.element('data',
						libxml.escape_element_bytes(codecs.encode(cs, 'base64')),
						('type', 'application/x-lzma' if compressed else None),
						('format', 'base64'),
					),
				),
				('path', str(route)),
				# inclusive range
				('start', 1),
				('stop', str(lc)),
			)

		yield from self.d_doc(module, 'factor..')

		for k in sorted(dir(module)):
			if k.startswith('__'):
				continue
			v = getattr(module, k)

			if self.is_module_function(module, v):
				yield from libxml.element('function', self.d_function(v, k),
					('xml:id', k),
					('identifier', k),
				)
			elif self.is_module(v):
				yield from self.d_import(module, v, k)
			elif self.is_module_class(module, v):
				yield from self.d_class(module, v, k)
			else:
				yield from libxml.element('data',
					self.d_object('object', v),
					('xml:id', k),
					('identifier', k),
				)

	def d_submodules(self, route, module, element='subfactor'):
		for typ, l in zip(('package', 'module'), route.subnodes()):
			for x in l:
				sf = x.module()
				if sf is not None:
					noted_type = getattr(sf, '__type__', None)
					noted_icon = getattr(sf, '__icon__', None)
				else:
					noted_type = 'error'
					noted_icon = ''

				yield from libxml.element(element, (),
					('type', noted_type),
					('icon', noted_icon),
					('container', 'true' if typ == 'package' else 'false'),
					('identifier', x.basename),
				)
		else:
			# Used by documentation packages to mimic Python modules.
			mods = getattr(module, '__submodules__', ())
			for x in mods:
				yield from libxml.element(element, (),
					('type', 'module'),
					('identifier', x),
				)

		if element == 'subfactor':
			# Composite fractions are subfactors too.
			if module.__factor_composite__:
				source_factors = libfactor.sources(route)
				prefix = len(source_factors.absolute)

				for x in source_factors.tree()[1]:
					rpoints = x.absolute[prefix:]
					path = '/'.join(rpoints)

					yield from libxml.element(element, (),
						('type', 'source'),
						('path', path),
						('identifier', x.points[-1]),
					)

			# conditionally for cofactor build.
			if route.container:
				# build out siblings
				yield from self.d_submodules(route.container, route.container.module(), 'cofactor')

	def emit(fs, key, iterator):
		r = fs.route(key)
		r.init('file')

		with r.open('wb') as f:
			# the xml declaration prefix is not written.
			# this allows stylesheet processing instructions
			# to be interpolated without knowning the declaration size.
			f.writelines(iterator)

	def serialize(self, module:types.ModuleType, metrics:typing.Mapping=None):
		"""
		# Construct an interator emitting an XML Fragments document. 
		"""

		route = self.route
		cname = self.canonical(route.fullname)
		basename = cname.split('.')[-1]

		package = route.floor()
		if package is None:
			project = None
		else:
			project = package / 'project'

		language = None
		try:
			if hasattr(module, '__file__'):
				factor_type = getattr(module, '__factor_type__', 'module')

				if factor_type == 'chapter':
					ename = 'chapter'
				else:
					ename = 'module'
					language = getattr(module, '__factor_language__', 'python')
			else:
				factor_type = 'namespace'

			content = libxml.element(ename,
				self.d_module(factor_type, route, module),
				('identifier', basename),
				('name', cname),
				('language', language)
			)
		except Exception as error:
			# When module is &None, an error occurred during import.
			factor_type = 'factor'

			# Serialize the error as the module content if import fails.
			content = libxml.element('module',
				serialization.prefixed('error',
					serialization.switch('d:').object(error),
				),
				('identifier', basename),
				('name', cname),
			)

		yield from libxml.element('factor',
			itertools.chain(
				self.d_context(package, project),
				self.d_submodules(route, module),
				content,
			),
			('version', '0'),
			('name', cname),
			('identifier', basename),
			('path', (
				None if '__factor_path__' not in module.__dict__
				else module.__factor_path__
			)),
			('depth', (
				None if '__directory_depth__' not in module.__dict__
				else (module.__directory_depth__ * '../')
			)),
			('type', factor_type),
			('xmlns', 'http://fault.io/xml/fragments'),
			('xmlns:d', 'http://fault.io/xml/data'),
			('xmlns:l', 'http://fault.io/xml/literals'),
			('xmlns:txt', 'http://fault.io/xml/text'),
			('xmlns:xlink', 'http://www.w3.org/1999/xlink'),
		)

if __name__ == '__main__':
	# structure a single module
	import sys
	r = libroutes.Import.from_fullname(sys.argv[1])
	w = sys.stdout.buffer.write
	wl = sys.stdout.buffer.writelines
	try:
		w(b'<?xml version="1.0" encoding="utf-8"?>')
		ctx = Context(r)
		module = r.module()
		module.__factor_composite__ = False
		i = ctx.serialize(module)
		wl(i)
		w(b'\n')
		sys.stdout.flush()
	except:
		import pdb
		pdb.pm()
