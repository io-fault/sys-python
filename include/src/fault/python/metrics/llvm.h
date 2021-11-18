/**
	// Python module level controls of LLVM coverage and profile data.
*/
void __llvm_profile_write_file(void);
void __llvm_profile_reset_counters(void);
void __llvm_profile_set_filename(const char *);

static PyObj _fault_metrics_flush(PyObj self) { __llvm_profile_write_file(); Py_RETURN_NONE; }
static PyObj _fault_metrics_clear(PyObj self) { __llvm_profile_reset_counters(); Py_RETURN_NONE; }

static PyObj _fault_metrics_file(PyObj self, PyObj filepath)
{
	static char ifbuf[2048] = {0,}; /* buf must be valid after exit */

	PyObj bytes;
	bytes = PyUnicode_EncodeFSDefault(filepath);
	if (bytes == NULL)
		return(NULL);

	if (PyBytes_GET_SIZE(bytes) < 2048)
	{
		memcpy(ifbuf, PyBytes_AS_STRING(bytes), PyBytes_GET_SIZE(bytes));
		ifbuf[PyBytes_GET_SIZE(bytes)] = 0;
		__llvm_profile_set_filename(ifbuf);
	}

	Py_DECREF(bytes);
	Py_RETURN_NONE;
}

#define FAULT_MODULE_FUNCTIONS() \
	PYMETHOD(_fault_metrics_set_path, _fault_metrics_file, METH_O, NULL) \
	PYMETHOD(_fault_metrics_write, _fault_metrics_flush, METH_NOARGS, NULL) \
	PYMETHOD(_fault_metrics_reset, _fault_metrics_clear, METH_NOARGS, NULL)
