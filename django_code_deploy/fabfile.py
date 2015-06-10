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
import logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

from fabric.api import env, roles, run, local,put, cd, sudo, settings
from time import gmtime, strftime
import os, sys
from git import Repo

env.user="ubuntu"


import boto, urllib2
from   boto.ec2 import connect_to_region

import aws_settings as AWS_SETTINGS

#objects
import collections
AWSAddress = collections.namedtuple('AWSAddress', 'publicdns privateip')

#type is web, worker, db
#environment is dev, staging, prod
#version is application version like f2
#region is aws region
def set_hosts(type,primary=None,version=AWS_SETTINGS.APP_VERSION,region=AWS_SETTINGS.AWS_REGION):
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses    = _get_awsaddress(type, primary, environment, version, region)
    env.hosts = list( item.publicdns for item in awsaddresses )
    print env.hosts

def dev():
    os.environ["AWS_ENVIRONMENT"] = "dev"

def staging():
    os.environ["AWS_ENVIRONMENT"] = "staging"

def prod():
    os.environ["AWS_ENVIRONMENT"] = "prod"


# Private method to get public DNS name for instance with given tag key and value pair
def _get_awsaddress(type,primary, environment,version,region):
    awsaddresses = []
    logger.info("region=%s", region)
    connection   = _create_connection(region)
    aws_tags = {"tag:Type" : type, "tag:Environment" : environment, "tag:Version" : version}
    if primary:
        aws_tags["tag:Primary"]=primary
    logger.info("tags=%s", aws_tags)
    reservations = connection.get_all_instances(filters = aws_tags)
    for reservation in reservations:
        for instance in reservation.instances:
            print "Instance", instance.public_dns_name, instance.private_ip_address
            awsaddress = AWSAddress(publicdns =str(instance.public_dns_name), privateip=str(instance.private_ip_address))
            awsaddresses.append(awsaddress)
    return awsaddresses

# Private method for getting AWS connection
def _create_connection(region):
    print "Connecting to ", region

    connection = connect_to_region(
        region_name = region
   )

    print "Connection with AWS established"
    return connection

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

