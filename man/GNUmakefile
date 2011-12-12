include ../GNUmakefile.inc
MAN1 = swup.1.gz
MAN2 = rdfgen.1.gz
MAN5 =  swup.5.gz

%.1.gz: %.1
	gzip -c -9 $^ > $^.gz
%.2.gz: %.1
	gzip -c -9 $^ > $^.gz
%.5.gz: %.5
	gzip -c -9 $^ > $^.gz

all: $(MAN1) $(MAN2) $(MAN5)  

install:
	install -d -m 0755 $(DESTDIR)/$(MANDIR)/man1
	install -d -m 0755 $(DESTDIR)/$(MANDIR)/man5
	install -c -m 0644 $(MAN1) $(DESTDIR)/$(MANDIR)/man1
	install -c -m 0644 $(MAN2) $(DESTDIR)/$(MANDIR)/man1
	install -c -m 0644 $(MAN5) $(DESTDIR)/$(MANDIR)/man5

uninstall:
	rm -f $(DESTDIR)/$(MANDIR)/man1/$(MAN1)
	rm -f $(DESTDIR)/$(MANDIR)/man1/$(MAN2)
	rm -f $(DESTDIR)/$(MANDIR)/man5/$(MAN5)


clean:
	-rm -f *.gz
