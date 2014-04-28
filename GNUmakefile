include GNUmakefile.inc
SUBDIRS = src etc man

all:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

install:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

.PHONY: clean
clean:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done


