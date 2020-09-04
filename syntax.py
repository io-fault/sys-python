"""
# AST tools for manipulating and querying a Python AST.

# Provides functions for instrumentation(future), constant injection, and coverable area detection(limited).
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

def coverable(tree, hasattr=hasattr):
	"""
	# Construct a &set of lines numbers that contains code
	# that can be covered.

	# Used by Python coverage reporting tools to identify coverage percentage.

	# [ Engineering ]
	# Currently does not extract exact expression ranges. Future revisions will
	# need information similar to what &..tools.llvm provides.
	"""
	seq = set()
	add = seq.add

	for x in ast.walk(tree):
		if not hasattr(x, 'lineno') or x.col_offset == -1:
			continue

		if isinstance(x, untraversable_nodes):
			# Letting expression nodes generate the coverable set.
			# These nodes don't actually generate line events during tracing.
			continue
		add(x.lineno)

	return seq

