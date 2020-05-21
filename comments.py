"""
# Functions for cleaning comments.
"""

def remove_common_indentation(lines):
	"""
	# Remove the leading indentation level from the given lines.
	"""

	# first non-empty line is used to identify
	# the indentation level of the entire string.
	for fl in lines:
		if fl.strip():
			break

	if fl.startswith('\t'):
		indentation = len(fl) - len(fl.lstrip('\t'))
		return [x[indentation:] for x in lines]
	else:
		# presume no indentation and likely single line
		return lines

def strip_notation_prefix(lines, prefix='# '):
	"""
	# Remove the comment notation prefix from a sequence of lines.
	"""

	pl = len(prefix)
	return [
		(('\t'*(xl-len(y))) + y[pl:] if y[:pl] == prefix else x)
		for xl, x, y in [
			(len(z), z, z.lstrip('\t'))
			for z in lines
		]
	]

def normalize_documentation(lines, prefix='# '):
	"""
	# Remove the leading indentation level from the given lines.
	"""

	# first non-empty line is used to identify
	# the indentation level of the entire string.
	for fl in lines:
		if fl.strip():
			break

	if fl.startswith('\t'):
		indentation = len(fl) - len(fl.lstrip('\t'))
		plines = strip_notation_prefix([x[indentation:] for x in lines], prefix=prefix)
	else:
		# assume no indentation and likely single line
		plines = strip_notation_prefix(lines, prefix=prefix)

	while plines[:1] == ['']:
		del plines[:1]

	while plines[-1:] == ['']:
		del plines[-1:]

	return plines
