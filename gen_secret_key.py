#!/usr/bin/env python

# Generates a 24-byte random base64-encoded string, which can be used as a
# Flask secret key.
import base64
import os

key = os.urandom(24)
print(base64.b64encode(key))
