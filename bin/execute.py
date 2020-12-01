"""
# Execute a Python script or module within the testing context.

# Used by &..laboratory to provide a proper environment when executing
# Python subprocesses inside of tests.
"""
import os
import sys
import contextlib
import builtins
import types

from fault.system import process
from fault.system import python
from fault.system import files

def prepare(exectype, path, execargs):
	exits = contextlib.ExitStack()
	co = None

	finder = None
	if os.environ.get('PYTHONIMPORTREDIRECTS', None) is not None:
		from sdk.factors import testing
		finder = testing.RedirectFinder.inherit()
		exits.enter_context(finder.redirection())

	telemetry = os.environ.get('FAULT_MEASUREMENT_CONTEXT', None)
	if telemetry:
		from sdk.factors import metrics
		route = files.Path.from_absolute(telemetry)
		measures = metrics.Measurements(route)
		process_data = measures.event()
		probelist = map(str.strip, os.environ['FAULT_METRICS_PROBES'].split(':'))
		for probe_desc in filter(bool, probelist):
			name, probe_ir = probe_desc.split('/')
			probe = python.Import.dereference(probe_ir)(name)
			probe.reconnect(measures, process_data, finder)

	module = types.ModuleType('__main__')
	main = module.__dict__

	main.update({
		'__name__': '__main__',
		'__builtins__': builtins,
		'__spec__': None,
	})

	if exectype == 'script':
		ir = None
		fr = None
		pkg = None
		loader = None
		spec = None
	elif exectype == 'module':
		ir = python.Import.from_fullname(path)
		spec = ir.spec()
		loader = spec.loader

		if ir.is_package():
			pkg = str(ir)
			fr = ir.file().container / '__main__.py'
		else:
			pkg = str(ir.container) or None
			fr = ir.file()
			co = loader.get_code(spec.name)

		path = str(fr)

	main['__package__'] = pkg
	main['__file__'] = path
	main['__loader__'] = loader
	main['__spec__'] = spec

	if co is None:
		with open(path) as f:
			co = compile(f.read(), path, 'exec')

	sys.argv[0] = path
	sys.argv[1:] = execargs
	sys.modules['__main__'] = module # Likely discard old main.

	return exits, co, module

def main(inv:process.Invocation) -> process.Exit:
	exectype, path, *execargs = inv.args # module <import> *args | script <filepath> *args

	exits, co, module = prepare(exectype, path, execargs)
	with exits:
		exec(co, module.__dict__, module.__dict__)

	if exectype == 'script':
		# No exception raise by script presumes success.
		# Modules are expected to raise system exit, however.
		raise SystemExit(0)

	raise RuntimeError("module (%s) did not raise exit" %(path,))

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
