"""
# Compile Python modules into stored bytecode.

# Provide high-level functions for compiling Python module into stored bytecode.
"""
import os
import builtins
import pickle

from fault.system import process
from fault.system import files

def mkbytecode(target, unit, language, dialect, optimize, parameters=None):
	from .. import bytecode

	if not parameters:
		parameters = {}

	check = parameters.pop('check', 'time')
	intention = parameters.pop('intention', 'debug')
	factor_name = parameters.pop('factor', None)

	with open(unit, 'rb') as f:
		origin, stored_ast = pickle.load(f)

	co = builtins.compile(stored_ast, origin, 'exec', optimize=optimize)
	bytecode.store('never', target, co, -1, None)

def mkast(target, origin, language, dialect, optimize, parameters=None):
	from .. import module

	if not parameters:
		parameters = {}

	check = parameters.pop('check', 'time')

	encoding = parameters.pop('encoding', 'utf-8')
	intention = parameters.pop('intention', 'debug')
	if intention == 'coverage':
		from .. import instrumentation
		compiler = instrumentation.compile
		optimize = 0
	else:
		compiler = module.compile

	factor_name = parameters.pop('factor', None)
	constants = []

	with open(origin, 'r', encoding=encoding) as f:
		source_file_contents = f.read()

	ast = compiler(factor_name, source_file_contents, origin, constants)
	with open(target, 'wb') as out:
		pickle.dump((str(origin), ast), out)

def delineate(output, origin, params):
	from . import delineate
	fpath = params['factor'].split('.')
	delineate.process_source(str(output), str(origin), fpath)

def replicate(target, origin):
	(target).fs_alloc().fs_mkdir()
	(target).fs_replace(origin)

def archive(output, source):
	"""
	# Copy the units directory, &source, to the target image location &output.
	"""
	replicate(output, source)

def main(inv:process.Invocation) -> process.Exit:
	out, src, *remainder = inv.args
	output = files.Path.from_path(out)
	source = files.Path.from_path(src)

	params = dict()
	params.update(zip(remainder[0::2], remainder[1::2]))

	intent = params.pop('intention', 'error')
	optimize = int(params.pop('cpython-optimize', 1))
	language, dialect = params.pop('format', 'python.psf-v3').split('.', 1)
	delineated = params.pop('delineated', None)

	if delineated is not None:
		if delineated == 'archive':
			archive(output, source)
		else:
			assert delineated == 'json'
			delineate(output, source, params)
	else:
		if dialect == 'ast':
			mkbytecode(output, source, language, dialect, optimize, params)
		else:
			mkast(output, source, language, dialect, optimize, params)

	return inv.exit(0)

if __name__ == '__main__':
	import sys
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
