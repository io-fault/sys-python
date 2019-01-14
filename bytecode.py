"""
# Python bytecode serialization.

# This supports modification time based pycs and hash based introduced in 3.7.

# [ Engineering ]

# Unstable API. This module may be partitioned in order to eliminate the conditions.
"""
import os
import types
import importlib
import marshal

try:
	from _imp import source_hash
	from importlib._bootstrap_external import _RAW_MAGIC_NUMBER, _code_to_timestamp_pyc, _code_to_hash_pyc
	import functools
	local_source_hash = functools.partial(source_hash, _RAW_MAGIC_NUMBER)
except (NameError, ImportError):
	# Signals to force modification time based checks as cpython<=3.6
	local_source_hash = None
	from importlib._bootstrap_external import _code_to_bytecode as _code_to_timestamp_pyc
else:
	# Python 3.7 or greater.
	from importlib._bootstrap_external import _code_to_timestamp_pyc

serialize_timestamp_checked = _code_to_timestamp_pyc # Present regardless of version.

def store(check:str, target:str, code:types.CodeType, fileno:int, source:bytes) -> types.CodeType:
	"""
	# Store the given &code object at the &target location system path.
	# The stored data should be suitable for use as a pycs file within __pycache__.
	# [ Parameters ]
	# /check/
		# - `'never'`
		# - `'time'`
		# - `'hash'`
	"""

	method = None
	if 0:
		if check in {None, 'time'} or local_source_hash is None:
			stat = os.fstat(fileno)
			method = (stat.st_mtime, stat.st_size)
			data = serialize_timestamp_checked(code, *method)
		elif check == 'hash':
			method = local_source_hash(source)
			data = _code_to_hash_pyc(code, method)
		elif check == 'never':
			method = local_source_hash(source)
			data = _code_to_hash_pyc(code, method, checked=False)
	data = marshal.dumps(code)

	with open(str(target), 'wb') as f:
		f.write(data)

	return (method, code)
