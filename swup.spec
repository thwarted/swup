# $Id: swup.spec,v 1.2 2006/08/09 20:49:00 nived Exp $
Summary: The secure software updater
Name: swup
Version: 2.7.15
Release: 3tr
License: GPL
Group: Trustix Official
Source0: %{name}-%{version}.tar.bz2
PreReq: python
Requires: rpm, rpm-python, gnupg, sysklogd
Requires: swup-conf
Requires: tsl-gpgkeys
Requires: python-modules
Provides: softwareupdater
Provides: swup-libs
Provides: swup-rdfgen
Provides: rdfgen
Obsoletes: rdfgen
Obsoletes: swup-libs
Obsoletes: swup-rdfgen
BuildRequires: python, coreutils

BuildRoot: %{_tmppath}/%{name}-root
%define sitepackagedir usr/%{_lib}/python$(python -V 2>&1| cut -c8-10)/site-packages
%define username swup
%define groupname swup
%define userid 113
%define groupid 113
%define homedir /home/swup
%define shell /bin/false
%define groupadd /usr/sbin/groupadd
%define useradd /usr/sbin/useradd

%description
SWUP - SoftWare UPdater is an extension for existing software packaging
systems to facilitate automatic and secure update and install. SWUP
handles dependencies between software packages, and is able to fetch
additional required software when installing or upgrading.

rdfgen is a tool for generating database files in rdf/xml format to work with
the swup software upgrading tool.

This package includes the swup and rdfgen binaries with required libraries.

%package conf
Summary: Config file for swup.
Group: Trustix Official
Obsoletes: swupconf
Provides: swupconf
Requires: %{name} >= %{version}-%{release}
PreReq: /bin/chmod

%description conf
This is the configuration file for swup.

The configuration file is separated into another package simply to ease
building products with different swup configuration.

%package cron
summary: cron file for swup.
group: trustix official
requires: crond
obsoletes: swupcron

%description cron
this is the cron file for swup. install this if you want swup to be run
automatically.

swup-cron now includes a configuration file which allows the user to specify
command line arguments to be used in the automatic swup run.

%package cgi
summary: SWUP Web Search Engine
group: trustix official
Requires: apache, python, swup
PreReq: %{groupadd}
PreReq: %{useradd}

%description cgi
swup-cgi includes a configurable cgi script that provides a Web based package
search engine. It uses swup and apache httpd as backends.

%prep
%setup -q

%install
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf ${RPM_BUILD_ROOT}
make
make DESTDIR=${RPM_BUILD_ROOT} SITEDIR=%{sitepackagedir}/swuplib install
install -d -m 0755 ${RPM_BUILD_ROOT}/usr/bin
for f in `find ${RPM_BUILD_ROOT}/usr/lib/swup -name \*.py`; do
    touch ${f}c
done
for f in `find ${RPM_BUILD_ROOT}/%{sitepackagedir} -name \*.py`; do
    touch ${f}c
done
# rdf ghost files, must be removed when uninstalling this package.
for i in rdf rdfgen; do
        touch ${RPM_BUILD_ROOT}/usr/lib/rdfgen/$i.pyc
done

#swupconf
mkdir -p ${RPM_BUILD_ROOT}/etc/swup/{gnupg,samples}
touch ${RPM_BUILD_ROOT}/etc/swup/gnupg/pubring.gpg

#
# Install all sample configs:
#
install -m 0644 etc/swup/swup.conf-* ${RPM_BUILD_ROOT}/etc/swup/samples/
#
# Pick suitable default config:
#

#
# Check if this is a TrustixOS distribution
#
if [ "`echo \"%{?distribution}\" | grep -q TrustixOS; echo $?`" == "0" ]; then
    if [ -f etc/swup/swup.conf-Trustix ]; then
        sed "s|DISTRIBUTION|%{?distribution}|g" < etc/swup/swup.conf-Trustix \
            > ${RPM_BUILD_ROOT}/etc/swup/swup.conf
    else
        echo "'etc/swup/swup.conf-Trustix' is not a file"
        exit 1
    fi
elif [ -f  etc/swup/swup.conf-%{?release_version} ]; then
    install -m 0644 etc/swup/swup.conf-%{?release_version} \
        ${RPM_BUILD_ROOT}/etc/swup/swup.conf
else
    echo ""
    echo "No nice config found, installing /etc/swup/swup.conf"
    echo ""
    sleep 3
    install -m 0644 etc/swup/swup.conf-default \
        ${RPM_BUILD_ROOT}/etc/swup/swup.conf
fi

#
# swupcron
#
mkdir -p ${RPM_BUILD_ROOT}/etc/cron.{hourly,daily,weekly,monthly}/
install -m 0755 etc/cron.daily/swup.cron \
    ${RPM_BUILD_ROOT}/etc/cron.daily/swup.cron
touch ${RPM_BUILD_ROOT}/etc/cron.{hourly,weekly,monthly}/swup.cron

#
# Generate site package filelist
#
pushd $RPM_BUILD_ROOT
for file in `find %{sitepackagedir} -name \*.py`; do
        echo /${file}
        echo %ghost /${file}c
done >> ${RPM_BUILD_DIR}/%{name}-%{version}/sitefiles.txt
popd

%clean
[ -n "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != / ] && rm -rf ${RPM_BUILD_ROOT}

%pre cgi
#
# Add user and group if missing
#
if [ -z "`getent group %{groupname}`" ]; then
        %{groupadd}  -g %{groupid} %{groupname}
fi
if [ -z "`getent passwd %{username}`" ]; then
%{useradd} -d %{homedir} -g %{groupname} -s %{shell} -u %{userid} %{username}
fi


%post
python -c "import compileall; compileall.compile_dir('/usr/lib/swup')" \
    > /dev/null 2>&1
python -c "import compileall; compileall.compile_dir('/usr/lib/rdfgen')" \
    > /dev/null 2>&1
python -c \
    "import compileall; compileall.compile_dir('/%{sitepackagedir}/swuplib')" \
    > /dev/null 2>&1

%post conf
if [ "$1" = 2 ]; then
    if [ -f /etc/swup/gnupg/pubring.gpg ]; then
        /bin/chmod 644 /etc/swup/gnupg/pubring.gpg || :
    fi
fi

%files -f sitefiles.txt
%defattr(-,root,root,0755)
%doc docs/README docs/COPYING docs/CHANGELOG
%doc docs/swup.vimrc
/usr/bin/swup
/usr/bin/rdfgen
%dir /usr/lib/swup
%dir /usr/lib/rdfgen
/usr/lib/swup/*.py
/usr/lib/rdfgen/*.py
/usr/share/man/man1/swup.1.gz
/usr/share/man/man5/swup.5.gz
/usr/share/man/man1/rdfgen.*
%ghost /usr/lib/swup/*.pyc
%ghost /usr/lib/rdfgen/*.pyc

%files cron
%defattr(-,root,root,0755)
/etc/cron.daily/swup.cron
%config(noreplace) /etc/swup/swup-cron.conf
%ghost /etc/cron.hourly/swup.cron
%ghost /etc/cron.monthly/swup.cron
%ghost /etc/cron.weekly/swup.cron

%files conf
%defattr(-,root,root,0755)
%config(noreplace) /etc/swup/swup.conf
%dir /etc/swup/conf.d
/etc/swup/samples
%dir %attr(0711,root,root) /etc/swup/gnupg
%ghost /etc/swup/gnupg/pubring.gpg

%files cgi
%defattr(-,root,root,0755)
%dir %attr(0755,swup,swup)/home/swup/public_html/cgi-bin/
%attr(0755,swup,swup)/home/swup/public_html/cgi-bin/swup_query.py
%config(noreplace) /home/swup/public_html/cgi-bin/swup_query_config.py
%config(noreplace) /etc/httpd/conf.d/swup_query.conf

%changelog
* Mon Feb 26 2007 Nived Gopalan <nived at trustix dot org>
- Rebuilt

* Thu Aug 10 2006 Nived Gopalan <nived at trustix dot org> 2.7.15-2tr
- Added swup.conf for TSL-3.0.5

* Tue Aug 16 2005 Nived Gopalan <nived at comodo dot com> 2.7.15-1tr
- New upstream
- Added -cgi sub package and swup user / group creation
- Merged swup-rdfgen and swup-libs with swup

* Thu Aug 11 2005 Erlend Midttun <erlendbm at trustix dot org> 2.7.13-2tr
- Fix upgrade.

* Thu Aug 11 2005 Ajith Thampi <ajith at comodo dot com> 2.7.13-1tr
- New Upstream
- gnupg is 0711

* Thu Jul 21 2005 Ajith Thampi <ajith at comodo dot com> 2.7.12-1tr
- New Upstream
- gnupg should be 755 and pubring.gpg should be 644

* Wed Jul 20 2005 Ajith Thampi <ajith at comodo dot com> 2.7.11-1tr
- New Upstream

* Fri Jul 01 2005 Ajith Thampi <ajith at comodo dot com> 2.7.9-1tr
- New Upstream
- Better defattr

* Thu Jun 30 2005 Ajith Thampi <ajith at comodo dot com> 2.7.8-1tr
- New Upstream

* Wed Jun 29 2005 Ajith Thampi <ajith at comodo dot com> 2.7.7-1tr
- New Upstream

* Fri Jun 24 2005 Ajith Thampi <ajith at comodo dot com> 2.7.6-1tr
- New Upstream

* Wed Jun 22 2005 Syed Shabir Zakiullah <syedshabir at comodo dot com> 2.7.5-1tr
- New Upstream

* Mon Jun 20 2005 Syed Shabir Zakiullah <syedshabir at comodo dot com> 2.7.4-1tr
- New Upstream

* Mon Dec  6 2004 Erlend Midttun <erlendbm at trustix dot org> 7tr
- No longer create log dirs; we leave this to syslog

* Thu Nov 25 2004 Erlend Midttun <erlendbm at trustix dot org> 6tr
- Now let swup-conf require >= swup

* Tue Oct 12 2004 Chr. H. Toldnes <christht at trustix dot org> 5ct
- Added conf.d directory
- Don't build as noarch

* Tue Jun 29 2004 Chr. H. Toldnes <christht at trustix dot org> 4ct
- Hide output from %post scripts

* Tue Jun 22 2004 Chr. H. Toldnes <christht at trustix dot org> 3ct
- fixed misplacement of site package

* Fri Jun 18 2004 Chr. H. Toldnes <christht at trustix dot org> 2ct
- Major cleanup:
  - rdfgen -> swup-rdfgen
  - swupconf -> swup-conf
  - swupcron -> swup-cron
- Handling of more config files

* Thu Apr 29 2004 Oystein Viggen <oysteivi at trustix dot org> 1ov
- Use %{_lib} when guessing at site-packages directory
- compile_dir site-packages/swuplib

* Thu Feb 26 2004 Chr. H. Toldnes <christht at trustix dot org> 1ct
- Changelog now for specfile only
- Intelligent finding correct config.
