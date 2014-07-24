#!/usr/bin/env python

import os
from mintUploadCore import *

services = read_services()
if len(services) > 0:
    os.system("/usr/share/linuxmint/mintUpload/file-uploader.py &")
