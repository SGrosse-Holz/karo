TESTDIR = tests
TESTFILE = test_karo.py
COVERAGEREPDIR = tests/coverage
MODULE = karo

.PHONY : tests all clean mytests myall myclean

all : tests

tests :
	cd $(TESTDIR) && coverage run $(TESTFILE)
	@mv $(TESTDIR)/.coverage .
	coverage html -d $(COVERAGEREPDIR)

clean :
	-rm -r $(COVERAGEREPDIR)/*
	-rm .coverage

# Personal convenience targets
DUMPPATH = "/home/simongh/Dropbox (MIT)/htmldump"

mytests : tests
	cp -r $(COVERAGEREPDIR)/* $(DUMPPATH)/coverage

myall : mytests

myclean : clean
	-rm -r $(DUMPPATH)/coverage/*
