/**
	# Inline functions supporting Python [executable] bindings.
*/

/**
	# Create a &fault.system.process.Invocation instance from the system process.
	# Used by bindings calling explicit entry points.
*/
static PyObject *
_fault_system_invocation(PyObject **process_module)
{
	PyObject *mod, *ic, *inv;

	mod = PyImport_ImportModule(FAULT_CONTEXT_NAME ".system.process");
	if (mod == NULL)
		return(NULL);

	ic = PyObject_GetAttrString(mod, "Invocation");
	if (ic == NULL)
	{
		Py_DECREF(mod);
		return(NULL);
	}

	inv = PyObject_CallMethod(ic, "system", "");
	Py_DECREF(ic);
	if (inv == NULL)
		Py_DECREF(mod);

	*process_module = mod;
	return(inv);
}
