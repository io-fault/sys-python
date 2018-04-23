"""
# Python bytecode serialization.
"""
import types
import importlib

def serialize(code, time, size):
	"""
	# Serialize the given &code object for filesystem storage into a &bytes instance.
	"""
	return importlib._bootstrap_external._code_to_bytecode(code, time, size)

def store(target:str, code:types.CodeType, time:int, size:int) -> types.CodeType:
	"""
	# Store the given &code object at the &target location system path.
	# The stored data should be suitable for use as a `.pyc` file within __pycache__.

	# [ Parameters ]
	# /time
		# Modification time of the corresponding source file.
	# /size
		# The size of the corresponding source file.
	"""

	data = serialize(code, time, size)
	with open(str(target), 'wb') as f:
		f.write(data)

	return code
