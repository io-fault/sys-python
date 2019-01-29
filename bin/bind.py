"""
# Create a Python executable bound to the execution of a particular module.
"""

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
	'PYTHON_EXECUTABLE_PATH',
	'TARGET_MODULE',
	'DEFAULT_ENTRY_POINT',
	'PYTHON_PATH',
	'PYTHON_PATH_STR',
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
	return 'L' + quoted(':'.join(paths))

def binding(executable, target_module, entry_point, paths):
	return [
		"#define %s %s\n" %(dname, define)
		for (dname, define) in zip(requirements, [
			quoted(executable),
			quoted(target_module),
			quoted(entry_point),
			qpaths(paths),
			cpaths(paths),
		])
	]

if __name__ == '__main__':
	import sys
	module_path, call_name, *bpaths = sys.argv[1:]
	paths = bpaths or sys.path
	print(''.join(binding(sys.executable, module_path, call_name, paths)))
