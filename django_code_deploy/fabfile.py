#
# Django Code Deploy
#
# Copyright 2015 - 2016 devops.center
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

from fabric.api import env, roles, run, local, put, cd, sudo, settings, task
from time import gmtime, strftime
import os, sys
from git import Repo

env.user="ubuntu"
TRUTH_VALUES = [True, 1, '1', 'true', 't', 'yes', 'y']

import boto, urllib2
from   boto.ec2 import connect_to_region

import distutils.sysconfig

#objects
import collections
AWSAddress = collections.namedtuple('AWSAddress', 'publicdns privateip')


# set_hosts selects all instances that match the filter criteria.
#  type is web, worker, db
#  environment is dev, staging, prod
#  appname is application name, such as "fresco", "topopps", "mojo", etc.
#  action is the deferred action needed, such as "deploy", "security-updates", etc.
#  region is aws region
@task
def set_hosts(type,primary=None,appname=None,action=None,region=None):
    if appname is None:
        local('echo "ERROR: appname option is not set"')
    if region is None:
        local('echo "ERROR: region option is not set"')
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses    = _get_awsaddress(type, primary, environment, appname, action, region)
    env.hosts = list( item.publicdns for item in awsaddresses )
    logger.info("hosts: %s", env.hosts)

# set_one_host picks a single instance out of the set.
#  filters are the same as with set_hosts.
@task
def set_one_host(type,primary=None,appname=None,action=None,region=None):
    if appname is None:
        local('echo "ERROR: appname option is not set"')
    if region is None:
        local('echo "ERROR: region option is not set"')
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses    = _get_awsaddress(type, primary, environment, appname, action, region)
    env.hosts = [awsaddresses[0].publicdns]
    logger.info("hosts: %s", env.hosts)

@task
def dev():
    os.environ["AWS_ENVIRONMENT"] = "dev"

@task
def staging():
    os.environ["AWS_ENVIRONMENT"] = "staging"

@task
def prod():
    os.environ["AWS_ENVIRONMENT"] = "prod"

@task
def set_environment(environment):
    os.environ["AWS_ENVIRONMENT"] = environment

@task
def set_access_key(accessKeyPath):
    env.key_filename = accessKeyPath

@task
def set_user(loginName):
    env.user = loginName

@task
def show_environment():
    run('env')

# Private method to get public DNS name for instance with given tag key and value pair
def _get_awsaddress(type,primary, environment,appname,action,region):
    awsaddresses = []
    logger.info("region=%s", region)
    connection   = _create_connection(region)
    aws_tags = {"tag:Type" : type, "tag:Env" : environment, "tag:App" : appname, "instance-state-name" : "running"}
    if action:
        aws_tags["tag:ActionNeeded"] = action
    if primary:
        aws_tags["tag:Primary"] = primary
    logger.info("tags=%s", aws_tags)
    reservations = connection.get_all_instances(filters = aws_tags)
    for reservation in reservations:
        for instance in reservation.instances:
            print "Instance structure: {}".format(instance)
            if instance.public_dns_name:                    # make sure there's really an instance here
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

@task
def tar_from_git(branch):
    local('rm -rf %s.tar.gz' % TAR_NAME)
    local('git archive %s --format=tar.gz --output=%s.tar.gz' % (branch,TAR_NAME))

@task
def unpack_code():
    cmd = "mkdir -p "+UPLOAD_CODE_PATH
    sudo(cmd)
    put('%s.tar.gz' % TAR_NAME, '%s' % UPLOAD_CODE_PATH, use_sudo=True)
    with cd('%s' % UPLOAD_CODE_PATH):
        sudo('tar zxf %s.tar.gz' % TAR_NAME)


@task
def link_new_code():
    try:
        sudo('unlink /data/deploy/pending')
    except:
        pass
    sudo('ln -s %s /data/deploy/pending' % UPLOAD_CODE_PATH)
    with cd('/data/deploy'):
        sudo('(ls -t|head -n 5;ls)|sort|uniq -u|xargs rm -rf')

@task
def pip_install():
    with cd('/data/deploy/pending'):
        sudo('pip install -r requirements.txt')

@task
def download_nltk_data():
    sudo_app('if [[ -f nltk.txt ]]; then mkdir -p /usr/share/nltk_data/; cat nltk.txt | while read -r line; do python -m nltk.downloader -d /usr/share/nltk_data ${line}; done; fi')

@task
def collect_static():
    with cd('/data/deploy/pending'):
        sudo('if [[ ! -d static ]]; then mkdir static/ ;fi')
        sudo('chmod 777 static')
        sudo('python manage.py collectstatic --noinput')


@task
#https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-check
def django_check():
    with cd('/data/deploy/pending'):
        sudo('python manage.py check')

@task
def remote_inflate_code():
    unpack_code()
    link_new_code()
    codeversioner()

@task
def codeversioner():
    repo = Repo('.')
    headcommit = repo.head.commit
    commitid = headcommit.hexsha
    versionhash = commitid
    print versionhash
    with cd('/data/deploy/pending'):
        run("echo 'version=\"%s\"' > /tmp/versioner.py" % versionhash)
        cmd = 'cp /tmp/versioner.py /data/deploy/pending/versioner.py'
        sudo(cmd)

@task
def deploycode(branch,doCollectStatic=True):
    tar_from_git(branch)
    remote_inflate_code()
    pip_install()
    if doCollectStatic in TRUTH_VALUES:
        collect_static()
    else:
        sudo('cp -r ' + '/usr/local/opt/python/lib/python2.7/site-packages' + '/django/contrib/admin/static/admin /data/deploy/pending/static/')

@task
def dbmigrate_docker(containerid,codepath='/data/deploy/current'):
    run('docker exec -it %s /bin/bash -c "cd /data/deploy/current && python manage.py migrate --noinput --ignore-ghost-migrations"' % containerid)

@task
def dbmigrate(migrateOptions=None):
    cmdToRun = "cd /data/deploy/pending && python manage.py migrate --noinput"

    if migrateOptions is not None:
        cmdToRun += " " + migrateOptions

    run(cmdToRun)

supervisor="/usr/bin/supervisorctl"

# 
@task
def swap_code():
    sudo("unlink /data/deploy/current")
    sudo("ln -s $(readlink /data/deploy/pending) /data/deploy/current")

@task 
def reload_nginx():
    sudo("/usr/local/nginx/sbin/nginx -s reload")

@task
def reload_uwsgi():
    sudo("/bin/bash -c 'echo c > /tmp/uwsgififo'")
    
@task
def restart_nginx():
    sudo("%s restart nginx" % supervisor)

@task
def restart_uwsgi():
    sudo("mkdir -p /var/run/uwsgi")
    sudo("%s restart uwsgi" % supervisor)

@task
def restart_celery():
    sudo("%s restart celery:*" % supervisor)

@task
def restart_djangorq():
    sudo("%s restart djangorq-worker:*" % supervisor)

@task
def run_cmd(cmdToRun):
    run(cmdToRun)

@task
def sudo_cmd(cmdToRun):
    sudo(cmdToRun)

@task
def run_app(cmdToRun):
    run('cd /data/deploy/pending ; ' + cmdToRun)

@task
def sudo_app(cmdToRun):
    sudo('cd /data/deploy/pending ; ' + cmdToRun)

