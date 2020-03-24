"""
# Extend metrics or delineation construction contexts with adapters built against the selected
# Python implementation.
"""
import sys
import importlib
import itertools
import pickle

from fault.system import execution as libexec
from fault.system import process
from fault.system import files
from fault.system import python

from ...context import templates
from ....factors import cc
from ....factors import data as ccd
from ....factors import constructors

tool_name = 'python'
name = 'fault.python'

def identification():
	"""
	# Collect the python reference parameter from the &sysconfig module.
	"""

	from importlib.machinery import EXTENSION_SUFFIXES
	version = '.'.join(map(str, sys.version_info[:2]))
	abi = sys.abiflags

	cache_tag = getattr(sys.implementation, 'cache_tag')
	if cache_tag is None:
		cache_tag = sys.implementation.name + version.replace('.', '') + abi

	triplet = cache_tag + abi + '-' + sys.platform

	return {
		'identifier': triplet,
		'version': version,
		'abi': abi,
		'tag': cache_tag,
		'implementation': sys.implementation.name,
		'executable': sys.executable,
		'extension-suffix': EXTENSION_SUFFIXES[0],
	}

def instantiate_software(dst, package, name, template, type, fault='fault'):
	# Initiialize llvm instrumentation or delineation tooling inside the target context.
	ctxpy = dst / 'lib' / 'python'

	command = [
		"python3", "-m",
		fault+'.text.bin.ifst',
		str(ctxpy / package / name),
		str(template), type,
	]

	pid, status, data = libexec.effect(libexec.KInvocation(sys.executable, command))
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
			'transformations': {
				# Effectively copy source files as &.bin.compile
				# takes Python source.
				'python': templates.Projection,
			},

			'integrations': {
				'module': templates.Inherit('tool:pyc-subprocess'),
				'library': templates.Inherit('tool:pyc-subprocess'),

				'tool:pyc-local': {
					'method': 'internal',
					'name': 'pyc',
					'interface': compile.__name__ + '.function_bytecode_compiler',
					'command': __package__ + '.compile',
				},

				# Likely unused in cases where the executing Python is the target Python.
				'tool:pyc-subprocess': {
					'method': 'python',
					'name': 'pyc',
					'interface': compile.__name__ + '.subprocess_bytecode_compiler',
					'command': __package__ + '.compile',
				},
			}
		},
		'python': {
			'inherit': domain,
			'default-factor-type': 'module',

			# They're not actually .pyc files, but rather raw marshal.dumps of code objects.
			'formats': {
				'library': 'pyc',
				'module': 'pyc',
			},
			'target-file-extensions': {
				'library': '.pyc',
				'module': '.pyc',
			},
		}
	}

def fragments(args, fault, ctx, ctx_route, ctx_params, domain):
	"""
	# Initialize the syntax tooling for delineation contexts.
	"""

	return {
		domain: {
			'variants': {
				'system': system,
				'architecture': architecture,
			},
			'transformations': {
				'python': {
					'command': __package__ + '.delineate',
					'interface': None,
					'method': 'pythoon',
				},
			},

			'integrations': {
				'elements': templates.Duplication,
			}
		},
		'python': {
			'inherit': domain,
			'default-type': 'module',
			'formats': {
				'library': 'pyc',
				'module': 'pyc',
			},
			'target-file-extensions': {
				'library': '.pyc',
			},
		}
	}

def instruments(args, fault, ctx, ctx_route, ctx_params, domain):
	"""
	# Initialize the instrumentation tooling for instruments contexts.
	"""
	imp = python.Import.from_fullname(__package__).container
	tmpl_path = imp.file().container / 'templates' / 'context.txt'

	instantiate_software(ctx_route, 'f_intention', tool_name, tmpl_path, 'metrics')

	# Register tool and probe constructor.
	from .. import coverage
	data = {
		'python-controller': '.'.join((coverage.__name__, coverage.Probe.__qualname__)),
	}

	return {
		domain: {
			'transformations': {
				'python': {
					'metrics': tool_name,
				}
			},
		},
		'metrics': {
			tool_name: data,
		}
	}

def install(args, fault, ctx, ctx_route, ctx_params):
	"""
	# Initialize the context for its configured intention.
	"""
	ctx_intention = ctx_params['intention']
	host_system = ctx.index['host']['system']

	mechfile = ctx_route / 'mechanisms' / name

	pydata = identification()

	if ctx_intention == 'fragments':
		data = fragments(args, fault, ctx, ctx_route, ctx_params)
	else:
		data = compilation(pydata['identifier'], host_system, pydata['tag'].replace('-','') + pydata['abi'])
		ccd.update_named_mechanism(mechfile, 'default', data)

		if ctx_intention == 'instruments':
			layer = instruments(args, fault, ctx, ctx_route, ctx_params, pydata['identifier'])
			ccd.update_named_mechanism(mechfile, 'instrumentation-control', layer)

	ccd.update_named_mechanism(mechfile, 'language-specifications', {
		'syntax': {
			'target-file-extensions': {
				'python': 'py',
			},
		}
	})

def main(inv:process.Invocation) -> process.Exit:
	fault = inv.environ.get('FAULT_CONTEXT_NAME', 'fault')
	ctx_route = files.Path.from_absolute(inv.environ['CONTEXT'])
	ctx = cc.Context.from_directory(ctx_route)
	ctx_params = ctx.index['context']
	install(inv.args, fault, ctx, ctx_route, ctx_params)
	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system(environ=('FAULT_CONTEXT_NAME', 'CONTEXT')))
