#!/usr/bin/env bash

rm -rf /opt/sandman/cache
mkdir /opt/sandman/cache
chmod 777 /opt/sandman/cache
easy_install-3.4 pip
pip3 install argcomplete
pip3 install jsonschema
echo "Please run command 'source /etc/profile.d/sandman.sh' to add sandman to path"
