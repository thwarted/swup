include ../../GNUmakefile.inc
.PHONY: all install clean

all:

install:
	install -d -m 0755 $(DESTDIR)/$(SITEDIR)/driver
	install -c -m 0644 *.py $(DESTDIR)/$(SITEDIR)/driver

clean:
	-rm -f *.pyc
