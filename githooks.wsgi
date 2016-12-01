# vim:ft=python:
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..')))
from githooks import app as application
