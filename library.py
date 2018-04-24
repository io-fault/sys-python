"""
# Support for Python coverage tooling suitable for fault metrics contexts.
"""
import contextlib
import collections
import pickle
import itertools

from ...factors import metrics

from . import trace
from . import instrumentation
from . import source

class Probe(metrics.Probe):
	def project(self, telemetry, route, frames):
		"""
		# Identify counters in the Python factor sources.
		"""
		data = collections.defaultdict(dict)

		for factor, pyc in frames.items():
			src = str(pyc[-1][0])
			with open(src) as f:
				tree, nodes = source.parse(f.read(), src, filter=instrumentation.visit)

			selector = ((node, instrumentation.delineate(node)) for node in nodes)
			data[src] = {
				(addr[0], addr[1]+1, addr[2], addr[3]+1): (
					(addr[0], addr[1]+1, addr[2], addr[3]+1),
					node[0].__class__.__name__
					if not isinstance(node[0], (source.ast.Str, source.ast.Name))
					else '%s[%s]' %(
						node[1].__class__.__name__,
						node[0].__class__.__name__,
					)
				)
				for node, addr in selector
				if addr is not None
			}

		return data

	@contextlib.contextmanager
	def setup(self, context, telemetry, data):
		"""
		# Install the meta path hook for loading instrumented bytecode.
		"""

		try:
			yield None
		finally:
			pass

	@contextlib.contextmanager
	def connect(self, harness, measures):
		"""
		# Construct a trace and subscribe to interpreter events
		# for the duration of the test. Profile and coverage information
		# is emitted as a pickle file relative to &measures.
		"""

		try:
			yield None
		finally:
			pass

			m = measures / self.name / 'profile.pickle'
			with m.open('wb') as f:
				pickle.dump({}, f)

			try:
				from f_telemetry.python import instrumentation as python_tm
				m = measures / self.name / 'coverage.pickle'
				data = collections.defaultdict(collections.Counter)
				for counter in python_tm.counters.items():
					(path, address), count = counter
					sl, sc, el, ec = address
					data[path][(sl,sc+1,el,ec+1)] = count

				with m.open('wb') as f:
					pickle.dump(data, f)
			except ImportError:
				raise

	@staticmethod
	def abstract_call_selector(call):
		path, line, symbol = call
		if symbol[0:1] + symbol[-1:] == '<>':
			lambda_type = symbol.strip('<>')
			if lambda_type == 'lambda':
				lambda_type = 'function'
			symbol = None
		else:
			lambda_type = None

		return path, metrics.SymbolQualifiedLocator((line, line), symbol, lambda_type)

	def profile(self, factors, measures):
		data = collections.defaultdict(lambda: collections.defaultdict(list))
		for m_typ, m_id, m_route in measures:
			profile_data = m_route / self.name / 'profile.pickle'
			try:
				with profile_data.open('rb') as f:
					profile = pickle.load(f)
			except EOFError:
				continue

			for (caller, call), times in profile.items():
				path, sql = self.abstract_call_selector(call)
				if caller is not None:
					caller = self.abstract_call_selector(caller)
				data[path][(caller, (path, sql))].extend(times)

		yield from data.items()

	def counters(self, factors, measures):
		for m_typ, m_id, m_route in measures:
			coverage_data = m_route / self.name / 'coverage.pickle'
			try:
				with coverage_data.open('rb') as f:
					coverage = pickle.load(f)
			except EOFError:
				# Likely empty file.
				continue

			for path, counters in coverage.items():
				yield path, [(k, v) for k,v in counters.items()]
