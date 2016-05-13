#!/usr/bin/python2

import os
from mintupload_core import *

services = read_services()
if len(services) > 0:
    os.system("/usr/lib/linuxmint/mintupload/file-uploader.py &")
