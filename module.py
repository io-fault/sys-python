"""
# Module compilation tools.
"""
import ast
import builtins
import typing

constant_expression = "%s = %r"

def mkconstant(name, value, path='/dev/null', lineno=-1):
	"""
	# Create a constant for injection into a module.
	"""

	s = constant_expression % (name, value,)
	p = ast.parse(s, path)
	assert isinstance(p, ast.Module)

	k = p.body[0]
	return k

def inject(tree:ast.Module, factor:str, constants:typing.Iterable[typing.Tuple[str,str]]):
	"""
	# Inject the &ast.Module, &tree, with module-level assignments provided by &constants.
	"""

	f_id = mkconstant('__factor__', factor)
	syn_hash = mkconstant('__syntax_hash__', '')
	cnodes = [mkconstant(*pair) for pair in constants]
	cnodes[0:0] = (f_id, syn_hash)

	tree.body[0:0] = cnodes
	return cnodes

def compile(factor, source, path, constants, optimize=1, compiler=builtins.compile):
	"""
	# Compile a module's source injecting a factor identifier and source hash.
	"""

	tree = ast.parse(source, path)
	inject(tree, factor, constants)

	return compiler(tree, path, 'exec', optimize=optimize)
