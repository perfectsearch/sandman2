#!/bin/bash


[[ $# -eq 0 ]] && type="rpm" || type="$1"
ROOT=root
VERSION=`date +%s`
SANDMAN_HOME=$ROOT/opt/sandman
rm -rf $ROOT
rm -rf *.rpm
rm -rf *.deb
rm -rf install
rm -rf files
mkdir -p $SANDMAN_HOME/bin
mkdir -p $SANDMAN_HOME/etc
mkdir -p $SANDMAN_HOME/cache
mkdir -p $ROOT/etc/profile.d
cp ../sb2 $SANDMAN_HOME/bin
cp ../sm $SANDMAN_HOME/bin
cp ../sandman-repos $SANDMAN_HOME/bin
cp ../LICENSE $SANDMAN_HOME
cp ../README.txt $SANDMAN_HOME
cp ../requirements.txt $SANDMAN_HOME
echo 'eval "$(register-python-argcomplete sb2)"
eval "$(register-python-argcomplete sm)"
export PATH=$PATH:/opt/sandman/bin
'> $ROOT/etc/profile.d/sandman.sh
cat >$SANDMAN_HOME/etc/config.json <<EOL
{
	"vcsrepo": {
		"path": "/opt/sandman/cache/config",
		"source": "git@192.0.2.100:Core/Build/sandman-config.git",
		"revision": "master",
		"provider": "git"
	},
	"user": {
		"bzr": {"name": "\${system_user}"},
		"git": {"name": "\${system_user}"}
	}
}
EOL
rm -rf ../lib/*.pyc
rm -rf ../vcs/*.pyc
rm -rf ../lib/__pycache*
rm -rf ../vcs/__pycache*
cp -r ../lib  $SANDMAN_HOME/bin
cp -r ../vcs  $SANDMAN_HOME/bin
description="Sandman built from commit "`git rev-parse HEAD | head -c 8`
if [ $type = "rpm" ]; then
	fpm -s dir -t $type -n sandman -d bzr -d python34-setuptools -v $VERSION --after-install scripts/post_install_rpm.sh --description "$description" -C $ROOT
#	sudo yum upgrade -y ./sandman*
elif [ $type = "deb" ]; then
	fpm -s dir -t $type -n sandman -d bzr -d git -d python3-argcomplete -d python3-jsonschema -v $VERSION --after-install scripts/post_install_deb.sh --description "$description" -C $ROOT
#	ansible-playbook scripts/test_build_on_mint.yml
else
	echo "$type not supported"
fi
mkdir install
mv sandman* install
mv $ROOT/opt/sandman ./files
mv $ROOT/etc/profile.d/sandman.sh files
rm -rf $ROOT
