include ../../GNUmakefile.inc

#PYC = __init__.pyc rpmdriver.pyc


#%.pyc: %.py
#	../../utils/compile.py $^

all: #$(PYC)

install:
	install -d -m 0755 -o root -g root $(DESTDIR)/$(LIBDIR)/pkgdriver
	install -c -m 0644 -o root -g root *.py \
            $(DESTDIR)/$(LIBDIR)/pkgdriver

.PHONY: clean
clean:
	-rm *.pyc
