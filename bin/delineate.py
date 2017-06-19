"""
# Delineate a Python module.

# Emits serialized Fragments to standard out of the selected Python module.
"""

import sys
from ...system import libfactor
from ...system import library as libsys
from ...routes import library as libroutes
from .. import xml

def main(inv:libsys.Invocation):
	module_fullname, = inv.args

	r = libroutes.Import.from_fullname(module_fullname)
	w = sys.stdout.buffer.write
	wl = sys.stdout.buffer.writelines

	w(b'<?xml version="1.0" encoding="utf-8"?>')
	ctx = xml.Context(r)
	module = r.module()
	module.__factor_composite__ = libfactor.composite(r)

	i = ctx.serialize(module)
	wl(i)
	sys.stdout.flush()
	sys.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
