"""
# Create the necessary preprocessor statements for building a bound Python executable.
"""
import os
import sys
from fault.text.bin import cat
from fault.system import files

def command(target, source, compiler='cc'):
	"""
	# Construct the parameters to be used to compile and link the new executable according to
	# (python/module)`sysconfig`.
	"""
	import sysconfig

	ldflags = tuple(sysconfig.get_config_var('LDFLAGS').split())
	pyversion = sysconfig.get_config_var('VERSION')
	pyabi = sysconfig.get_config_var('ABIFLAGS') or ''
	pyspec = 'python' + pyversion + pyabi

	return (
		sysconfig.get_config_var('CC') or compiler, '-v',
		'-ferror-limit=2', '-Wno-array-bounds',
		'-o', target,
	) + ldflags + (
		'-I' + sysconfig.get_config_var('INCLUDEPY'),
		'-L' + sysconfig.get_config_var('LIBDIR'),
		'-l' + pyspec,
		source,
	)

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
]

def chars(string):
	return "','".join(string)

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
		return "\\\n\t" + " \\\n\t".join([xmacro+'("%s")' %(x,) for x in paths])
	else:
		return ""

def binding(struct, executable, target_module, entry_point, *argv):
	system_context, machine_arch, fi, fault_location, products, control_imports, paths = struct

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
	]

	if fault_location is not None:
		extensions.extend([
			'FAULT_PYTHON_PRODUCT',
			'FAULT_CONTEXT_NAME',
		])
		values.extend([
			quoted(fault_location[0]),
			quoted(fault_location[1]),
		])

	if system_context is not None:
		extensions.append('FACTOR_SYSTEM')
		values.append(quoted(system_context))

	if machine_arch is not None:
		extensions.append('FACTOR_MACHINE')
		values.append(quoted(machine_arch))

	if fi:
		extensions.append('_FAULT_INVOCATION')
		values.append(str(1))

	return (
		"#define %s %s\n" %(dname, define)
		for (dname, define) in zip(requirements + extensions, values)
	)

# Determines how far processing should go.
target_control = {
	'-E': 'source',
	'-c': 'object',
	'-X': 'extension',
	'-x': 'executable',
}

def options(argv):
	fl = None
	fi = True
	system_context = None
	machine_arch = None
	effect = 'source'
	products = []
	options = []
	paths = []
	defines = []
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
			system_context = x[2:]
		elif opt == '-m':
			machine_arch = x[2:]
		elif opt == '-D':
			defines.append(tuple(x[2:].split('=', 1)))
		elif opt in target_control:
			effect = target_control[opt]
			assert opt == x # Flag option has additional data.
		else:
			break

	struct = (system_context, machine_arch, fi, fl, products, options, sys.path+paths)
	return effect, struct, argv[i:]

def render(output):
	effect, struct, argv = options(sys.argv[1:])
	factor_path, call_name, *xargv = argv

	for sf in binding(struct, sys.executable, factor_path, call_name, *xargv):
		output.write(sf)

	sourcepath = (files.Path.from_path(__file__) ** 2)/'embed.txt'
	data = cat.structure(sourcepath, 'executable')
	for p in data.keys():
		output.write(data[p])

if __name__ == '__main__':
	render(sys.stdout)
	sys.stdout.flush()
