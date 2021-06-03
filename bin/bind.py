"""
# Bind a system executable to a Python module factor.
"""
import os
import sys

from fault.text.bin import cat
from fault.system import files
from fault.system import identity
from fault.system import execution
from fault.system import query

project_directory = (files.Path.from_absolute(__file__) ** 2)

def compile_sc(target, source, include, compiler=None):
	"""
	# Construct the parameters to be used to compile and link the new executable according to
	# (python/module)`sysconfig`.
	"""
	import sysconfig

	ldflags = tuple(sysconfig.get_config_var('LDFLAGS').split())
	libdir = sysconfig.get_config_var('LIBDIR')
	pyversion = sysconfig.get_config_var('VERSION')
	pyabi = sysconfig.get_config_var('ABIFLAGS') or ''
	pyspec = 'python' + pyversion + pyabi

	if not compiler:
		compiler = sysconfig.get_config_var('CC') or 'cc'

	sysargv = [compiler, '-w', '-x', 'c', '-o', target]
	sysargv.extend(ldflags)

	if libdir:
		rpath = '-Wl,-rpath,' + libdir
		sysargv.append(rpath)

	sysargv.extend([
		'-I' + sysconfig.get_config_var('INCLUDEPY'),
		'-I' + include,
		'-L' + libdir,
		'-l' + pyspec,
		source,
	])

	return sysargv

def _macrostr(func, string):
	return func + '("' + string + '")'

requirements = [
	'TARGET_MODULE',
	'DEFAULT_ENTRY_POINT',
	'ARGUMENT_COUNT',
	'ARGUMENTS',

	'PYTHON_EXECUTABLE_PATH',
	'PYTHON_PATH_STR',
	'PYTHON_PATH',
	'PYTHON_CONTROL_IMPORTS',

	'FACTOR_PATH_STR',
	'FACTOR_PATH',
	'FACTOR_SYSTEM',
	'FACTOR_PYTHON',
	'FACTOR_MACHINE',

	'FAULT_PYTHON_PRODUCT',
	'FAULT_CONTEXT_NAME',
]

def chars(string):
	return "','".join(string)

def escape(s):
	return s.replace('\\', '\\\\').replace('"', '\\"')

def static_array_terminated(string):
	return "'" + chars(string) + "', '\\000'"

def quoted(string):
	return '"' + string + '"'

def qpaths(paths):
	return ', '.join(['L' + quoted(x) for x in paths])

def cpaths(paths):
	return quoted(':'.join(paths))

def ipaths(xmacro, paths):
	if paths and (paths[0] or len(paths) > 1):
		return "\\\n\t" + " \\\n\t".join([xmacro+'("%s")' %(escape(x),) for x in paths])
	else:
		return ""

def binding(platform, struct, executable, target_module, entry_point, *argv):
	system, python, machine = platform
	fi, fault_location, products, control_imports, paths = struct

	extensions = []
	values = [
		quoted(target_module),
		quoted(entry_point),
		len(argv),
		ipaths('ARGUMENT', argv),
		quoted(executable),
		cpaths(paths),
		ipaths('PYTHON_PATH_STRING', paths),
		ipaths('IMPORT', control_imports),
		cpaths(products),
		ipaths('FACTOR_PATH_STRING', products),
		quoted(system),
		quoted(python),
		quoted(machine),
		quoted(fault_location[0]),
		quoted(fault_location[1]),
	]

	if fi:
		extensions.append('_FAULT_INVOCATION')
		values.append(str(1))

	return (
		"#define %s %s\n" %(dname, define)
		for (dname, define) in zip(requirements + extensions, values)
	)

def options(argv, symbol='main'):
	fpd = files.Path.from_absolute(files.__file__) ** 3
	fl = (str(fpd), 'fault')
	fi = True
	system, python = identity.python_execution_context()
	machine = identity.root_execution_context()[1]
	effect = 'executable'
	products = []
	options = []
	paths = []
	defines = []
	verbose = 0
	i = 0

	for x, i in zip(argv, range(len(argv))):
		opt = x[:2]

		if opt == '-l':
			options.append(x[2:])
		elif opt == '-L':
			products.append(x[2:])
		elif opt == '-F':
			# fault product and context name override.
			offset = x.rfind('/')
			fl = (x[2:offset], x[offset+1:])
		elif opt == '-f':
			fi = not fi
		elif opt == '-P':
			paths.append(x[2:])
		elif opt == '-S':
			system_name = x[2:]
		elif opt == '-M':
			machine = x[2:]
		elif opt == '-x':
			symbol = x[2:]
		elif opt == '-D':
			defines.append(tuple(x[2:].split('=', 1)))
		elif opt == '-E':
			effect = 'source'
		elif opt == '-v':
			verbose += 1
		else:
			break

	struct = (fi, fl, products, options, sys.path+paths)
	platform = (system, python, machine)
	return effect, verbose, symbol, platform, struct, argv[i:]

def render(output, factor_path, factor_argv, factor_element, platform, struct):
	for sf in binding(platform, struct, sys.executable, factor_path, factor_element, *factor_argv):
		output(sf.encode('utf-8'))

	sourcepath = project_directory / 'embed.txt'
	data = cat.structure(sourcepath, 'executable')
	for p in data.keys():
		output(data[p].encode('utf-8'))

def main(sysargv):
	effect, verbose, *config, rargv = options(sysargv[1:])
	target_exe, factor_path, *factor_argv = rargv

	if effect == 'source':
		# Render the source that would have been compiled.
		render(sys.stdout.buffer.write, factor_path, factor_argv, *config)
		sys.exit(200)
	else:
		# Create executable.
		assert effect == 'executable'

		includes = str(project_directory / 'include' / 'src')
		try:
			xargv = compile_sc(target_exe, '/dev/stdin', includes, os.environ.get('CC') or None)
		except ImportError:
			raise

		exe = xargv[0]
		for exe in query.executables(exe):
			break

		if verbose:
			sys.stderr.write(' '.join(xargv) + '\n')

		r, w = os.pipe()
		try:
			compiler = execution.KInvocation(str(exe), list(xargv))
			pid = compiler.spawn(fdmap=[(r, 0), (1, 1,), (2, 2)])
			import io
			output = io.FileIO(w, 'w')
		except:
			os.close(w)
			raise
		finally:
			os.close(r)

		try:
			with output:
				render(output.write, factor_path, factor_argv, *config)
		finally:
			rpid, status = os.waitpid(pid, 0)
			sys.exit(os.WEXITSTATUS(status))

if __name__ == '__main__':
	try:
		main(sys.argv)
	finally:
		sys.stdout.flush()
