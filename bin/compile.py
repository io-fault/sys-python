"""
# Compile Python modules into stored bytecode.

# Provide high-level functions for compiling Python module into stored bytecode.
"""
import os
import builtins
import pickle

from fault.system import process

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

def main(inv:process.Invocation) -> process.Exit:
	target, origin, *remainder = inv.args

	params = dict()
	params.update(zip(remainder[0::2], remainder[1::2]))

	optimize = int(params.pop('optimize', 1))
	language, dialect = params.pop('format', 'python.psf-v3').split('.', 1)

	if dialect == 'ast':
		mkbytecode(target, origin, language, dialect, optimize, params)
	else:
		mkast(target, origin, language, dialect, optimize, params)

	return inv.exit(0)

if __name__ == '__main__':
	import sys
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
