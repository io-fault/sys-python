/**
	// Included once by the source file defining module initialization.
*/
#include "fault/symbols.h"

#define FAULT_MODULE_FUNCTIONS() \
	FAULT_METRICS_FUNCTIONS()

#ifndef MODULE_FUNCTIONS
	#error MODULE_FUNCTIONS() macro with PyMethodDef entries not defined.
#endif

#define FAULT_METRICS_FUNCTIONS()
#if FV_COVERAGE()
	#if __clang__
		#undef FAULT_METRICS_FUNCTIONS
		#include "metrics/llvm.h"
	#else
		#warning Module-level metrics controls will not be available.
	#endif
#endif

#if FV_INJECTIONS()
	#define DEFINE_MODULE_GLOBALS \
		PyObj __ERRNO_RECEPTACLE__; \
		PyObj __PYTHON_RECEPTACLE__; \
		PyObj __dict__ = NULL;

	#define DROP_MODULE_GLOBALS() do { \
			Py_XDECREF(__ERRNO_RECEPTACLE__); \
			Py_XDECREF(__PYTHON_RECEPTACLE__); \
			__ERRNO_RECEPTACLE__ = NULL; \
			__PYTHON_RECEPTACLE__ = NULL; \
		} while(0)

	#define INIT_MODULE_GLOBALS(MODULE) \
		__ERRNO_RECEPTACLE__ = PyDict_New(); \
		__PYTHON_RECEPTACLE__ = PyDict_New(); \
		if (PyErr_Occurred()) { \
			DROP_MODULE_GLOBALS(); \
		} else { \
			PyModule_AddObject(MODULE, "__ERRNO_RECEPTACLE__", __ERRNO_RECEPTACLE__); \
			PyModule_AddObject(MODULE, "__PYTHON_RECEPTACLE__", __PYTHON_RECEPTACLE__); \
		}
#else
	#define DEFINE_MODULE_GLOBALS
	#define INIT_MODULE_GLOBALS(MODULE) do {} while(0)
	#define DROP_MODULE_GLOBALS() do {} while(0)
#endif

#define _py_INIT_FUNC_X(BN) CONCAT_IDENTIFIER(PyInit_, BN)
#define _py_INIT_FUNC _py_INIT_FUNC_X(F_FACTOR_NAME)

#if PY_MAJOR_VERSION < 3
#define _py_INIT_COMPAT CONCAT_IDENTIFIER(init, F_FACTOR_NAME)

/**
	// Invoke the new signature.
	// Allows the user to return(NULL) regardless of Python version.
*/
#define INIT(MODPARAM, STATE_SIZE, DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
	static PyMethodDef methods[] = { \
		FAULT_MODULE_FUNCTIONS() \
		MODULE_FUNCTIONS() \
		{NULL,} \
	}; \
	static PyObject * _py_INIT_FUNC(void); \
	_fault_reveal_symbol PyMODINIT_FUNC _py_INIT_COMPAT(void) \
	{ \
		PyObj _MOD = Py_InitModule(PYTHON_MODULE_PATH_STR, methods); \
		if (_MOD) { \
			__dict__ = PyModule_GetDict(_MOD); \
			if (__dict__ == NULL) { Py_DECREF(_MOD); return(-1); } \
			INIT_MODULE_GLOBALS(MODPARAM); \
			if (PyErr_Occurred()) { Py_DECREF(_MOD); return(-1); } \
			else { \
				if (_py_INIT_FUNC(_MOD) != 0) \
				{ \
					Py_DECREF(_MOD); \
					return(NULL); \
				} \
			} \
		} \
	} \
	static int _py_INIT_FUNC(PyObj MODPARAM)

#elif !defined(Py_mod_exec)

/*
	// Python 3.x without mod_exec
*/
#define INIT(MODPARAM, STATE_SIZE, DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
	static PyMethodDef methods[] = { \
		FAULT_MODULE_FUNCTIONS() \
		MODULE_FUNCTIONS() \
		{NULL,} \
	}; \
	\
	static struct PyModuleDef \
	module_definition = { \
		PyModuleDef_HEAD_INIT, \
		PYTHON_MODULE_PATH_STR, \
		DOCUMENTATION, \
		STATE_SIZE, \
		methods, \
		NULL, \
	}; \
	\
	static int _module_exec(PyObj MODPARAM); \
	_fault_reveal_symbol PyMODINIT_FUNC \
	_py_INIT_FUNC(void) \
	{ \
		PyObj m = NULL; \
		_CREATE_MODULE(&m); \
		if (m == NULL) return(NULL); \
		if (_module_exec(m) != 0) \
		{ \
			Py_DECREF(m); \
			return(NULL); \
		} \
		return(m); \
	} \
	static int _module_exec(PyObj MODPARAM)

#define _CREATE_MODULE(MOD) \
do { \
	PyObj _MOD = PyModule_Create(&module_definition); \
	if (_MOD == NULL) \
		*MOD = NULL; /* error */ \
	else \
	{ \
		__dict__ = PyModule_GetDict(_MOD); \
		if (__dict__ == NULL) \
		{ \
			Py_DECREF(_MOD); \
			*MOD = NULL; \
		} \
		else \
		{ \
			INIT_MODULE_GLOBALS(_MOD); \
			if (PyErr_Occurred()) \
			{ \
				Py_DECREF(_MOD); \
				*MOD = NULL; \
			} \
			else \
			{ \
				*MOD = _MOD; \
			} \
		} \
	} \
} while(0)

#else

/*
	// Multi-phase Initialization
*/
#define INIT(MODPARAM, STATE_SIZE, DOCUMENTATION) \
	DEFINE_MODULE_GLOBALS \
	static PyMethodDef methods[] = { \
		FAULT_MODULE_FUNCTIONS() \
		MODULE_FUNCTIONS() \
		{NULL,} \
	}; \
	\
	static int _module_exec(PyObj); \
	static int module_exec(PyObj MODPARAM) \
	{ \
		INIT_MODULE_GLOBALS(MODPARAM); \
		return _module_exec(MODPARAM); \
	} \
	static PyModuleDef_Slot module_slots[] = { \
		{Py_mod_exec, module_exec}, \
		{0, NULL} \
	}; \
	\
	static struct PyModuleDef \
	module_definition = { \
		PyModuleDef_HEAD_INIT, \
		PYTHON_MODULE_PATH_STR, \
		DOCUMENTATION, \
		STATE_SIZE, \
		methods, \
		module_slots, \
		NULL, \
		NULL, \
		NULL, \
	}; \
	\
	_fault_reveal_symbol PyMODINIT_FUNC \
	_py_INIT_FUNC(void) { \
		return(PyModuleDef_Init(&module_definition)); \
	} \
	static int _module_exec(PyObj MODPARAM)
#endif
