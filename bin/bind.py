"""
# Create the necessary preprocessor statements for building a bound Python executable.
"""
import os
import sys

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
		'-ferror-limit=3', '-Wno-array-bounds',
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

	'PYTHON_EXECUTABLE_PATH',
	'PYTHON_PATH_STR',
	'PYTHON_PATH',
	'PYTHON_OPTION_MODULES',

	'FACTOR_PATH_STR',
	'FACTOR_PATH',
]

envfp = os.environ.get('FACTORPATH', '').strip().split(':')

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

def binding(options, executable, target_module, entry_point, paths):
	return (
		"#define %s %s\n" %(dname, define)
		for (dname, define) in zip(requirements, [
			quoted(target_module),
			quoted(entry_point),
			quoted(executable),
			cpaths(paths),
			ipaths('PYTHON_PATH_STRING', paths),
			ipaths('INIT_PYTHON_OPTION', options),
			cpaths(envfp),
			ipaths('FACTOR_PATH_STRING', envfp),
		])
	)

def options(argv):
	options = []
	i = 0
	for x, i in zip(argv, range(len(argv))):
		if x[:2] != '-l':
			break
		options.append(x[2:])

	return options, argv[i:]

def display():
	import sys

	option_modules, argv = options(sys.argv[1:])
	module_path, call_name, *bpaths = argv
	paths = bpaths or sys.path

	for sf in binding(option_modules, sys.executable, module_path, call_name, paths):
		sys.stdout.write(sf)

if __name__ == '__main__':
	display()
