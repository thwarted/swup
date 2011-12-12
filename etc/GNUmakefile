include ../GNUmakefile.inc
.PHONY: all install clean

all:

install:
	install -d -m 0755 $(DESTDIR)/etc
	install -d -m 0755 $(DESTDIR)/etc/swup
	install -d -m 0755 $(DESTDIR)/etc/swup/gnupg
	install -d -m 0755 $(DESTDIR)/etc/swup/samples
	install -d -m 0755 $(DESTDIR)/etc/swup/conf.d
	install -d -m 0755 $(DESTDIR)/etc/cron.daily
	install -c -m 0644 swup/swup.conf* \
        $(DESTDIR)/etc/swup/samples/
	install -c -m 0644 swup/swup-cron.conf \
        $(DESTDIR)/etc/swup/
	install -c -m 0755 cron.daily/swup.cron \
	$(DESTDIR)/etc/cron.daily/

uninstall:
	rm -rf $(DESTDIR)/etc/swup
	rm -f $(DESTDIR)/etc/cron.daily/swup.cron

clean:

