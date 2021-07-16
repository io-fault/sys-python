"""
# Compile Python modules into stored bytecode.

# Provide high-level functions for compiling Python module into stored bytecode.
"""
import os

from fault.system import process

from .. import module
from .. import bytecode

def subprocess_bytecode_compiler(
		build, adapter,
		output, inputs,
		verbose=True,
		format=None,
		filepath=str
	):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes in a distinct process.
	"""

	intention = build.intention
	inf, = inputs # Only supports one source file.

	optimize = '1'
	if intention in ('debug', 'instruments', 'injections'):
		optimize = '0'

	command = [None] + adapter['tool']
	argv = [filepath(output), filepath(inf), 'optimize', optimize, 'intention', intention]
	return command + argv

def function_bytecode_compiler(
		build, adapter, output,
		inputs,
		verbose=True, filepath=str
	):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes locally to minimize overhead.
	"""

	intention = build.intention
	inf, = inputs # Only supports one source file.
	params = {
		'factor': build.factor.absolute_path_string,
		'intention': intention,
		'check': 'never',
	}

	optimize = 1
	if intention in ('debug', 'instruments', 'injections'):
		optimize = 0
		if intention == 'debug':
			params['check'] = 'time'

	command = [store, filepath(output), filepath(inf), optimize, params]
	return command

def store(target, source, optimize, parameters=None):
	if not parameters:
		parameters = {}

	check = parameters.pop('check', 'time')
	intention = parameters.pop('intention', 'debug')
	if intention == 'instruments':
		from .. import instrumentation
		compiler = instrumentation.compile
		optimize = 0
	else:
		compiler = module.compile

	factor_name = parameters.pop('factor', None)
	constants = []

	with open(source) as f:
		source_file_contents = f.read()
		co = compiler(factor_name, source_file_contents, source, constants, optimize=optimize)
		bytecode.store(check, target, co, f.fileno(), source_file_contents)

def main(inv:process.Invocation) -> process.Exit:
	target, infile, *remainder = inv.args

	params = dict()
	params.update(zip(remainder[0::2], remainder[1::2]))
	optimize = int(params.pop('optimize', 1))

	store(target, infile, optimize, params)
	return inv.exit(0)

if __name__ == '__main__':
	import sys
	sys.dont_write_bytecode = True
	process.control(main, process.Invocation.system())
