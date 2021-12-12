/**
	// Python C-API extensions for compensating for older versions
	// and for providing additional utility.
*/
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <pythread.h>

#if __ALWAYS__()
	/**
		// Py_Is macros introduced in CPython 3.10.
	*/
	#ifndef Py_Is
		#define Py_Is(x, y) ((x) == (y))
	#endif

	#ifndef Py_IsNone
		#define Py_IsNone(ob) Py_Is(ob, Py_None)
	#endif

	#ifndef Py_IsFalse
		#define Py_IsFalse(ob) Py_Is(ob, Py_False)
	#endif

	#ifndef Py_IsTrue
		#define Py_IsTrue(ob) Py_Is(ob, Py_True)
	#endif
#endif

#if __ALWAYS__()
	/**
		// Method definition macros.
		// Documentation fields are inaccessible in anticipation of interface modules.
	*/
	#define PyMethod_InstanceType(X) X
	#define PyMethod_ClassType(X) METH_CLASS|X

	/* Default to instance methods */
	#define PyMethod_TypeControl PyMethod_InstanceType
	#define PyMethod_Define(CC, NAME) \
		{#NAME, (PyCFunction) PyMethod_Id(NAME), PyMethod_TypeControl(CC), NULL}

	#define PyMethod_Variable(NAME) PyMethod_Define(METH_VARARGS, NAME)
	#define PyMethod_Keywords(NAME) PyMethod_Define(METH_VARARGS|METH_KEYWORDS, NAME)
	#define PyMethod_None(NAME) PyMethod_Define(METH_NOARGS, NAME)
	#define PyMethod_Sole(NAME) PyMethod_Define(METH_O, NAME)
	#define PyMethod_Vector(NAME) PyMethod_Define(METH_FASTCALL, NAME)
#endif

#define T_KPORT T_INT
#define T_KERROR T_INT

#define PYTHON_MODULE_PATH_STR ( \
	STRING_FROM_IDENTIFIER(F_PROJECT_PATH) \
	"." STRING_FROM_IDENTIFIER(F_FACTOR_NAME))

#define PYTHON_MODULE_PATH(TAIL_STRING) ( \
	STRING_FROM_IDENTIFIER(F_PROJECT_PATH) \
	"." STRING_FROM_IDENTIFIER(F_FACTOR_NAME) "." TAIL_STRING)

typedef PyObject * PyObj;

#if FV_INJECTIONS()
	extern PyObj __ERRNO_RECEPTACLE__;
	extern PyObj __PYTHON_RECEPTACLE__;
#endif

#if __ALWAYS__(return-macros)
	#ifndef Py_RETURN_NONE
		#define Py_RETURN_NONE \
			do { Py_INCREF(Py_None); return(Py_None); } while(0)
	#endif

	#ifndef Py_RETURN_TRUE
		#define Py_RETURN_TRUE \
			do { Py_INCREF(Py_True); return(Py_True); } while(0)
	#endif

	#ifndef Py_RETURN_FALSE
		#define Py_RETURN_FALSE \
			do { Py_INCREF(Py_False); return(Py_False); } while(0)
	#endif

	#ifndef Py_RETURN_INTEGER
		#define Py_RETURN_INTEGER(N) \
			do { return(PyLong_FromLong(N)); } while(0)
	#endif

	#ifndef Py_RETURN_NOTIMPLEMENTED
		#define Py_RETURN_NOTIMPLEMENTED \
			do { Py_INCREF(Py_NotImplemented); return(Py_NotImplemented); } while(0)
	#endif
#endif

#define PyAllocate(TYP) (((PyTypeObject *) TYP)->tp_alloc((PyTypeObject *) TYP, 0))

#define PYMETHOD(name, func, args, doc) {#name, (PyCFunction) func, args, PyDoc_STR(doc)},

static inline PyObj
_PyLoop_DictionaryItems(PyObj d)
{
	PyObj iterable, iterator;
	iterable = PyDict_Items(d);
	iterator = PyObject_GetIter(iterable);
	Py_DECREF(iterable);
	return(iterator);
}

static inline PyObj
PyImport_ImportAdjacentEx(PyObj module, const char *modname, const char *attribute)
{
	PyObj is_m, is_ob, is_fromlist;

	is_fromlist = Py_BuildValue("(s)", attribute);
	if (is_fromlist == NULL)
		return(NULL);

	is_m = PyImport_ImportModuleLevel(modname,
		PyModule_GetDict(module), PyModule_GetDict(module),
		is_fromlist, 1);

	Py_DECREF(is_fromlist);
	if (is_m == NULL)
		return(NULL);

	is_ob = PyObject_GetAttrString(is_m, attribute);
	Py_DECREF(is_m);

	return(is_ob);
}

static inline PyObj
PyImport_ImportAdjacent(const char *modname, const char *attribute)
{
	PyObj ia_module = PyImport_ImportModule(PYTHON_MODULE_PATH_STR);
	if (ia_module == NULL)
		return(NULL);

	return(PyImport_ImportAdjacentEx(ia_module, modname, attribute));
}

#define _PyLoop_NULL_INJECTION() ;
#define PyLoop_ITEM _ITEM
#define _PyLoop_Error(ITER) goto _PYERR_LABEL_##ITER
#define _PyLoop_PassThrough(ITEM, OUTPUT, ...) ((*(OUTPUT) = ITEM) ? NULL : NULL)
#define _PyLoop_ConvertLong(ITEM, OUTPUT, ...) ((*(OUTPUT) = PyLong_AsLong(ITEM)) == -1 ? -1 : 0)
#define _PyLoop_ConvertLongFailure -1 && (PyErr_Occurred() != NULL)

#define _PyLoop_Iterator(INJECTION, _CONVERT_SUCCESS, _CONVERT, GETITER, ITER, ...) \
{ \
	PyObj _ITER = NULL; \
	PyObj _PyLoop_ITEM = NULL; \
	\
	INJECTION() \
	\
	_ITER = GETITER(ITER); \
	if (_ITER == NULL) \
		_PyLoop_Error(ITER); \
	else \
	{ \
		while ((_PyLoop_ITEM = PyIter_Next(_ITER)) != NULL) \
		{ \
			if (_CONVERT(_PyLoop_ITEM, __VA_ARGS__) != _CONVERT_SUCCESS) \
			{ \
				Py_XDECREF(_PyLoop_ITEM); \
				_PyLoop_ITEM = NULL; \
				Py_XDECREF(_ITER); \
				_ITER = NULL; \
				_PyLoop_Error(ITER); \
			} \


			#define PyLoop_CatchError(ITER) \
			Py_DECREF(_PyLoop_ITEM); \
		} \
		\
		Py_XDECREF(_PyLoop_ITEM); \
		_PyLoop_ITEM = NULL; \
		Py_XDECREF(_ITER); \
		_ITER = NULL; \
	} \
	\
	if (PyErr_Occurred()) \
	{ \
		_PYERR_LABEL_##ITER: \


		#define PyLoop_End(ITER) \
	} \
}

#define PyLoop_ForEachTuple(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 1, PyArg_ParseTuple, PyObject_GetIter, ITER, __VA_ARGS__)
#define PyLoop_ForEachDictItem(DICT, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 1, PyArg_ParseTuple, _PyLoop_DictionaryItems, DICT, __VA_ARGS__)
#define PyLoop_ForEachLong(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, _PyLoop_ConvertLongFailure, _PyLoop_ConvertLong, PyObject_GetIter, ITER, __VA_ARGS__)

/*
	// For Each item in iterator loop with no conversion.
	PyLoop_ForEach(iter, &obj)
	{
	    ...
	}
	PyLoop_CatchError(iter)
	{
	    ...
	}
	PyLoop_End(iter)
*/
#define PyLoop_ForEach(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, NULL, _PyLoop_PassThrough, PyObject_GetIter, ITER, __VA_ARGS__)
