
prefix = /usr/local

REPO = https://github.com/markokr/rarfile
NEWS = doc/news.rst

PACKAGE = $(shell python3 setup.py --name)
VERSION = $(shell python3 setup.py --version)
RXVERSION = $(shell python3 setup.py --version | sed 's/\./[.]/g')
TAG = v$(VERSION)
TGZ = dist/$(PACKAGE)-$(VERSION).tar.gz
URL = $(REPO)/releases/download/v$(VERSION)/$(PACKAGE)-$(VERSION).tar.gz

all:
	pyflakes3 rarfile.py
	tox -e lint
	tox -e py38-cryptography -- -n auto

install:
	python setup.py install --prefix=$(prefix)

clean:
	rm -rf __pycache__ build dist .tox
	rm -f *.pyc MANIFEST *.orig *.rej *.html *.class test/*.pyc
	rm -rf doc/_build doc/_static doc/_templates doc/html
	rm -rf .coverage cover*
	rm -rf *.egg-info
	rm -f test/files/*.rar.[pjt]* *.diffs

toxclean: clean
	rm -rf .tox

ack:
	for fn in test/files/*.py38-cryptography; do \
		cp $$fn `echo $$fn | sed 's/[.]py.*/.exp/'` || exit 1; \
	done

prepare:
	@echo "Checking version - $(VERSION)"
	@grep -qE '^\w+ $(RXVERSION)\b' $(NEWS) \
	|| { echo "Version '$(VERSION)' not in $(NEWS)"; exit 1; }
	@echo "Checking git repo"
	@git diff --stat --exit-code || { echo "ERROR: Unclean repo"; exit 1; }

release: prepare
	git tag $(TAG)
	git push github $(TAG):$(TAG)

upload:
	mkdir -p dist && rm -f dist/*
	cd dist && wget -q $(URL)
	tar tvf $(TGZ)
	twine upload $(TGZ)

shownote:
	awk -v VER="$(VERSION)" -f doc/note.awk $(NEWS) \
	| pandoc -f rst -t gfm --wrap=none

unrelease:
	git push github :$(TAG)
	git tag -d $(TAG)

dist-test:
	python3 setup.py sdist
	rm -rf $(PACKAGE)-$(VERSION)
	tar xf $(TGZ)
	cd $(PACKAGE)-$(VERSION) && tox

