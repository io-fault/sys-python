"""
# Compile Python modules into stored bytecode.

# Provide high-level functions for compiling Python module into stored bytecode.
"""
import os
from fault.system import library as libsys
from fault.time import library as libtime

from .. import module
from .. import bytecode

def subprocess_bytecode_compiler(
		build, adapter,
		o_type, output, i_type, inputs,
		verbose=True,
		format=None,
		filepath=str
	):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes in a distinct process.
	"""
	intention = context.intention(factor.domain)
	inf, = inputs

	optimize = '1'
	if intention in ('debug', 'metrics', 'test'):
		optimize = '0'

	command = [None, filepath(output), filepath(inf), optimize]
	return command

def function_bytecode_compiler(
		build, adapter,
		o_type, output, i_type, inputs,
		verbose=True, filepath=str
	):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes locally to minimize overhead.
	"""

	intention = build.context.intention(None)
	inf, = inputs # One source file.
	params = {
		'factor': build.factor.fullname,
		'intention': intention,
	}

	optimize = 1
	if intention in ('debug', 'metrics', 'test'):
		optimize = 0

	command = [
		store, filepath(output), filepath(inf), optimize, params
	]
	return command

def store(target, source, optimize, parameters=None):
	if not parameters:
		parameters = {}

	intention = parameters.pop('intention', 'debug')
	if intention == 'metrics':
		from .. import instrumentation
		compiler = instrumentation.compile
		optimize = 0
	else:
		compiler = module.compile

	factor_name = parameters.pop('factor', None)
	constants = [
		('__timestamp__', int(libtime.now())),
	]

	with open(source) as f:
		co = compiler(factor_name, f.read(), source, constants, optimize=optimize)
		st = os.fstat(f.fileno())
		bytecode.store(target, co, st.st_mtime, st.st_size)

def main(inv:libsys.Invocation) -> libsys.Exit:
	target, infile, *remainder = inv.args

	params = dict()
	params.update(zip(remainder[0::2], remainder[1::2]))
	optimize = int(params.pop('optimize', 1))

	store(target, infile, optimize, params)
	return inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
