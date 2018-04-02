from distutils.core import setup
setup(
    name='django-code-deploy',
    packages=['django_code_deploy'],  # this must be the same as the name above
    version='0.9.97',
    description='Deploys Django code to AWS based on tags',
    author='Josh devops.center, Bob devops.center, Gregg devops.center',
    author_email='josh@devops.center, bob@devops.center, gjensen@devops.center',
    # use the URL to the github repo
    url='https://github.com/devopscenter/django-code-deploy',
    # I'll explain this in a second
    download_url='https://github.com/devopscenter/django-code-deploy/tarball/0.1',
    keywords=['testing', 'logging', 'example'],  # arbitrary keywords
    classifiers=[],
)
