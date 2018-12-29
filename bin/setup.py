"""
# Extend metrics or delineation construction contexts with adapters built against the selected
# Python implementation.
"""
import sys
import importlib
import itertools
import pickle

from fault.system import library as libsys
from fault.system import process
from fault.system import files
from fault.system import python

from ....factors import cc
from .. import parameters

tool_name = 'python'
name = 'fault.python'

delineate_template = {
	'command': __package__ + '.delineate',
	'interface': cc.__name__ + '.package_module_parameter',
	'method': 'python',
	'name': 'delineate-python-source',
	'redirect': 'stdout'
}

def add_delineate_mechanism(route, tool_name:str):
	"""
	# Add delineation mechanism.
	"""

	return cc.update_named_mechanism(route, tool_name, delineate_template)

def instantiate_software(dst, package, name, template, type, fault='fault'):
	# Initiialize llvm instrumentation or delineation tooling inside the target context.
	ctxpy = dst / 'lib' / 'python'

	command = [
		"python3", "-m",
		fault+'.text.bin.ifst',
		str(ctxpy / package / name),
		str(template), type,
	]

	pid, status, data = libsys.effect(libsys.KInvocation(sys.executable, command))
	if status != 0:
		sys.stderr.write("! ERROR: tool instantiation failed\n")
		sys.stderr.write("\t/command/\n\t\t" + " ".join(command) + "\n")
		sys.stderr.write("\t/status/\n\t\t" + str(status) + "\n")

		sys.stderr.write("\t/message/\n")
		sys.stderr.buffer.writelines(b"\t\t" + x + b"\n" for x in data.split(b"\n"))
		sys.stderr.write("<- [%d]\n" %(pid,))
		raise SystemExit(1)

def compilation(domain, system, architecture):
	"""
	# Generate mechanisms for compiling Python libraries.
	# This domain only supports one-to-one source-to-target compilation,
	# and used by (factor/type)`factor.directory` records.
	"""
	from . import compile

	return {
		domain: {
			'variants': {
				'system': system,
				'architecture': architecture,
			},
			'formats': {
				'library': 'pyc',
			},
			'target-file-extensions': {
				'library': '.pyc',
			},
			'transformations': {
				'python': {
					'type': 'transparent',
					'interface': cc.__name__ + '.transparent',
					'command': "/bin/ln",
				},
			},

			'integrations': {
				'library': {
					'inherit': 'tool:pyc-subprocess',
				},
				'tool:pyc-local': {
					'method': 'internal',
					'interface': compile.__name__ + '.function_bytecode_compiler',
					'name': 'pyc',
					'command': __package__ + '.compile',
				},

				# Likely unused in cases where the executing Python is the target Python.
				'tool:pyc-subprocess': {
					'method': 'python',
					'interface': compile.__name__ + '.subprocess_bytecode_compiler',
					'name': 'pyc',
					'command': __package__ + '.compile',
				},
			}
		},
		'python': {
			'inherit': domain,
		}
	}

def fragments(args, fault, ctx, ctx_route, ctx_params):
	"""
	# Initialize the syntax tooling for delineation contexts.
	"""

	mechanism_layer = {
		'factor': {
			'transformations': {
				'python': delineate_template,
			}
		}
	}

	cc.update_named_mechanism(ctx_route / 'mechanisms' / name, 'delineation', mechanism_layer)

def instruments(args, fault, ctx, ctx_route, ctx_params, domain):
	"""
	# Initialize the instrumentation tooling for instruments contexts.
	"""
	imp = python.Import.from_fullname(__package__).container
	tmpl_path = imp.file().container / 'templates' / 'context.txt'

	instantiate_software(ctx_route, 'f_intention', tool_name, tmpl_path, 'metrics')

	# Register tool and probe constructor.
	from .. import library
	data = {
		'constructor': '.'.join((library.__name__, library.Probe.__qualname__)),
	}

	return {
		domain: {
			'transformations': {
				'python': {
					'telemetry': data
				}
			},
		}
	}

def install(args, fault, ctx, ctx_route, ctx_params):
	"""
	# Initialize the context for its configured intention.
	"""
	ctx_intention = ctx_params['intention']
	host_system = ctx.index['host']['system']

	mechfile = ctx_route / 'mechanisms' / name

	pydata = parameters.identification()
	sysfact = parameters.sysconfig_factors(pydata, domain='host')
	pydata.update(sysfact)

	if ctx_intention == 'fragments':
		data = fragments(args, fault, ctx, ctx_route, ctx_params)
	else:
		data = compilation(pydata['identifier'], host_system, pydata['tag'].replace('-','') + pydata['abi'])
		cc.update_named_mechanism(mechfile, 'default', data)
		cc.update_named_mechanism(mechfile, 'language-specifications', {
			'syntax': {
				'target-file-extensions': {
					'python': 'py',
				},
			}
		})

		if ctx_intention == 'instruments':
			layer = instruments(args, fault, ctx, ctx_route, ctx_params, pydata['identifier'])
			cc.update_named_mechanism(mechfile, 'metrics', layer)

	# Setup a Python extension symbol for Construction Context tools.
	f = parameters.sysconfig_factors(parameters.identification(), domain='system')
	(ctx_route / 'symbols' / 'context:python-extension').store(pickle.dumps(f))

def main(inv:process.Invocation) -> process.Exit:
	fault = inv.environ.get('FAULT_CONTEXT_NAME', 'fault')
	ctx_route = files.Path.from_absolute(inv.environ['CONTEXT'])
	ctx = cc.Context.from_directory(ctx_route)
	ctx_params = ctx.index['context']
	install(inv.args, fault, ctx, ctx_route, ctx_params)
	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system(environ=('FAULT_CONTEXT_NAME', 'CONTEXT')))
