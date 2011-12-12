include ../GNUmakefile.inc
.PHONY: clean all install

all:

install:
	install -d -m 0755 $(DESTDIR)/$(BINDIR)
	install -d -m 0755 $(DESTDIR)/$(SLIBDIR)
	install -c -m 0644 *.py $(DESTDIR)/$(SLIBDIR)
	install -c -m 0755 swup $(DESTDIR)/$(BINDIR)

uninstall:
	-rm -f $(DESTDIR)/$(BINDIR)/swup
	-rm -rf $(DESTDIR)/$(SLIBDIR)

clean:
	-rm -f *.pyc

