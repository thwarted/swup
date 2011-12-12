include ./GNUmakefile.inc
.PHONY: clean all install
SUBDIRS = swup rdfgen etc man swuplib cgi

all:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

install:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

uninstall:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

clean:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done


