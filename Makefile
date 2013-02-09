#
# Copyright © 2011-2013, RokuSigma Inc. and contributors as an unpublished
# work. See AUTHORS for details.
#
# RokuSigma Inc. (the “Company”) Confidential
#
# NOTICE: All information contained herein is, and remains the property of the
# Company. The intellectual and technical concepts contained herein are
# proprietary to the Company and may be covered by U.S. and Foreign Patents,
# patents in process, and are protected by trade secret or copyright law.
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from the
# Company. Access to the source code contained herein is hereby forbidden to
# anyone except current Company employees, managers or contractors who have
# executed Confidentiality and Non-disclosure agreements explicitly covering
# such access.
#
# The copyright notice above does not evidence any actual or intended
# publication or disclosure of this source code, which includes information
# that is confidential and/or proprietary, and is a trade secret, of the
# Company. ANY REPRODUCTION, MODIFICATION, DISTRIBUTION, PUBLIC PERFORMANCE,
# OR PUBLIC DISPLAY OF OR THROUGH USE OF THIS SOURCE CODE WITHOUT THE EXPRESS
# WRITTEN CONSENT OF THE COMPANY IS STRICTLY PROHIBITED, AND IN VIOLATION OF
# APPLICABLE LAWS AND INTERNATIONAL TREATIES. THE RECEIPT OR POSSESSION OF
# THIS SOURCE CODE AND/OR RELATED INFORMATION DOES NOT CONVEY OR IMPLY ANY
# RIGHTS TO REPRODUCE, DISCLOSE OR DISTRIBUTE ITS CONTENTS, OR TO MANUFACTURE,
# USE, OR SELL ANYTHING THAT IT MAY DESCRIBE, IN WHOLE OR IN PART.
#

ROOT=$(shell pwd)
CACHE_ROOT=${ROOT}/.cache
PKG_ROOT=${ROOT}/.pkg
PROJECT_NAME=hellogae
SDK_ROOT=$(shell dirname $(shell which dev_appserver.py))

-include Makefile.local

.PHONY: all
all: ${PKG_ROOT}/.stamp-h ${ROOT}/src/secret_keys.py

.PHONY: check
check: all
	mkdir -p build/report/xunit
	"${PKG_ROOT}"/bin/coverage run xunit/__main__.py
	"${PKG_ROOT}"/bin/coverage xml \
	    --omit="xunit/__main__.py" \
	    -o build/report/coverage.xml

.PHONY: run
run: all
	mkdir -p "${ROOT}"/db/blobstore
	"${PKG_ROOT}"/bin/python "${SDK_ROOT}"/dev_appserver.py \
	    --blobstore_path="${ROOT}"/db/blobstore \
	    --datastore_path="${ROOT}"/db/datastore \
	    --history_path="${ROOT}"/db/datastore.history \
	    --search_indexes_path="${ROOT}"/db/searchindexes \
	    --high_replication \
	    --persist_logs \
	    --use_sqlite \
	    -p 8080 .

.PHONY: shell
shell: all
	"${PKG_ROOT}"/bin/python "${ROOT}"/manage.py \
	    shell -s localhost:8080

.PHONY: mostlyclean
mostlyclean:
	- rm -rf lib
	- rm -rf build
	- rm -rf .coverage

.PHONY: clean
clean: mostlyclean
	- rm -rf "${PKG_ROOT}"

.PHONY: distclean
distclean: clean
	- rm -rf "${CACHE_ROOT}"
	- rm -rf Makefile.local

.PHONY: maintainer-clean
maintainer-clean: distclean
	@echo 'This command is intended for maintainers to use; it'
	@echo 'deletes files that may need special tools to rebuild.'

# ===----------------------------------------------------------------------===

${ROOT}/src/secret_keys.py:
	@echo  >"${ROOT}"/src/secret_keys.py '#!/usr/bin/env python'
	@echo >>"${ROOT}"/src/secret_keys.py '# -*- coding: utf-8 -*-'
	@echo >>"${ROOT}"/src/secret_keys.py "SESSION_KEY='`LC_CTYPE=C < /dev/urandom tr -dc A-Za-z0-9_ | head -c24`'"
	@echo >>"${ROOT}"/src/secret_keys.py "CSRF_SECRET_KEY='`LC_CTYPE=C < /dev/urandom tr -dc A-Za-z0-9_ | head -c24`'"

# ===----------------------------------------------------------------------===

${CACHE_ROOT}/virtualenv/virtualenv-1.8.4.tar.gz:
	mkdir -p "${CACHE_ROOT}"/virtualenv
	sh -c "cd "${CACHE_ROOT}"/virtualenv && curl -O 'http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.8.4.tar.gz'"

${PKG_ROOT}/.stamp-h: ${ROOT}/requirements*.pip ${CACHE_ROOT}/virtualenv/virtualenv-1.8.4.tar.gz
	# Because build and run-time dependencies are not thoroughly tracked,
	# it is entirely possible that rebuilding the development environment
	# on top of an existing one could result in a broken build. For the
	# sake of consistency and preventing unnecessary, difficult-to-debug
	# problems, the entire development environment is rebuilt from scratch
	# everytime this make target is selected.
	${MAKE} clean
	
	# The `${PKG_ROOT}` directory, if it exists, is removed by the `clean`
	# target. The PyPI cache is nonexistant if this is a freshly checked-out
	# repository, or if the `distclean` target has been run. This might cause
	# problems with build scripts executed later which assume their existence,
	# so they are created now if they don't already exist.
	mkdir -p "${PKG_ROOT}"
	mkdir -p "${CACHE_ROOT}"/pypi
	
	# `virtualenv` is used to create a separate Python installation for this
	# project in `${PKG_ROOT}`.
	tar \
	    -C "${CACHE_ROOT}"/virtualenv --gzip \
	    -xf "${CACHE_ROOT}"/virtualenv/virtualenv-1.8.4.tar.gz
	python "${CACHE_ROOT}"/virtualenv/virtualenv-1.8.4/virtualenv.py \
	    --clear \
	    --distribute \
	    --never-download \
	    --prompt="(${PROJECT_NAME}) " \
	    "${PKG_ROOT}"
	rm -rf "${CACHE_ROOT}"/virtualenv/virtualenv-1.8.4
	
	# pip has broken the Python Imaging Library install (perhaps because
	# the tarball does not follow standard naming practice). So we
	# manually install it here, specifying the download URL directly:
	"${PKG_ROOT}"/bin/easy_install \
	    http://effbot.org/downloads/Imaging-1.1.7.tar.gz
	
	# readline is installed here to get around a bug on Mac OS X which is
	# causing readline to not build properly if installed from pip.
	"${PKG_ROOT}"/bin/easy_install readline
	
	# install production dependencies:
	for reqfile in "${ROOT}"/requirements.pip; do \
	    CFLAGS=-I/opt/local/include LDFLAGS=-L/opt/local/lib \
	    "${PKG_ROOT}"/bin/python "${PKG_ROOT}"/bin/pip install \
	        --download-cache="${CACHE_ROOT}"/pypi \
	        -r "$$reqfile"; \
	done
	
	# bundle production dependencies for upload:
	mkdir -p "${ROOT}"/lib
	"${PKG_ROOT}"/bin/pip zip --list | \
	    grep '    ' | \
	    grep -v PIL- | \
	    grep -v distribute- | \
	    grep -v jinja2 | \
	    grep -v pip- | \
	    grep -v readline- | \
	    grep -v webapp2_extras | \
	    grep -v webob | \
	    while read line; do \
	        package=`echo $$line | cut -d' ' -f1`; \
	        "${PKG_ROOT}"/bin/pip zip --no-pyc "$$package"; \
	        cp "${PKG_ROOT}"/lib/python2.7/site-packages/"$$package".zip "${ROOT}"/lib/; \
	    done
	ls -1 "${PKG_ROOT}"/lib/python2.7/site-packages | \
	    grep '\.py$$' | \
	    while read module; do \
	        cp "${PKG_ROOT}"/lib/python2.7/site-packages/"$$module" "${ROOT}"/lib/; \
	    done
	
	# install development/testing dependencies:
	for reqfile in "${ROOT}"/requirements-*.pip; do \
	    CFLAGS=-I/opt/local/include LDFLAGS=-L/opt/local/lib \
	    "${PKG_ROOT}"/bin/python "${PKG_ROOT}"/bin/pip install \
	        --download-cache="${CACHE_ROOT}"/pypi \
	        -r "$$reqfile"; \
	done
	
	# All done!
	touch "${PKG_ROOT}"/.stamp-h

#
# End of File
#
