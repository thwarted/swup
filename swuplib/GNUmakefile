include ../GNUmakefile.inc
.PHONY: all clean install
SUBDIRS = driver

all:

install:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done
	install -d -m 0755 $(DESTDIR)/$(SITEDIR)
	install -c -m 0644 *.py $(DESTDIR)/$(SITEDIR)

uninstall:
	-rm -rf $(DESTDIR)/$(SITEDIR)

clean:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done
	-rm -f *.pyc

        

