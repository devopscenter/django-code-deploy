# django-code-deploy
This module deploys django code to AWS instances, making use of [fab](http://docs.fabfile.org). This is a simple way to remove infrastructure dependencies (such as number and IP addresses of target instances) from the app repo itself. By no means complete, but may be a helpful step.

## Setup
First add this simplified fabfile.py to the root of your project:
```python
from django_code_deploy import fabfile as deploy
```

That's it, your project now has all it needs to be deployed.

Then you'll need to pip install django-code-deploy wherever fab will run (e.g. a jenkins server). For example,
```bash
sudo pip install django-code-deploy
```
## Tag instances
Finally, you'll need to make sure that your instances have these 3 standard tags, since django-code-deploy works by looking for all instances that match a specified set of tags. These tags are:
* **Type** - the type of instance, such as web, worker, db.
* **Env** - the environment name, such as dev, staging, prod.
* **App** - the application name, such as "fresco", "topopps", "mojo", etc.

## Usage
Here's a example set of commands for deploying an app:
```bash
fab deploy.dev deploy.set_hosts:type=web,appname=test,region=us-west-2 deploy.deploycode:branch=dev deploy.dbmigrate
fab deploy.dev deploy.set_hosts:type=web,appname=test,region=us-west-2 deploy.restart_celery deploy.restart_uwsgi deploy.restart_nginx
```
Since this was running as a jenkins job, it assumes that the git repo was updated before it ran. With that in mind, this 
* set the envronment to 'dev'
* obtained a list of all instances in the default region of type 'web', app name 'test', and env 'dev'.
* deployed the dev branch of the repo that had previously been obtained by jenkins
* ran db migrations
* restarted celery
* restarted uwsgi
* restarted nginx

Note that the deploycode method also performs a collectstatic step before returning.
## Complete list of fab methods and arguments
This is a complete list of the invocable methods, and arguments that may be specified in each one.
```python
set_hosts(type,             #type is web, worker, db
  primary=None,
  appname=None,             #appname is application name, such as "fresco", "topopps", "mojo", etc.
  region=None               #region is aws region
```
These next three set AWS_ENVIRONMENT (os-level env var) to either dev, staging, or prod.
```python
dev()
staging()
prod()
set_environment(anEnv)  For an environment that is not one of dev, staging or prod
```

Use the set_access_key() to the location and file that is the private access key to be used to access the instance
set_access_key('/path/to/theKey')

These are the main methods to use in a deploy.
```python
deploycode(branch)
dbmigrate()
restart_nginx()
restart_uwsgi()
restart_celery()
```
Other methods:
```python
dbmigrate_docker(containerid,codepath='/data/deploy/current')
django_check()
codeversioner()
```

## Other notes
* The code is deployed in directories organized like this, one per deploy: /data/deploy/*today's date* ... the newest deploy will be symlinked to /data/deploy/current/
* As is the nature of fab, the instances are processed one at a time. No attempt has been made to do the actual deploys in parallel.

* (c) 2015 - 2018, devops.center llc.
