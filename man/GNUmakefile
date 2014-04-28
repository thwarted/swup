include ../GNUmakefile.inc
MAN1 = swup.1.gz
MAN5 =  swup.5.gz

%.1.gz: %.1
	gzip -c -9 $^ > $^.gz

%.5.gz: %.5
	gzip -c -9 $^ > $^.gz

all: $(MAN1) $(MAN5)

install:
	install -d -m 0755 -o root -g root $(DESTDIR)/$(MANDIR)/man1
	install -d -m 0755 -o root -g root $(DESTDIR)/$(MANDIR)/man5
	install -c -m 0644 -o root -g root $(MAN1) $(DESTDIR)/$(MANDIR)/man1
	install -c -m 0644 -o root -g root $(MAN5) $(DESTDIR)/$(MANDIR)/man5

.PHONY: clean
clean:
	-rm *.gz
