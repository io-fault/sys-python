"""
# Query functions for interrogating Python ASTs.
"""
import ast

untraversable_nodes = (
	ast.Global, ast.Dict, ast.Str,
	ast.Name, ast.List, ast.Tuple,
	ast.arg,
	ast.Assign,
)

def apply(path:str, callable:object):
	"""
	# Apply the given &callable to the parsed AST of the file
	# selected by the given &path.
	"""

	with open(path) as f:
		a = ast.parse(f.read(), path)
		ast.fix_missing_locations(a)
		return callable(a)

def coverable(ast, hasattr=hasattr):
	"""
	# Construct a &set of lines numbers that contains code
	# that can be covered.

	# Used by Python coverage reporting tools to identify coverage percentage.
	"""
	seq = set()
	add = seq.add

	for x in ast.walk(a):
		if not hasattr(x, 'lineno'):
			continue

		if x.col_offset != -1:
			if isinstance(x, untraversable_nodes):
				# Letting expression nodes generate the coverable set.
				# These nodes don't actually generate line events during tracing.
				continue
			add(x.lineno)

	return seq

