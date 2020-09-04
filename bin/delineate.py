"""
# Delineate a Python source file.
"""
import sys
import ast
import functools
import typing

from fault.system import process
from fault.system import files

from fault.syntax import types as syntax
from fault.context import comethod
from fault.context.tools import cachedcalls

from .. import source
from .. import comments

Assignments = (ast.Assign, ast.AnnAssign)

def read_name(node):
	"""
	# Read the identifiers from an attribute series terminated with a name.
	"""
	while isinstance(node, ast.Attribute):
		yield node.attr
		node = node.value

	if not isinstance(node, ast.Name):
		raise ValueError("attributes series did not finish with a name")

	yield node.id

def _read_expression(context, i):
	f = Fragment(context, None, i)
	return {'syntax': f.syntax(), 'area': f.area}

def _read_data_iterable(context, i):
	values = []

	for x in i:
		if x.__class__ not in Constants:
			values.append(_read_expression(context, x))
		else:
			f = Constants[x.__class__](context, x)
			values.append(f)

	return values

Constants = {
	# ast.Constant is the node used by 3.8;
	# the others are slated for deprecation.
	getattr(ast, 'NameConstant', None): (lambda y,x: x.value),
	getattr(ast, 'Num', None): (lambda y,x: x.n),
	getattr(ast, 'Str', None): (lambda y,x: x.s),
	getattr(ast, 'Bytes', None): (lambda y,x: repr(x.s)),
	getattr(ast, 'Constant', None): (lambda y,x: x.value),

	ast.Tuple: (lambda y,x: tuple(_read_data_iterable(y,x.elts))),
	ast.List: (lambda y,x: _read_data_iterable(y,x.elts)),
}

def read_constants(ctx, v):
	"""
	# Retrieve the constants from the expression.
	# Expressions within &v that are not simple containers are
	# handled by referring to the source.

	# [ Parameters ]
	# /ctx/
		# The node fragment containing the expression, &v.
	# /v/
		# Expression.
	"""
	return Constants.get(v.__class__, _read_expression)(ctx, v)

class Fragment(object):
	"""
	# Expression container providing higher-level access to the properties of a node
	# with respect to that node's context path.
	"""

	_method_types = {'property', 'staticmethod', 'classmethod'}
	_type_map = {
		ast.Module: 'module',
		ast.FunctionDef: 'function',
		ast.ClassDef: 'class',
		ast.Lambda: 'lambda',
		ast.Import: 'import',
		ast.ImportFrom: 'import-from',
		ast.Assign: 'data',
		ast.AnnAssign: 'data',
		getattr(ast, 'AsyncFunctionDef', None): 'function',
		None: None,
	}

	def async_def(self,
		Type=getattr(ast, 'AsyncFunctionDef', (None).__class__)
	):
		assert self.node is not None
		return isinstance(self.node, Type)

	@cachedcalls(16)
	def decorator_names(self) -> typing.List[str]:
		"""
		# Get decorators from the node's (id)`decorator_list` field that
		# are simple names.
		"""
		return [
			x.id for x in getattr(self.node, 'decorator_list', ())
			if isinstance(x, ast.Name)
		]

	def qualifiers(self):
		ql = self.decorator_names()

		# Filter qualifiers that are absorbed by the element type.
		ql = [x for x in ql if x not in self._method_types]
		if self.async_def():
			ql.append('async')

		return ql

	@property
	@cachedcalls(16)
	def abstract_type(self):
		n = self._type_map.get(self.node.__class__, None)
		if n == 'function' and self.ancestor.abstract_type == 'class':
			n = 'method'
			for q in self.decorator_names():
				if q in self._method_types:
					n = q
					break
		return n

	def __init__(self, context, identifier:str, node:ast.AST):
		self.context = context
		self.identifier = identifier
		self.node = node
		self._init()

	def _init(self):
		sl, sc, el, ec = self.node._f_area

		ctx = getattr(self.node, '_f_context', None)
		if ctx is not None:
			sl, sc = ctx[0][:2]

		# Convert offsets; syntax.Area uses column-0 as an end of line reference.
		src = self.source()
		self.area = syntax.Area.delineate(
			sl, sc+1, el, ec,
			len(src[el-1]) if src else 0
		)

	@functools.lru_cache(16)
	def source(self):
		"""
		# Access the source lines from the root Fragment containing the module.
		"""

		f = self.context
		while isinstance(f, Fragment):
			f = f.context
		return f

	@property
	def ancestor(self):
		"""
		# Retrieve the named ancestor of the fragment.
		"""
		f = self.context

		while isinstance(f, Fragment):
			if f.identifier is not None:
				return f
			f = f.context

		return None

	@property
	@functools.lru_cache(32)
	def path(self):
		"""
		# Construct a fragment path to the node using &ancestor.
		"""
		points = []

		f = self
		while f.abstract_type != 'module':
			points.append(f.identifier)
			f = f.ancestor

		return tuple(reversed(points))

	def select(self):
		"""
		# Select the node's syntax from the reference's &source.
		"""

		return self.area.select(self.source())

	def syntax(self):
		src = self.select()[-1]
		src = b''.join(src)
		return src.decode('utf-8')

	def subnode(self, node, identifier):
		"""
		# Create a fragment using &self as the new fragment's context.
		"""
		return self.__class__(self, identifier, node)

	def descend(self):
		"""
		# Iterate over the nodes contained within the body of this fragment
		# and yield &Fragment instances.
		"""

		Class = self.__class__
		for x in getattr(self.node, 'body', ()) or ():
			yield Class(self, getattr(x, 'Identifier', None), x)

	def __repr__(self):
		src = self.source()
		prefix, suffix, lines = self.area.select(src)
		return "<%s: %r>" %(self.abstract_type, b''.join(lines),)

	def read_assign(self):
		"""
		# Retrieve the area and value of an assignment expression along with its name.
		"""

		axpr = self.node
		name = axpr.targets[0].id
		v = axpr.value

		return (name, read_constants(self, v))

	def read_ann_assign(self):
		"""
		# Retrieve the area and value of an assignment expression along with its name.
		"""

		axpr = self.node
		name = axpr.target.id
		v = axpr.value

		return (name, read_constants(self, v))

	def read_docstring(self):
		"""
		# Retrieve the normalized string contents of the first expression in &node.
		"""

		doc = None
		try:
			for sub in self.descend():
				if isinstance(sub.node, ast.Expr):
					# Maybe documentation string.
					fields = dict(ast.iter_fields(sub.node))
					astr = fields.get('value')

					if isinstance(astr, ast.Str):
						doc = comments.normalize_documentation(astr.s.split('\n'))
				break
			else:
				sub = None
		except TypeError:
			pass

		return (sub, doc)

class Switch(comethod.object):
	"""
	# Extraction selector state.
	"""

	def text(self, data):
		yield str(data)

	def element(self, identifier, nodes, *args, **kw):
		kw.update(args)

		for k in list(kw):
			if kw[k] is None:
				del kw[k]

		yield (identifier, list(nodes), kw)

	def attributes(self, fragment):
		docarea = None
		docexpr, doc = fragment.read_docstring()

		docd = (docexpr is not None)
		if docd:
			self.documentation[fragment.path] = doc
			docarea = docexpr.area

		return [
			('identifier', fragment.identifier),
			('area', fragment.area),
			('documented', docarea),
		]

	def param_attributes(self, fragment):
		return [
			('identifier', fragment.identifier),
			('area', fragment.area),
		]

	def annotation_type(self, fragment):
		"""
		# Construct an element type node from the annotation of the &fragment.
		"""
		ann = fragment.node.annotation
		f = fragment.subnode(ann, None)
		syntax = f.syntax().lstrip(":").rstrip(",")

		# If it's a simple name or attribute series, provide a reference attribute.
		try:
			ids = list(read_name(f.node))
			name = '.'.join(reversed(ids)) or None
		except ValueError:
			name = None

		return self.element('type',
			[],
			*self.attributes(f),
			syntax = syntax,
			reference = name
		)

	@comethod('data')
	def extract_assignment(self, fragment):
		if fragment.ancestor.abstract_type not in {'module', 'class'}:
			# Restrict to module/class entries.
			return ()

		try:
			dtype = self.annotation_type(fragment)
			name, constant = fragment.read_ann_assign()
		except AttributeError:
			dtype = ()
			try:
				name, constant = fragment.read_assign()
			except AttributeError:
				return ()

		fragment.identifier = name
		self.data[fragment.path] = constant

		return self.element('data',
			dtype,
			('identifier', name),
			('area', fragment.area),
		)

	@comethod('property')
	def extract_property(self, fragment):
		return self.element('property',
			self.effects(fragment),
			*self.attributes(fragment)
		)

	def annotate(self, fragment):
		if fragment.node.annotation is None:
			return ()
		return self.annotation_type(fragment)

	def parameters_v1(self, fragment):
		args = fragment.node.args
		required_count = len(args.args) - len(args.defaults)

		for a in args.args[0:required_count]:
			f = fragment.subnode(a, a.arg)
			yield from self.element('parameter',
				self.annotate(f),
				*self.param_attributes(f),
			)

		if args.vararg:
			f = fragment.subnode(args.vararg, args.vararg.arg)

			yield from self.element('vector',
				self.annotate(f),
				*self.param_attributes(fragment.subnode(args.vararg, args.vararg.arg)),
				syntax="*"+args.vararg.arg
			)

		for kw, kwd in zip(args.args[required_count:], args.defaults):
			f = fragment.subnode(kw, kw.arg)
			yield from self.element('option',
				self.annotate(f),
				*self.param_attributes(f),
			)

		for kw, kwd in zip(args.kwonlyargs, args.kw_defaults):
			f = fragment.subnode(kw, kw.arg)
			yield from self.element('option',
				self.annotate(f),
				*self.param_attributes(f),
			)

		if args.kwarg:
			f = fragment.subnode(args.kwarg, args.kwarg.arg)

			yield from self.element('map',
				self.annotate(f),
				*self.param_attributes(f),
				syntax="**"+args.kwarg.arg
			)

	def effects(self, fragment):
		rtype = fragment.node.returns

		if rtype is not None:
			rtype = fragment.subnode(rtype, None)
			yield from self.element('type',
				[],
				('syntax', rtype.syntax())
			)

	def signature(self, fragment):
		yield from self.effects(fragment)
		yield from self.parameters_v1(fragment)

	@comethod('function')
	@comethod('method')
	@comethod('classmethod')
	@comethod('staticmethod')
	def extract_function(self, fragment):
		return self.element(fragment.abstract_type,
			self.signature(fragment),
			*self.attributes(fragment),
			qualifiers=(fragment.qualifiers() or None)
		)

	@comethod('module')
	def extract_module_content(self, fragment):
		return self.element('module',
			self.descend(fragment),
			*self.attributes(fragment)
		)

	@comethod('import')
	def extract_import(self, fragment, prefix=None, depth=None):
		isnode = fragment.node

		for isname in isnode.names:
			# Potentially multiple import elements for each statement.
			# import a as x, b as y

			if isname.asname is not None:
				# Element identifier is the target name.
				import_id = isname.asname
				offset = import_id.find('.')
				if offset > -1:
					path = import_id.split('.')
					import_id = import_id[:offset]
				else:
					path = [import_id]
			else:
				# Otherwise, element identifier is the *first* field.
				import_id, *path = isname.name.split('.')
				path.insert(0, import_id)

			yield from self.element('import',
				(),
				('identifier', import_id),
				path = prefix + path if prefix else path,
				area = fragment.area,
				relative = depth,
			)

	@comethod('import-from')
	def extract_import_from(self, fragment):
		isnode = fragment.node

		prefix = []
		if isnode.module:
			prefix.extend(isnode.module.split('.'))

		return self.extract_import(fragment, prefix=prefix, depth=isnode.level)

	@comethod('class')
	def extract_class(self, fragment):
		return self.element('class',
			self.descend(fragment),
			*self.attributes(fragment)
		)

	@comethod(None)
	def unknown(self, fragment):
		return ()

	def descend(self, fragment):
		for f in fragment.descend():
			yield from self.comethod(f.abstract_type)(f)

	def __init__(self):
		self.documentation = {}
		self.data = {}

def load(source_path:str, identifier=None):
	with open(source_path) as f:
		python_source = f.read()

	srclines, tree, prepared = source.parse(python_source, source_path)
	for snode, node, field, index in prepared:
		node.Identifier = getattr(node, 'name', None)

	if srclines:
		l = len(srclines[-1])
	else:
		l = 0

	tree._f_area = (1, 0, len(srclines)-1, l)
	root = Fragment(srclines, identifier, tree)

	return root

def main(inv:process.Invocation) -> process.Exit:
	import json
	target, source, *defines = inv.args # (output-directory, source-file-path)
	root = load(source, source)

	s = Switch()
	x, = s.comethod('module')(root)
	x[2]['source-encoding'] = 'utf-8'

	r = files.Path.from_path(target)
	r.fs_mkdir()

	with (r/"elements.json").fs_open('w') as f:
		json.dump(x, f)

	keys = []
	docs = []
	for k, v in s.documentation.items():
		if v is None:
			continue
		keys.append(k)
		docs.append(v)

	with (r/"documented.json").fs_open('w') as f:
		json.dump(keys, f)

	with (r/"documentation.json").fs_open('w') as f:
		json.dump(docs, f)

	keys = []
	data = []
	for k, v in s.data.items():
		if v is None:
			continue
		keys.append([x for x in k if x is not None])
		data.append(v)
	with (r/"data.json").fs_open('w') as f:
		json.dump([keys, data], f)

	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
