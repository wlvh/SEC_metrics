import importlib.util,sys,unittest,json
spec=importlib.util.spec_from_file_location('rft','tools/run_fast_tests.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
names=list(m.FAST_TESTS); bad=[]
for n in names:
    try:
        s=unittest.defaultTestLoader.loadTestsFromName(n)
        def walk(x):
            for t in x:
                if isinstance(t,unittest.TestSuite): yield from walk(t)
                else: yield t
        for t in walk(s):
            if type(t).__name__=='_FailedTest': raise ImportError(str(t._exception)[:120])
    except Exception as e: bad.append((n,type(e).__name__,str(e)[:120]))
print(json.dumps({'selected':len(names),'load_failures':len(bad),'failures':bad[:40]},indent=1))
