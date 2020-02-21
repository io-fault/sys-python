"""
# Incorporate the constructed factors for use by the system targeted by the Construction Context.

# This copies constructed files into a filesystem location that Python requires them
# to be in order for them to be used. For fabricated targets, this means placing
# bytecode compiles into (system/filename)`__pycache__` directories. For Python extension
# modules managed with composite factors, this means copying the constructed extension
# library into the appropriate package directory.
"""
import os
import sys
import marshal

from fault.project import library as libproject
from fault.project import explicit

from fault.system import process
from fault.system import python
from fault.system import files
from fault.system import identity

from ...tools.python.bytecode import serialize_timestamp_checked

try:
	import importlib.util
	cache_from_source = importlib.util.cache_from_source
except (ImportError, AttributeError):
	try:
		import imp
		cache_from_source = imp.cache_from_source
		del imp
	except (ImportError, AttributeError):
		# Make a guess preferring the cache directory.
		try:
			import os.path
			def cache_from_source(filepath):
				return os.path.join(
					os.path.dirname(filepath),
					'__pycache__',
					os.path.basename(filepath) + 'c'
				)
		except:
			raise
finally:
	pass

def main(inv:process.Invocation) -> process.Exit:
	"""
	# Incorporate the constructed targets.
	"""
	intention, *factors = inv.args
	env = os.environ

	py_variants = dict(zip(['system', 'architecture'], identity.python_execution_context()))
	os_variants = dict(zip(['system', 'architecture'], identity.root_execution_context()))

	for x in map(files.Path.from_path, factors):
		context = x.identifier

		wholes, composites = explicit.query(x)

		# Handle bytecode caches.
		for fpath, data in wholes.items():
			sources = data[-1]
			if not sources:
				continue

			cache_dir = sources[0] * '__pycache__'
			cache_dir.fs_mkdir()

			caches = map(files.Path.from_absolute, map(cache_from_source, map(str, sources)))
			prefix = x + fpath

			for src, cache in zip(sources, caches):
				name, *ext = src.identifier.split('.')
				var = {'name': name}
				var.update(py_variants)
				segment = libproject.compose_integral_path(var)

				i = (src * '__f-int__') + segment
				if intention is not None:
					i = i.suffix_filename('.%s.i' %(intention,))
				else:
					i = i.suffix_filename('.i')

				if i.fs_type() == 'void':
					continue

				sys.stdout.write("[*| %s -> %s]\n" %(i, cache))
				if cache.fs_type() != 'void':
					os.unlink(str(cache))

				stat = os.stat(str(src))
				try:
					code = marshal.loads(i.fs_load())
					cache.fs_store(serialize_timestamp_checked(code, stat.st_mtime, stat.st_size))
				except ValueError:
					pass

		for fpath, data in composites.items():
			if 'extensions' not in fpath:
				continue
			domain, typ, syms, sources = data

			fpath = list(fpath)
			prefix = (x + fpath) * '__f-int__'

			var = {'name': fpath[-1]}
			var.update(os_variants)
			segment = libproject.compose_integral_path(var)

			i = prefix + segment
			if intention is not None:
				i = i.suffix_filename('.%s.i' %(intention,))
			else:
				i = i.suffix_filename('.i')

			del fpath[fpath.index('extensions')]
			target = x + fpath
			export = target.suffix_filename('.so')

			target.container.fs_mkdir()

			if i.fs_type() == 'void':
				sys.stdout.write("[!# expected target (%s) for '%s' does not exist]\n" %(i, export))
			else:
				sys.stdout.write("[&| %s -> %s]\n" %(i, export))
				export.fs_link_relative(i)

	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
