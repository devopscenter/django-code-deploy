#
# Django Code Deploy
#
# Copyright 2015 devops.center
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from fabric.api import env, roles, run, local,put, cd, sudo, settings
from time import gmtime, strftime
import os, sys
from git import Repo

env.user="ubuntu"

timest =  strftime("%Y-%m-%d_%H-%M-%S", gmtime())
UPLOAD_CODE_PATH = os.path.join("/data/deploy", timest)
TAR_NAME = "devops"

def tar_from_git(branch):
    local('rm -rf %s.tar.gz' % TAR_NAME)
    local('git archive origin/%s --format=tar.gz --output=%s.tar.gz' % (branch,TAR_NAME))

def unpack_code():
    cmd = "mkdir -p "+UPLOAD_CODE_PATH
    sudo(cmd)
    put('%s.tar.gz' % TAR_NAME, '%s' % UPLOAD_CODE_PATH, use_sudo=True)
    with cd('%s' % UPLOAD_CODE_PATH):
        sudo('tar zxf %s.tar.gz' % TAR_NAME)
    #sudo('chgrp -R %S %s' % (GROUP_SERVICE,UPLOAD_CODE_PATH))

def link_new_code():
    try:
        sudo('unlink /data/deploy/current')
    except:
        pass
    sudo('ln -s %s /data/deploy/current' % UPLOAD_CODE_PATH)
    with cd('/data/deploy'):
        sudo('(ls -t|head -n 5;ls)|sort|uniq -u|xargs rm -rf')

def remote_inflate_code():
    unpack_code()
    link_new_code()
    codeversioner()

def codeversioner():
    repo = Repo('.')
    headcommit = repo.head.commit
    commitid = headcommit.hexsha
    versionhash = commitid
    print versionhash
    with cd('/data/deploy/current'):
        run("echo 'version=\"%s\"' > /tmp/versioner.py" % versionhash)
        cmd = 'cp /tmp/versioner.py /data/deploy/current/versioner.py'
        sudo(cmd)

def deploycode(branch):
    tar_from_git(branch)
    remote_inflate_code()


def dbmigrate_docker(containerid,codepath='/data/deploy/current'):
    run('docker exec -it %s /bin/bash -c "cd /data/deploy/current && python manage.py migrate --noinput --ignore-ghost-migrations"' % containerid)

