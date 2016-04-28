# django-code-deploy
This module deploys django code to AWS instances, making use of [fab](http://docs.fabfile.org).

## Setup
First add aws_settings.py to the root of your project, with these two entries:
```python
AWS_REGION='us-west-2'
APP_NAME='name-of-your-app'
```
note that these values are only defaults, and may be overridden when actually deploying via fab.

Then add this simplified fabfile.py to the root of your project:
```python
from django_code_deploy import fabfile as deploy
```

That's it, your project now has all it needs to be deployed.

Then you'll need to pip install django-code-deploy wherever fab will run (e.g. a jenkins server). For example,
```bash
sudo pip install django-code-deploy
```

## Usage

