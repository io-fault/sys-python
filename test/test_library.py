"""
# Test library exports.
"""
from .. import library

def test_syntax(test):
	test/hasattr(library, 'syntax') == True

if __name__ == '__main__':
	import sys
	from ...development import libtest
	libtest.execute(sys.modules[__name__])
