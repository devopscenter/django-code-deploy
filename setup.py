from distutils.core import setup
setup(
  name = 'django-code-deploy',
  packages = ['django_code_deploy'], # this must be the same as the name above
  version = '0.9.88',
  description = 'Deploys Django code to AWS based on tags',
  author = 'Josh devops.center, Bob devops.center, Gregg devops.center',
  author_email = 'josh@devops.center, bob@devops.center, gjensen@devops.center',
  url = 'https://github.com/devopscenter/django-code-deploy', # use the URL to the github repo
  download_url = 'https://github.com/devopscenter/django-code-deploy/tarball/0.1', # I'll explain this in a second
  keywords = ['testing', 'logging', 'example'], # arbitrary keywords
  classifiers = [],
)
