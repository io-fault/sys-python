#!/usr/bin/env fault-tool cc-adapter
##

[unit-suffix]:
	fv-idelineation: ""
	fv-ianalysis: ""
	!: ".ast"

[protocol]:
	: http://if.fault.io/project/integration.vectors

[factor-type]:
	: http://if.fault.io/factors/python

[integration-type]:
	: module
	: interface

-pyc-ast-1:
	: "interpret-ast" - -
	: [unit File]
	: [source File]
	: format [language].[dialect]
	: intention [fv-intention]

-pyc-bytecode-1:
	: "compile-bytecode" - -
	: [factor-image File]
	: [unit File]
	: format python.ast
	: intention [fv-intention]
