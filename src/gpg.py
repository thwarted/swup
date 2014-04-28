#!/usr/bin/env python
# simple gpg wrapper by oysteivi
import os

# define some defaults
gnupgdir = '/etc/swup/gnupg'
true, false = 1, 0

# define some exceptions
signature_fail = 'gpg.signature_fail'
key_import_failure = 'gpg.key_import_failure'
list_keys_failure = 'gpg.list_keys_failure'

# A general error which includes all availible errors
# nice as a security net or for lazy programmers...
general_error = \
(signature_fail, key_import_failure, list_keys_failure)


def checksig (filename, gnupgdir = gnupgdir):
	"""Checks the signature for a specified file.
	
	Takes the filename of the signature and an optional gnupg homedir.
	Returns true and the output of the gpg command (tuple) if the
	signature was verifiable, raises hell if not.
	"""
	
	command = "gpg --no-tty --homedir " + \
	gnupgdir + " --verify " + "'%s'" %filename  + " 2>&1"
	
	fd = os.popen(command)
	output = fd.read()
	retval = fd.close()
	
	if retval == None:
		return true, output
	else:
		raise signature_fail, output



def import_key (filename, gnupgdir = gnupgdir):
	"""Adds a key to the gnupg pubring.

	The filename of the key is the first argument. The second is 
	optionally the gnupg homedir to be used.

	If the key was already imported, the function is successful, but 
	nothing happens.
	
	Returns true, and the output of the gpg command, if the key was 
	successfully added, raises an exception if not.
	"""
	
	command = "gpg --no-tty --homedir " + \
		  gnupgdir + " --import " + filename + " 2>&1"

	fd = os.popen(command)
	output = fd.read()
	retval = fd.close()
	if retval == None:
		return true, output
	else:
		raise key_import_failure, output



def list_keys (gnupgdir = gnupgdir):
	"""List keys in gnupg pubring. Takes one optional argument to
	specify gnupg homedir where keys are found.
	"""

	command = "gpg --no-tty --homedir " + \
		  gnupgdir + " --list-public-keys " + "2>&1"
	fd = os.popen(command)
	output = fd.read()
	retval = fd.close()

	if retval == None:
		return true, output
	else:
		raise list_keys_failure, output
