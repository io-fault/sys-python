"""
# AST manipulations for injecting coverage counters into Python source.
"""
import ast
import builtins
import functools

from . import module
from . import source

BranchNodes = (
	ast.BoolOp,
	ast.IfExp,
)

expression_mapping = {
	ast.withitem: 'context_expr',
	ast.comprehension: 'value',
}

def visit_expression(node, parent, field, index):
	"""
	# Visit the node in a statement. Keyword defaults, expressions, statements.
	"""

	if isinstance(node, ast.withitem):
		yield from visit_expression(node.context_expr, node, 'context_expr', None)
		return
	elif isinstance(node, (ast.keyword, ast.Starred, ast.comprehension)):
		# Instrument the inside of the comprehension.
		yield from visit_expression(node.value, node, 'value', None)
		return
	elif isinstance(node, ast.arguments):
		# Only need keywords.
		for i, v in source.sequence_nodes(node.kw_defaults):
			yield from visit_expression(v, node, 'kw_defaults', i)
		return
	elif isinstance(node, (ast.Expr, ast.Return, ast.Assign, ast.AugAssign)):
		yield node.value, node, 'value', None
	else:
		# Count the expression as a whole.
		yield node, parent, field, index

	branches = set(x for x in source.bottom(node) if isinstance(x[0], BranchNodes))
	for x in branches:
		if isinstance(x[0], ast.BoolOp):
			for i, v in zip(range(len(x[0].values)), x[0].values):
				if isinstance(v, ast.AST):
					yield (v, x[0], 'values', i)
		elif isinstance(x[0], ast.IfExp):
			for y in source.shallow(x[0]):
				yield y
		else:
			pass # Never

def visit_container(nodes, parent, field):
	for index, stmt in nodes:
		if isinstance(stmt, ast.For):
			yield from visit_expression(stmt.iter, stmt, 'iter', None)
			yield from visit_container(source.sequence_nodes(stmt.body), stmt, 'body')
		elif hasattr(stmt, 'body'):
			yield from visit(stmt, parent, field, index)
		elif isinstance(stmt, ast.arguments):
			# Only need keywords.
			for i, v in source.sequence_nodes(stmt.kw_defaults):
				yield from visit_expression(v, stmt, 'kw_defaults', i)
		elif isinstance(stmt, ast.Expr) and stmt.col_offset == -1:
			# Likely docstring.
			pass
		elif isinstance(stmt, (ast.Name,)):
			pass
		elif isinstance(stmt, (ast.Break, ast.Continue)):
			yield (stmt, parent, field, index)
		else:
			yield from visit_expression(stmt, parent, field, index)

def visit(node, parent=None, field=None, index=None, sequencing=source.sequence_nodes):
	"""
	# Identify nodes that should be instrumented for coverage and profiling.
	"""
	for subfield, subnode in ast.iter_fields(node):
		if isinstance(subnode, ast.AST):
			yield from visit_expression(subnode, node, subfield, None)
		elif isinstance(subnode, list):
			yield from visit_container(sequencing(subnode), node, subfield)
		else:
			pass

# Profiling is not yet supported.
initialization = """
if True:
	from f_intention.python import instrumentation as _fi_module
	from functools import partial as _fi_partial
	import collections as _fi_col
	try:
		_FI_INCREMENT__ = _fi_partial(_fi_col._count_elements, _fi_module.counters)
	except:
		_FI_INCREMENT__ = _fi_module.counters.update
	del _fi_partial, _fi_col
	def _FI_COUNT__(area, rob, F=__file__, C=_FI_INCREMENT__):
		C(((F, area),))
		return rob
	#_FI_ENTER__ = _fi_module.note_enter
	#_FI_EXIT__ = _fi_module.note_exit
	#_FI_SUSPEND__ = _fi_module.note_suspend
	#_FI_CONTINUE__ = _fi_module.note_continue
	del _fi_module
""".strip() + '\n'

count_boolop_expression = "(_FI_INCREMENT__(((__file__, %r),)) or INSTRUMENTATION_ERROR)"
count_call_expression = "_FI_COUNT__(%r,None)"

# Seeks the pass for the replacement point.
profile = """
if True:
	try:
		_FI_ENTER__(%r)
		pass
	finally:
		_FI_EXIT__(%r)
"""

def construct_call_increment(node, area, path='/dev/null', lineno=1):
	s = count_call_expression % (area,)
	p = ast.parse(s, path)
	k = p.body[0]
	for x in ast.walk(k):
		source.node_set_address(x, (-lineno, 0))

	update = functools.partial(k.value.args.__setitem__, -1)
	return k, update

def construct_boolop_increment(node, area, path='/dev/null', lineno=1):
	s = count_boolop_expression % (area,)
	p = ast.parse(s, path)
	expr = p.body[0]
	for x in ast.walk(expr):
		source.node_set_address(x, (-lineno, 0))

	update = functools.partial(expr.value.values.__setitem__, 1)
	return expr, update

def construct_profile_trap(identifier, container, nodes, path='/dev/null', lineno=1):
	src = profile %(identifier,identifier)
	tree = ast.parse(src, path)
	trap = tree.body[0].body[0]

	trap.body[1:1] = nodes
	assert isinstance(trap.body[-1], ast.Pass)
	del trap.body[-1]

	return trap

def construct_initialization_nodes(path="/dev/null"):
	"""
	# Construct instrumentation initialization nodes for injection into an &ast.Module body.
	"""
	nodes = ast.parse(initialization, path)
	for x in ast.walk(nodes):
		source.node_set_address(x, (-1, 0))

	return nodes

def instrument(path, noded, address):
	"""
	# Adjust the AST so that &node will record its execution.
	"""

	# Counter injection node.
	node, parent, field, index = noded

	if isinstance(node, ast.Pass):
		note, update = construct_call_increment(node, address)
		getattr(parent, field)[index] = note
	elif isinstance(node, ast.expr):
		note, update = construct_boolop_increment(node, address, path=path)
		update(node)
		if index is None:
			setattr(parent, field, note.value)
		else:
			getattr(parent, field)[index] = note.value
	elif isinstance(node, (ast.arguments, ast.arg)):
		pass
	else:
		note, update = construct_call_increment(node, address)
		if index is not None:
			position=(0 if isinstance(node, source.InterruptNodes) else 1)
			getattr(parent, field).insert(index+position, note)
		else:
			assert False
			pass # never

	return node

def delineate(noded):
	node = noded[0]
	if hasattr(node, '_f_context'):
		area = node._f_context[0][0:2] + node._f_area[2:]
	else:
		area = getattr(node, '_f_area', None)

	return area

def apply(path, noded):
	node = noded[0]
	if hasattr(node, '_f_context'):
		area = node._f_context[0][0:2] + node._f_area[2:]
	else:
		area = node._f_area

	return instrument(path, noded, area)

def compile(factor, source, path, constants,
		parse=source.parse,
		hash=module.hash_syntax,
		filter=visit
	):
	"""
	# Compile Python source of a module into an instrumented &types.CodeObject
	"""
	srclines, tree, nodes = parse(source, path, filter=visit)

	for noded in nodes:
		if not hasattr(noded[0], '_f_area'):
			continue
		if isinstance(noded[0], (ast.expr_context, ast.slice)):
			continue

		apply(path, noded)

	# Add timestamp and factor id.
	module.inject(tree, factor, hash(source), constants)
	tree.body[0:0] = construct_initialization_nodes().body

	return tree

if __name__ == '__main__':
	from . import bytecode
	import sys
	import os
	out, src = sys.argv[1:]

	st = os.stat(src)
	with open(src) as f:
		co = compile(None, f.read(), src, (), filter=visit)

	bytecode.store(out, co, st.st_mtime, st.st_size)
