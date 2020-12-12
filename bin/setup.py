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

from ...factors import constructors
from ...factors import cc
from ...factors import data as ccd

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
	"""
	from . import compile

	return {
		'variants': {
			'system': system,
			'architecture': architecture,
		},
		'transformations': {
			# Effectively copy source files as &.bin.compile
			# takes Python source.
			'python': constructors.Projection,
			'v3': constructors.Projection,
			'v3.10': constructors.Projection,
		},

		'integrations': {
			'python-module': constructors.Inherit('tool:pyc-subprocess'),

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
		},

		# They're not actually .pyc files, but rather raw marshal.dumps of code objects.
		'formats': {
			'python-module': 'pyc',
		},
		'target-file-extensions': {
			'python-module': '.pyc',
		},
	}

def delineation(domain, system, architecture):
	"""
	# Initialize the syntax tooling for delineation contexts.
	"""

	return {
		'formats': {
			'python-module': 'i',
		},
		'target-file-extensions': {
			'python-module': '.i',
		},

		'variants': {
			'system': system,
			'architecture': architecture,
		},

		'transformations': {
			'v3.10': constructors.Inherit('tool:pyd-subprocess'),
			'v3': constructors.Inherit('tool:pyd-subprocess'),
			'python': constructors.Inherit('tool:pyd-subprocess'),

			'tool:pyd-subprocess': {
				'method': 'python',
				'command': __package__ + '.delineate',
				'interface': constructors.__name__ + '.delineation',
			},
		},

		'integrations': {
			'python-module': constructors.Clone,
		},
	}

def coverage(args, fault, ctx, ctx_route, ctx_params, domain):
	"""
	# Initialize the tooling for coverage contexts.
	"""
	imp = python.Import.from_fullname(__package__).container
	tmpl_path = imp.file().container / 'templates' / 'context.txt'

	instantiate_software(ctx_route, 'f_intention', tool_name, tmpl_path, 'metrics')
	return {}

def install(args, fault, ctx, ctx_route, ctx_params):
	"""
	# Initialize the context for its configured intention.
	"""
	ctx_intention = ctx_params['intention']
	host_system = ctx.index['host']['system']

	mechfile = ctx_route / 'mechanisms' / name

	pydata = identification()
	arch = pydata['tag'].replace('-', '')
	domain_id = pydata['identifier']

	if ctx_intention == 'delineation':
		data = delineation(domain_id, host_system, arch)
		ccd.update_named_mechanism(mechfile, 'root', {domain_id: data})
	else:
		data = compilation(domain_id, host_system, arch)
		ccd.update_named_mechanism(mechfile, 'root', {domain_id: data})

		if ctx_intention == 'coverage':
			layer = coverage(args, fault, ctx, ctx_route, ctx_params, domain_id)
			ccd.update_named_mechanism(mechfile, 'instrumentation-control', layer)

	ccd.update_named_mechanism(mechfile, 'path-setup', {'context': {'path': [domain_id]}})
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
