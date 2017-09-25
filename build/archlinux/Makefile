DESTDIR = root
PREFIX = /opt
VERSION = `date +%s`
SANDMAN_HOME = /sandman

.PHONY: install
install:
	mkdir -p $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/bin
	mkdir -p $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/etc
	mkdir -p $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/cache
	mkdir -p $(DESTDIR)/etc/profile.d
	cp sb2 $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/bin
	cp sm $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/bin
	cp LICENSE $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)
	cp README.txt $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)
	cp requirements.txt $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)
	echo 'PREFIX=$(PREFIX)' > $(DESTDIR)/etc/profile.d/sandman.sh
	echo 'SANDMAN_HOME=$(SANDMAN_HOME)' >> $(DESTDIR)/etc/profile.d/sandman.sh
	cat sandman.sh >> $(DESTDIR)/etc/profile.d/sandman.sh
	cp config.json $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/etc/config.json
	rm -rf lib/*.pyc
	rm -rf vcs/*.pyc
	rm -rf lib/__pycache*
	rm -rf vcs/__pycache*
	cp -r lib  $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/bin
	cp -r vcs  $(DESTDIR)$(PREFIX)$(SANDMAN_HOME)/bin
	description="Sandman built from commit "`git rev-parse HEAD | head -c 8`

#.PHONY: uninstall
#uninstall:
#    rm -f $(DESTDIR)$(PREFIX)/bin/mygame
