include ../GNUmakefile.inc
.PHONY: all clean install
all:

install:
	install -d -m 0755 $(DESTDIR)/$(BINDIR)
	install -d -m 0755 $(DESTDIR)/$(RLIBDIR)
	install -c -m 0644 *.py $(DESTDIR)/$(RLIBDIR)
	install -c -m 0755 rdfgen $(DESTDIR)/$(BINDIR)

uninstall:
	-rm -f $(DESTDIR)/$(BINDIR)/rdfgen
	-rm -rf $(DESTDIR)/$(RLIBDIR)
clean:
	-rm -f *.pyc

