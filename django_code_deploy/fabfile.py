#
# Django Code Deploy
#
# Copyright 2015 - 2018 devops.center
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

from fabric.api import *

from time import gmtime, strftime
import os
import sys
from git import Repo


# Use bash for fabric local commands, per http://www.booneputney.com/development/fabric-run-local-bash-shell/
from fabric.api import local as local_cmd  # import local with alternate name

# create new local command, with the shell set to /bin/bash
def local(command_string):
    local_cmd(command_string, shell="/bin/bash")



class FabricException(Exception):
    pass


# Set some global defaults for all operations
env.user = "ubuntu"
env.key_filename = []
ACCESS_KEY_PATH = "~/.ssh/"
env.connection_attempts = 3


TRUTH_VALUES = ['True', 'TRUE', '1', 'true', 't', 'Yes',
                'YES', 'yes', 'y']  # arguments in fab are always strings

import boto
import urllib2
from boto.ec2 import connect_to_region

import distutils.sysconfig

# objects
import collections
AWSAddress = collections.namedtuple(
    'AWSAddress', 'name publicdns privateip shard')


# set_hosts selects all instances that match the filter criteria.
#  type is web, worker, db
#  environment is dev, staging, prod
#  appname is application name, such as "fresco", "topopps", "mojo", etc.
#  action is the deferred action needed, such as "deploy", "security-updates", etc.
#  region is aws region
@task
def set_hosts(type, primary=None, appname=None, action=None, region=None,
              shard='all', aRole=None):
    if appname is None:
        local('echo "ERROR: appname option is not set"')
    if region is None:
        local('echo "ERROR: region option is not set"')
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses = _get_awsaddress(type, primary, environment, appname,
                                   action, region, shard, aRole)

    env.hosts = list(item.publicdns for item in awsaddresses)
    env.host_names = list(item.name for item in awsaddresses)

    _log_hosts(awsaddresses)


# set_one_host picks a single instance out of the set.
#  filters are the same as with set_hosts.
@task
def set_one_host(type, primary=None, appname=None, action=None, region=None,
                 shard='all', aRole=None):
    if appname is None:
        local('echo "ERROR: appname option is not set"')
    if region is None:
        local('echo "ERROR: region option is not set"')
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses = _get_awsaddress(type, primary, environment, appname,
                                   action, region, shard, aRole)

    awsaddresses = [awsaddresses[0]]

    env.hosts = [awsaddresses[0].publicdns]
    env.host_names = [awsaddresses[0].name]

    _log_hosts(awsaddresses)


@task
def set_one_host_per_shard(type, primary=None, appname=None, action=None,
                           region=None, shard='all', aRole=None):
    if appname is None:
        local('echo "ERROR: appname option is not set"')
    if region is None:
        local('echo "ERROR: region option is not set"')
    environment = os.environ["AWS_ENVIRONMENT"]
    awsaddresses = _get_awsaddress(type, primary, environment, appname,
                                   action, region, shard, aRole)

    pruned_list = []
    for ahost in awsaddresses:
        if not next((True for bhost in pruned_list if ahost.shard == bhost.shard), False):
            pruned_list.append(ahost)

    env.hosts = list(item.publicdns for item in pruned_list)
    env.host_names = list(item.name for item in pruned_list)

    _log_hosts(pruned_list)


def _log_hosts(awsaddresses):
    logger.info("")
    logger.info(
        "Instances to operate upon - name, public dns, private ip, shard")
    logger.info(
        "---------------------------------------------------------------")
    for instance in awsaddresses:
        logger.info("%s  %s  %s  %s", instance.name,
                    instance.publicdns, instance.privateip, instance.shard)
    logger.info("")
    logger.info("")
    logger.info("keys: %s", env.key_filename)
    logger.info("")


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
    env.key_filename = [accessKeyPath]


@task
def set_access_key_path(anAccessKeyPath):
    global ACCESS_KEY_PATH
    if(anAccessKeyPath.endswith('/')):
        ACCESS_KEY_PATH = anAccessKeyPath
    else:
        ACCESS_KEY_PATH = anAccessKeyPath + "/"


@task
def set_user(loginName):
    env.user = loginName


@task
def show_environment():
    run('env')

# Private method to get public DNS name for instance with given tag key
# and value pair


def _get_awsaddress(type, primary, environment, appname, action, region, shard,
                    aRole):
    awsaddresses = []
    connection = _create_connection(region)
    aws_tags = {"tag:Type": type, "tag:Env": environment,
                "tag:App": appname, "instance-state-name": "running"}
    if action:
        aws_tags["tag:ActionNeeded"] = action
    if primary:
        aws_tags["tag:Primary"] = primary
    if aRole:
        aws_tags["tag:role"] = aRole
    logger.info("Filtering via tags=%s", aws_tags)
    instances = connection.get_only_instances(filters=aws_tags)
    shards = [e for e in shard.split(' ')]
    for instance in instances:
        if instance.public_dns_name:                                # make sure there's really an instance here
            shardt = (
                "None" if not 'Shard' in instance.tags else instance.tags['Shard'])
            awsaddress = AWSAddress(name=instance.tags['Name'], publicdns=instance.public_dns_name,
                                    privateip=instance.private_ip_address, shard=shardt)
            if (shard == 'all') or (shardt in shards):
                awsaddresses.append(awsaddress)
                if instance.key_name not in env.key_filename:
                    env.key_filename.append(instance.key_name)
    # convert any AWS key-pair names to a file path for the actual key pair
    # locally
    env.key_filename = [key if os.path.isfile(
        key) else ACCESS_KEY_PATH + key + ".pem" for key in env.key_filename]
    return awsaddresses

# Private method for getting AWS connection


def _create_connection(region):
    logger.info("")
    logger.info("Connecting to AWS region %s", region)

    connection = connect_to_region(
        region_name=region
    )

    logger.info("Connection with AWS established")
    return connection

timest = strftime("%Y-%m-%d_%H-%M-%S", gmtime())
# deploy directories have timestamps for names.
UPLOAD_CODE_PATH = os.path.join("/data/deploy", timest)
TAR_NAME = "devops"

# These are tasks for building on jenkins (or other build box)
# Initally support a yarn-based workflow for node
@task
def build(branch, installPath, node=False):
    
    # ensure yarn installs all build tools
    with lcd(installPath):
        local("pwd")
        local('yarn --production=false --no-progress --non-interactive install')

        # do the build
        local('npm run dist')

        if node in TRUTH_VALUES:
            local('if [[ -d "config" ]]; then echo "<collecting config>" ; rsync -ra --stats config/ dist/config; fi;')
            local('if [[ -d "src/public" ]]; then echo "<collecting public>" ; rsync -ra --stats src/public/ dist/public; fi;')
            local('if [[ -d "node_modules" ]]; then echo "<collecting node_modules>" ; rsync -ra --stats node_modules/ dist/node_modules; fi;')

    # make sure the new files are part of the local git repo
    local('find . -path ./\.git -prune -o -name \.gitignore -type f -exec rm -f {} \;')
    local('echo "%s.tar.*" >> .gitignore' % TAR_NAME)
    local('echo "fabfile.*" >> .gitignore')
    local("git add .")
    local("git commit -am 'add results of build' --no-verify --quiet")




# Obtain git_sha from Jenkins git plugin, make sure it's passed along with the code so that
# uwsgi, djangorq, and and celery can make use of it (e.g. to pass to
# Sentry for releases)

@task
def set_git_sha():
    local('echo "GIT_SHA=${GIT_COMMIT}" >> dynamic_env.ini', shell="/bin/bash")
    local('git add .')


@task
def tar_from_git(branch):
    local("pwd")
    local('find . -path ./\.git -prune -o -name \.gitignore -type f -exec rm -f {} \;')
    local('echo "%s.tar.*" >> .gitignore' % TAR_NAME)
    local('echo "fabfile.*" >> .gitignore')
    local('rm -rf %s.tar.gz' % TAR_NAME)
    local('git archive %s --format=tar.gz --output=%s.tar.gz' %
          (branch, TAR_NAME))

@task
def clean_up():
    local('git reset --hard ${GIT_COMMIT}')
    local('git clean -fdq')


@task
def unpack_code():
    cmd = "mkdir -p " + UPLOAD_CODE_PATH
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
        # keep onlly 5 most recent deploys, excluding any symlinks or other purely alpha directories. The steps are
        #  1. generate list of directories, sorted by modification time.
        #  2. reemove anything tha tdoes not have a "2" in it, e.g. the millenia (leftmost digit of the 4 digit year)
        #  3. keep the 5 most recent - these become the ones to keep.
        #  4. add a listing of all directories to these top 5.
        #  5. sort the combined listing
        #  6. keep only directory names that are *not* repeated - so this will be all directories beyond those first 5 numeric directories.
        #  7. filter out any alpha directories that were added by the second ls.
        #  8. remove all of the directories that remain.
        sudo('(ls -t|grep 2|head -n 5;ls)|sort|uniq -u|grep 2|xargs rm -rf')


@task
def pip_install():
    with cd('/data/deploy/pending'):
        sudo('pip install -r requirements.txt')

@task
def yarn_install(installPath):

    try:
        with cd("/data/deploy/pending/%s" % installPath):
            sudo('yarn --no-progress --non-interactive install')
    except FabricException:
        pass

@task
def download_nltk_data():
    run("echo 'loading NLTK data specified in nltk.txt'")
    sudo_app(
        'if [[ -f nltk.txt ]]; then mkdir -p /usr/share/nltk_data/; cat nltk.txt | while read -r line; do python -m nltk.downloader -d /usr/share/nltk_data ${line}; done; fi')


@task
def collect_static():
    with cd('/data/deploy/pending'):
        sudo('if [[ ! -d static ]]; then mkdir static/ ;fi')
        sudo('chmod 777 static')
        sudo('python manage.py collectstatic --noinput')



@task
# https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-check
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


# This assumes the local repo is ready (any build has been done and commited), then creates the tarball, finally deploys one at a time 
@task
def deploycode(branch, nltkLoad="False", doCollectStatic="True"):
    tar_from_git(branch)
    remote_inflate_code()

    if not yarn in TRUTH_VALUES:
        pip_install()

    if nltkLoad in TRUTH_VALUES:
        download_nltk_data()

 # Either do a django collectstatic, or at least collect django admin static assets (except for yarn deploys)
    if doCollectStatic in TRUTH_VALUES:
        collect_static()
    else:
        if not yarn in TRUTH_VALUES:
            sudo('cp -r ' + '/usr/local/opt/python/lib/python2.7/site-packages' +
                 '/django/contrib/admin/static/admin /data/deploy/pending/static/')


# This deploy assumes the tar ball ha been created (and any build steps done prior), then deploys all targets in parallel
@task
@parallel
def deployParallel(nltkLoad="False", doCollectStatic="True", yarn="False"):
    remote_inflate_code()

    if not yarn in TRUTH_VALUES:
        pip_install()

    if nltkLoad in TRUTH_VALUES:
        download_nltk_data()

# Either do a django collectstatic, or at least collect django admin static assets (except for yarn deploys)
    if doCollectStatic in TRUTH_VALUES:
        collect_static()
    else:
        if not yarn in TRUTH_VALUES:
            sudo('cp -r ' + '/usr/local/opt/python/lib/python2.7/site-packages' +
                 '/django/contrib/admin/static/admin /data/deploy/pending/static/')


@task
def dbmigrate_node(installPath):

    pathToUse = '/data/deploy/pending/' + installPath + "/dist"

    with cd(pathToUse):
        run('pwd')
        run('npm run migrate')

    

@task
@parallel
def dbmigrate(migrateOptions=None):
    cmdToRun = "cd /data/deploy/pending && python manage.py migrate --noinput"

    if migrateOptions is not None:
        cmdToRun += " " + migrateOptions

    run(cmdToRun)

# todo: deprecate this task
@task
def dbmigrate_docker(containerid, codepath='/data/deploy/current'):
    run('docker exec -it %s /bin/bash -c "cd /data/deploy/current && python manage.py migrate --noinput --ignore-ghost-migrations"' % containerid)


#
# These atomic tasks for putting the new deploy into effect are preferred, as they
# may run in parallel, while minimizing the exposure between the swap_code and putting the new code into effect
#
supervisor = "/usr/bin/supervisorctl"


@task
def swap_code():
    try:
        sudo('unlink /data/deploy/current')
    except:
        pass

    sudo("ln -s $(readlink /data/deploy/pending) /data/deploy/current")


@task
@parallel
def reload_web(doCollectStatic=None):
    swap_code()
    if doCollectStatic in TRUTH_VALUES:
        collect_static()

    reload_nginx()
    reload_uwsgi()


@task
@parallel
def restart_web(doCollectStatic=None):
    swap_code()
    if doCollectStatic in TRUTH_VALUES:
        collect_static()

    restart_nginx()
    restart_uwsgi()


@task
@parallel
def reload_worker(async="djangorq", doCollectStatic=None):
    swap_code()
    if doCollectStatic in TRUTH_VALUES:
        collect_static()

    if async == "djangorq":
        reload_djangorq()
    elif async == "celery":
        restart_celery()
    else:
        logger.info("Specified async facility not supported")


@task
@parallel
def restart_worker(async="djangorq", doCollectStatic=None):
    swap_code()
    if doCollectStatic in TRUTH_VALUES:
        collect_static()

    if async == "djangorq":
        restart_djangorq()
    elif async == "celery":
        restart_celery()
    else:
        logger.info("Specified async facility not supported")


@task
@parallel
def reload_node(processName):
    swap_code()

    sudo("%s restart %s" % (supervisor, processName))


@task
def reload_nginx():
    sudo("/usr/local/nginx/sbin/nginx -s reload")


@task
def reload_uwsgi():
    sudo("/bin/bash -c 'echo c > /tmp/uwsgififo'")


@task
def reload_djangorq():
    sudo(
        "for process in $(ps -ef|grep rq|grep -v grep|awk '{print $2}'); do kill -INT ${process}; done")


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
def restart_pgpool():
    sudo("%s restart pgpool" % supervisor)


@task
def run_cmd(cmdToRun):
    run(cmdToRun)


@task
def sudo_cmd(cmdToRun):
    sudo(cmdToRun)


@task
def run_app(cmdToRun, stopOnError="True"):
    if stopOnError in TRUTH_VALUES:
        with cd('/data/deploy/pending'):
            run(cmdToRun)
    else:
        with settings(abort_exception=FabricException):
            try:
                with cd('/data/deploy/pending'):
                    run(cmdToRun)
            except FabricException:
                pass


@task
def sudo_app(cmdToRun):
    with cd('/data/deploy/pending'):
        sudo(cmdToRun)

