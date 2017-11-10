#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 v1.2.3"
    exit
fi

# Gather information
release=$1
version=${release#"v"}
tempdir=$(mktemp -d)
workingdir=`pwd`
pushd $tempdir > /dev/null

# Build archive
wget --quiet https://github.com/openmotics/gateway/archive/$release.tar.gz
tar -xzf $release.tar.gz
cd gateway-$version/src
tar -czf ../gateway_$version.tgz .
mv ../gateway_$version.tgz $workingdir/

# Cleanup
popd > /dev/null
rm -rf $tempdir

echo "gateway_$version.tgz"

