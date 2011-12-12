#!/bin/sh
#
# This script should build the spec file for $PACKAGE
# and maybe build the packages.

#
# Important variables:
#
MAIN='swup'
PACKAGE="$MAIN"
VERSIONFILE="$PACKAGE/swuplib/help.py"
CVSHOST='swup.trustix.org'
NAME="$MAIN"


#
# Exit on all errors:
#

set -e

usage()
{
cat >&2 <<EOF
Usage: $cmd [-u user] [-b] [-d] [-t tempdir]
EOF
}

usage_help()
{
    usage
    cat >&2 <<EOF

Options are:
    -u user             CVS user 
    -b                  Build new rpms
    -d                  Build devel packages. version numbers using date.
    -t tempdir		Build tarball in this directory instead of an auto-
			created one.
EOF
}
#
#
# Check arguments, issue usage, version or help, or continue
#
if [ $# == 0 ]; then
    usage_help
    exit 1
fi
TEMPDIR=""
while getopts h:u:bdt: opt; do
    case $opt in
        h) usage_help; exit 0;;
        u) cvsuser="$OPTARG";;
        b) buildrpm=yes;;
        d) develbuild=yes;;
	t) TEMPDIR="$OPTARG";;
        *) usage; echo "Use $cmd -h for help" >&2; exit 1;;
    esac
done

#
# Get current timestamp
#

TIMESTAMP=`date +%G%m%d.%H%M` 
CVSROOT="$cvsuser@$CVSHOST:/home/cvs"

#
# Set up secure TMPDIR
#
if [ -z "$TEMPDIR" ]; then
TEMPDIR=$(mktemp -d /tmp/$NAME-build.XXXXXXX)
else
mkdir -p $TEMPDIR
rm -rf $TMPDIR/$NAME*
fi

#
# Tag cvs with timestamp
#


#
# Export cvs using timestamp into TMPDIR/$PACKAGE-TIMESTAMP
#

cd $TEMPDIR
export CVSROOT
export CVS_RSH=ssh
echo $CVSROOT
cvs -z3 co $PACKAGE

#
# Get version from $VERSIONFILE
#

VERSION=`grep ^VERSION $VERSIONFILE | sed s"|\"||g" | sed s"|VERSION=||"`

if [ "$develbuild" == "yes" ]; then
    VERSION="$VERSION.$TIMESTAMP"
fi

NV="$NAME-$VERSION"

mv $PACKAGE $NV
#
# Update $PACKAGE.spec with new timestamp
#
sed "s|VERSION|$VERSION|" $NV/trustix/$NAME.spec.src \
	> $NV/trustix/$NAME.spec
rm $NV/trustix/$NAME.spec.src

tar cfBPjv $NV.tar.bz2 $NV

rm -rf $NV

#
# Build new rpms! (Must be root) 
#
if [ -n "$buildrpm" ]; then
    rpm -ta $NV.tar.bz2
    #
    # remove tempdir
    #
    rm -rf $TEMPDIR
else
    echo "New $NAME tarball: '$TEMPDIR/$NV.tar.bz2'"
fi


