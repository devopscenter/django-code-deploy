#project setup http://peterdowns.com/posts/first-time-with-pypi.html

#https://packaging.python.org/en/latest/distributing.html#uploading-your-project-to-pypi
python setup.py sdist

#https://packaging.python.org/en/latest/distributing.html#uploading-your-project-to-pypi
twine upload dist/*


