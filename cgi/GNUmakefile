include ../GNUmakefile.inc
.PHONY: clean all install

all:

install:
	install -d -m 0755 $(DESTDIR)/$(CGIHOMEDIR)
	install -d -m 0755 $(DESTDIR)/$(CGIWEBDIR)
	install -d -m 0755 $(DESTDIR)/$(CGIBINDIR)
	install -d -m 0755 $(DESTDIR)/$(HTTPDCONFDIR)
	install -c -m 0755 swup_query.py $(DESTDIR)/$(CGIBINDIR)/
	install -c -m 0644 swup_query_config.py $(DESTDIR)/$(CGIBINDIR)/
	install -c -m 0644 swup_query.conf $(DESTDIR)/$(HTTPDCONFDIR)/

uninstall:
	-rm -f $(DESTDIR)/$(CGIHOMEDIR)/
	-rm $(DESTDIR)/$(HTTPDCONFDIR)/swup_query.conf

clean:
	-rm -f *.pyc

