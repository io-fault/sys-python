"""
# Support for Python coverage tooling suitable for fault metrics contexts.
"""
import contextlib
import collections
import pickle
import itertools

from fault.development import metrics

from . import syntax
from . import trace

class Probe(metrics.Probe):
	def project(self, telemetry, route, frames):
		"""
		# Identify traversable lines in the Python factor sources.
		"""
		data = collections.defaultdict(dict)

		for factor, pyc in frames.items():
			src = str(pyc[-1][0])
			traversable = syntax.apply(src, syntax.coverable)
			data[src] = {
				line: ((line, 1, line+1, 0), 'code')
				for line in traversable
			}

		return data

	@contextlib.contextmanager
	def setup(self, context, telemetry, data):
		"""
		# No-op context manager. Python requires no setup.
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

		traceref, events = trace.prepare()
		try:
			traceref.subscribe()
			yield None
		finally:
			traceref.cancel()

			# Extract measurements from the collected events
			# and record them into the measure directory..
			profile, coverage = trace.measure(events)
			m = measures / self.name / 'profile.pickle'
			with m.open('wb') as f:
				pickle.dump(profile, f)

			m = measures / self.name / 'coverage.pickle'
			with m.open('wb') as f:
				pickle.dump(coverage, f)

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

		la = metrics.libsyntax.Area.from_line_range((line, line))
		return path, metrics.SymbolQualifiedLocator(la, symbol, lambda_type)

	def profile(self, factors, measures):
		data = collections.defaultdict(lambda: collections.defaultdict(list))
		for m_typ, m_id, m_route in measures:
			profile_data = m_route / self.name / 'profile.pickle'
			with profile_data.open('rb') as f:
				profile = pickle.load(f)

			for (caller, call), times in profile.items():
				path, sql = self.abstract_call_selector(call)
				if caller is not None:
					caller = self.abstract_call_selector(caller)
				data[path][(caller, (path, sql))].extend(times)

		yield from data.items()

	def counters(self, factors, measures):
		for m_typ, m_id, m_route in measures:
			coverage_data = m_route / self.name / 'coverage.pickle'
			with coverage_data.open('rb') as f:
				coverage = pickle.load(f)

			for path, counters in coverage.items():
				yield path, list(counters.items())
