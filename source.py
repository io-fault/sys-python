"""
# Python source (AST) processing tools.
"""
import ast
import tokenize
import itertools
import collections
import functools
import builtins

from . import module

# Tokens skipped to identify the end of an AST node.
insignificant = set([
	tokenize.ENCODING,
	tokenize.ENDMARKER,
	tokenize.INDENT,
	tokenize.DEDENT,
	tokenize.NL,
	tokenize.NEWLINE,
	tokenize.COMMENT,
])

InlineComprehension = (
	ast.ListComp,
	ast.GeneratorExp,
	ast.DictComp,
)

InterruptNodes = (
	ast.Break,
	ast.Continue,
	ast.Raise,
	ast.Return,
	ast.Yield,
	ast.YieldFrom,
)

def sequence_nodes(node_list):
	# Reverses and enumerates to allow immediate instrumenation insertions
	# to occur when a node is processed by the downstream generators.
	l = list(zip(range(len(node_list)), node_list))
	l.reverse()
	return l

def shallow(node, iter_fields=ast.iter_fields, isinstance=isinstance, list=list):
	"""
	# &ast.iter_child_nodes implementation providing path context for node substitution.
	"""

	for x in ((subnode, node, field, None) for field, subnode in iter_fields(node)):
		subnode = x[0]

		if isinstance(subnode, list):
			yield from (
				(v, node, x[2], i) for i, v in sequence_nodes(subnode)
				if isinstance(v, ast.AST)
			)
		elif isinstance(subnode, ast.AST):
			yield x

def bottom(tree, listdir=shallow, Queue=collections.deque):
	"""
	# &ast.walk implementation providing path context for node substitution.
	"""

	d = Queue(shallow(tree))
	pop = d.popleft
	extend = d.extend
	while d:
		n = pop()
		extend(listdir(n[0]))
		yield n

def node_set_address(node, address):
	"""
	# Set the `lineno` and `col_offset` attributes on the &node.
	"""
	node.lineno, node.col_offset = address

def node_remove_docstring(container):
	"""
	# Remove the initial &ast.Expr node in the body of &container given
	# that it has the properties that would identify it as the docstring source.
	"""
	if not container.body:
		return

	if not hasattr(container, 'docstring'):
		return

	if not isinstance(container.body[0], ast.Expr):
		return

	if container.body[0].col_offset != -1:
		# Probably not the doc-string node.
		return

	assert container.body[0].value.s == container.docstring
	del container.body[0]

def associate_siblings(following, nodes,
		iterate=ast.iter_child_nodes,
		chain=itertools.chain,
		list=list,
		isinstance=isinstance,
		hasattr=hasattr,
		getattr=getattr
	):
	"""
	# Associate the child nodes of &nodes with their following
	# sibling taking care to communicate the parent's following
	# sibling for the final child.

	# &following can be &None if the node is at the end of the document.
	"""

	immediate = list(iterate(nodes))
	n_map = collections.defaultdict(list)
	for node in immediate:
		ln = getattr(node, 'lineno', None)

		if isinstance(node, ast.expr_context):
			# Purely informative; no need to associate these.
			continue
		elif ln is None:
			# Find a child with location data.
			sub = [(x.lineno, x.col_offset) for x in ast.walk(node) if hasattr(x, 'lineno')]
			sub.sort()
			if sub:
				node.lineno, node.col_offset = sub[0]
				ln = node.lineno
			else:
				continue

		address = (ln, node.col_offset)
		n_map[address].append(node)

	positions = list(n_map.keys())
	positions.sort()
	if positions:
		positions.append(following)

	# Update each record noting the following sibling.
	s1 = zip(positions[0::2], positions[1::2])
	s2 = zip(positions[1::2], positions[2::2])
	for subject, follows in chain(s1, s2):
		for lnode in n_map[subject]:
			yield (subject, (lnode, follows))
			yield from associate_siblings(follows, lnode)

def map_tokens(tokens, STRING=tokenize.STRING):
	"""
	# Construct a dictionary associating start addresses with their corresponding token.
	"""

	token_map = {}
	for i in range(len(tokens)):
		t = tokens[i]
		if t.start not in token_map:
			token_map[t.start] = i
		if t.type == STRING:
			# Additional address for possible doc-strings.
			token_map[(t.end[0], -1)] = i
			token_map[(t.start[0], t.start[1]+1)] = i

	return token_map

def count_trailing_insignificant(tokens, OP=tokenize.OP, NAME=tokenize.NAME):
	count = 0
	backwards = iter(reversed(tokens))

	for t in backwards:
		if t.type not in insignificant:
			if t.type in {OP, NAME}:
				if t.string in {'->', 'and', 'or', 'if'}:
					# Skip BoolOp keywords.
					count += 1
					continue

				sub = t.line.strip().split()
				if ''.join(sub) in {'else:', 'finally:', 'except:', 'elif:'}:
					count += 1
					continue
			break
		else:
			count += 1

	return count

def identify_boundary(tokens, start, end, OP=tokenize.OP, NAME=tokenize.NAME):
	"""
	# Narrows the token window by trimming insignificant (whitespace or certain keywords) tokens
	# from the list.

	# The default token sequence for a node is constrained by the node's location and it's
	# identified following sibling, &associate_siblings.
	"""
	# Extract window from following sibling address.
	l = list(tokens[start:end])
	n_tokens = len(l)

	# Trim whitespace from list.
	trim(l)

	position, token = find_terminal(l, len(l))
	if position < len(l):
		# Maybe some unwanted whitespace.
		del l[position+1:]
		count = count_trailing_insignificant(l) + 1
		token = l[-count]
		return len(l)-count, token, token.start
	else:
		return position, token, token.end

def find_terminal(tokens, length, stop=None, condition=(lambda x: False), OP=tokenize.OP):
	"""
	# Find the end of the context tokens
	"""
	opened = closed = 0

	for i, t in enumerate(tokens):
		if t.type == OP:
			if t.string in '([{':
				opened += 1
			elif t.string in ')]}':
				closed += 1
				if closed > opened:
					return i, t
				continue

		if closed == opened:
			if (t.type == OP and stop == t.string.strip()) or condition(t):
				return i, t

	return i+1, tokens[-1]

def find_token(tokens, token_type, enum=enumerate):
	for i, v in enum(tokens):
		if v.type == token_type:
			return i, v

def find_newline(tokens, NEWLINE=tokenize.NEWLINE, enum=enumerate):
	for i, v in enum(tokens):
		if v.type == NEWLINE:
			return i, v

def find_token_with_string(tokens, token_type, string, enum=enumerate):
	for i, v in enum(tokens):
		if v.type == token_type and v.string == string:
			return i, v

def isolate_enclosure(start, stop, tokens=(), OP=tokenize.OP):
	t_offset, open_c = find_token_with_string(tokens, OP, start)
	del tokens[:t_offset+1]

	# Find close.
	t_offset, token = find_terminal(tokens, len(tokens), stop=stop)

	end = tokens[t_offset]
	del tokens[:t_offset+1]

	# Likely the starting node, inclusive on the opening and closing braces.
	return open_c, end, open_c.start, end.end

def isolate_name(tokens, NAME=tokenize.NAME):
	"""
	# Return the first NAME token in &tokens and remove it along with the
	# ones that preceded it.
	"""

	k = find_token(tokens, NAME)
	t_offset, t = k
	del tokens[:t_offset+1]
	return t, t, t.start, t.end

def isolate_number(tokens, NUMBER=tokenize.NUMBER):
	"""
	# Return the first NAME token in &tokens and remove it along with the
	# ones that preceded it.
	"""

	k = find_token(tokens, NUMBER)
	t_offset, t = k
	del tokens[:t_offset+1]
	return t, t, t.start, t.end

def isolate_string(tokens, STRING=tokenize.STRING, enum=enumerate):
	t_offset, first = find_token(tokens, STRING)
	del tokens[:t_offset+1]

	last = first
	# Look for the final string in the token window.
	for i, x in enum(tokens):
		if x.type == STRING:
			last = x
		elif x.type in insignificant:
			pass
		else:
			break
	del tokens[:i+1]

	return first, last, first.start, last.end

isolate = {
	ast.Bytes: isolate_string,
	ast.Str: isolate_string,
	ast.Num: isolate_number,
	ast.Name: isolate_name,
	ast.Attribute: isolate_name,
	ast.NameConstant: isolate_name,
	ast.Dict: functools.partial(isolate_enclosure, '{', '}'),
	ast.Set: functools.partial(isolate_enclosure, '{', '}'),
	ast.List: functools.partial(isolate_enclosure, '[', ']'),
	ast.Subscript: functools.partial(isolate_enclosure, '[', ']'),
	ast.Call: functools.partial(isolate_enclosure, '(', ')'),
}

def chain(tokens, nodes, node, address, following, OP=tokenize.OP):
	"""
	# Delineate a chain of nodes that are identified by the same address.
	"""
	t_offset = 0

	for current in nodes:
		try:
			r = isolate[current.__class__](tokens)
			yield current, r
		except KeyError:
			# Essentially, the chain has stopped.
			pass

def trim(tokens):
	"""
	# Identify the number of trailing whitespace tokens and remove them from the list.
	"""

	count = count_trailing_insignificant(tokens)
	del tokens[len(tokens)-count:]

	return count

# Types that can be processed by &chain.
chain_classes = tuple(isolate)

def areas(token_map, tokens, context, node, address, following):
	"""
	# Given a node and the tokens from the start of the node,
	# to the next following sibling node, identify the actual
	# stop address of the node filtering whitespace backwards,
	# and balancing nesting operators forward.
	"""

	if address not in token_map:
		return
	start = token_map[address]
	end = eol = None

	if following is not None:
		if following <= address:
			stop = start + find_newline(itertools.islice(tokens, start))[0]
		else:
			stop = token_map[following]
	else:
		# End of file pointer.
		stop = None

	if isinstance(node, (ast.Expr, ast.Str)) and address[1] == -1:
		# Doc-string.
		t = tokens[start]
		yield node, t.start, t.end
	elif isinstance(node, chain_classes):
		scope = tokens[start:stop]
		for x in chain(scope, context, node, address, following):
			yield x[0], x[1][2], x[1][3]
	else:
		position, t, end = identify_boundary(tokens, start, stop)
		yield node, address, end or t.end

def _lookup_region(associations, contexts, tokens, tmap, node, list=list, isinstance=isinstance):
	# Usually partial()'d by &_prepare.
	address = associations.get(node)
	if address is None:
		return (), ()

	start, stop = address
	assert start == (node.lineno, node.col_offset)

	context = list(contexts[start])
	if isinstance(node, chain_classes):
		# Align the stop of the root context's following sibling as &areas
		# will be calculating the boundary of *all* nodes in &context.
		# This is the reason &_lookup_region returns a set of delineations.
		pstart, stop = associations.get(context[0], ((0,0), (0,0)))
		assert stop is None or stop > start
		chain = True
	else:
		chain = False

	context.reverse()
	ld = [(x,(y,v)) for x,y,v in areas(tmap, tokens, context, node, start, stop)]

	return context if chain else (), ld

def join(lookup, nodes):
	"""
	# Assign the address information provided by &lookup to the nodes
	# generated by the &nodes iterator.
	"""
	for node_desc in nodes:
		node = node_desc[0]
		if hasattr(node, '_f_area'):
			# Likely filled in from context.
			continue

		context, nodeset = lookup(node)
		if context is not None:
			# Empty contexts are used to filter nodes without addressing information.

			i = 0
			in_ctx = 0
			f_context = []
			for xnode, (start, stop) in nodeset:
				xnode._f_area = start + stop
				xnode._f_context = f_context
				xnode._f_index = i
				f_context.append(xnode._f_area)
				in_ctx += 1 if xnode is node else 0
				i += 1
			del i
		else:
			assert nodeset[0][0] is node
			start, stop = nodeset[0][1]
			node._f_area = start + stop

		yield node_desc

def _prepare(nodes, tokens, filter=bottom, identify=_lookup_region):
	# Note the syntax area of the nodes in the AST.
	tmap = map_tokens(tokens)

	sa = {}
	d=collections.defaultdict(list)
	for k, (node, follow) in (associate_siblings(None, nodes)):
		if follow is not None and follow < k:
			follow = None
		sa[node] = (k, follow)

		if hasattr(node, 'lineno'):
			d[(node.lineno, node.col_offset)].append(node)

	lookup = functools.partial(_lookup_region, sa, d, tokens, tmap)
	yield from join(lookup, filter(nodes))

def parse(source:str, path:str, filter=bottom, encoding='utf-8') -> ast.Module:
	"""
	# Parse the given &source creating an &ast.Module whose child nodes have their exact areas
	# assigned to the `_f_area` attribute.
	"""
	nodes = ast.parse(source, path)
	ast.fix_missing_locations(nodes)

	readline = iter(source.encode(encoding).splitlines(True)).__next__
	tokens = list(tokenize.tokenize(readline))

	return nodes, _prepare(nodes, tokens, filter=filter)

if __name__ == '__main__':
	import sys
	src, = sys.argv[1:]
	with open(src) as f:
		nodes, selected = parse(f.read(), src)

	buffer = []
	for nd in selected:
		n = nd[0]
		if not hasattr(n, '_f_area'):
			continue
		area = n._f_area
		area = (area[0], area[1]+1, area[2], area[3]+1)
		if hasattr(n, '_f_context'):
			start = n._f_context[0][:2]
			area = (start[0], start[1]+1) + area[2:]
		buffer.append('%d.%d-%d.%d\t%s%s'%(area + (n.__class__.__name__,repr(nd[1]))))
		if len(buffer) > 64:
			print('\n'.join(buffer))
			del buffer[:]

	print('\n'.join(buffer))
	del buffer[:]
