include ../GNUmakefile.inc

PYC = cmdline.pyc config.pyc resolver.pyc download.pyc gpg.pyc help.pyc log.pyc spiparser.pyc swup.pyc upgrade.pyc utils.pyc urilib.py
SUBDIRS = pkgdriver

#%.pyc: %.py
#	python -c "import compileall; compileall.compile_dir('.', 0)"

all:
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

install:
	install -d -m 0755 -o root -g root $(DESTDIR)/$(BINDIR)
	install -d -m 0755 -o root -g root $(DESTDIR)/$(LIBDIR)
	install -c -m 0644 -o root -g root *.py $(DESTDIR)/$(LIBDIR)
	install -c -m 0755 -o root -g root swup $(DESTDIR)/$(BINDIR)
	chmod 0755 $(DESTDIR)/$(BINDIR)/swup
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done


.PHONY: clean
clean:
	-rm *.pyc
	for dir in $(SUBDIRS); do $(MAKE) -C $$dir $@ || exit 1; done

