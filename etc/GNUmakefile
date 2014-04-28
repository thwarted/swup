include ../GNUmakefile.inc

all:

install:
	install -d -m 0755 -o root -g root $(DESTDIR)/etc
	install -d -m 0755 -o root -g root $(DESTDIR)/etc/swup
	install -d -m 0755 -o root -g root $(DESTDIR)/etc/swup/gnupg
	[ -f $(DESTDIR)/etc/swup/swup.conf ] || install -c -m 0644 -o root -g root swup/swup.conf $(DESTDIR)/etc/swup

clean:

