#!/bin/bash -ev

python setup.py sdist

twine upload dist/*
 
