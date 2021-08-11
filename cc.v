#!/usr/bin/env fault-tool cc-adapter
##

[unit-suffix]:
	fv-form-delineated:
		# Delineation, no extension.
		: ""
	!:
		# Execution imaging.
		: ".ast"

[protocol]:
	: http://if.fault.io/project/integration.vectors

[factor-type]:
	: http://if.fault.io/factors/python

[integration-type]:
	: module
	: interface

-cpy-optimize:
	fv-intention-coverage:
		: 0
	fv-intention-debug:
		: 0
	fv-intention-profile:
		: 2
	fv-intention-optimal:
		: 2
	!: 1

-pyc-ast-1:
	: "interpret-ast" - -
	: [unit File]
	: [source File]
	fv-form-delineated:
		: delineated json
	: factor [factor-path]
	: format [language].[dialect]
	: intention [fv-intention]
	: cpython-optimize [-cpy-optimize]

-pyc-reduce-1:
	: "compile-bytecode" - -
	: [factor-image File]
	:
		fv-form-delineated:
			: [unit-directory File]
			: delineated archive
		!: [unit File]
	: format python.ast
	: intention [fv-intention]
