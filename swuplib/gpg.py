#!/usr/bin/python
# simple gpg wrapper by oysteivi
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
import os
from swuplib import ex

# define some defaults
gnupgdir = '/etc/swup/gnupg'
true, false = 1, 0

def checksig (filename, gnupgdir = gnupgdir, keyring = None):
    """Checks the signature for a specified file.
    
    Takes the filename of the signature and an optional gnupg homedir.
    Returns true and the output of the gpg command (tuple) if the
    signature was verifiable, raises hell if not.
    """
    
    command = "gpg --no-permission-warning --no-tty --homedir %s " %gnupgdir
    if keyring:
        command += " --keyring %s " %keyring
    command += " --verify " + "'%s'" %filename  + " 2>&1"
    
    fd = os.popen(command)
    output = fd.read()
    retval = fd.close()
    
    if retval == None:
        return true, output
    else:
        raise ex.signature_error, filename



def import_key (filename, gnupgdir = gnupgdir):
    """Adds a key to the gnupg pubring.

    The filename of the key is the first argument. The second is 
    optionally the gnupg homedir to be used.

    If the key was already imported, the function is successful, but 
    nothing happens.
    
    Returns true, and the output of the gpg command, if the key was 
    successfully added, raises an exception if not.
    """
    #
    # Make sure we have a valid gnupg dir:
    #
    import os
    if not os.path.isdir(gnupgdir):
        os.makedirs(gnupgdir)
    
    command = "gpg --no-permission-warning --no-tty --homedir " + \
              gnupgdir + " --import " + filename + " 2>&1"

    fd = os.popen(command)
    output = fd.read()
    retval = fd.close()
    if retval == None:
        return true, output
    else:
        output = "Bad return value from gpg: %s \n" %retval + output
        raise ex.import_key_error, output

def delete_key (keyid, gnupgdir = gnupgdir):
    """Deletes gpg key

    Search string passed to gpg is the first argument. The second is
    optionally the gnupg homedir to be used.

    Gpg asks user for confirmation. If no is answered the function is 
    successful, but nothing happens.

    Raises an exception if something goes astray.
    """
    
    command = "gpg --no-permission-warning --homedir " + \
              gnupgdir + " --delete-keys " + keyid + " 2>&1"

    fd = os.popen(command)
    output = fd.read()
    retval = fd.close()
    if retval == None:
        return true, output
    else:
        output = "Bad return value from gpg: %s \n" %retval + output
        raise ex.delete_key_error, output



def list_keys (gnupgdir = gnupgdir, keyring = None):
    """List keys in gnupg pubring. Takes one optional argument to
    specify gnupg homedir where keys are found.
    """

    command = "gpg --no-permission-warning --no-tty --homedir %s " %gnupgdir
    if keyring:
        command += "--keyring %s " %keyring
    command += " --list-public-keys 2>&1"
    fd = os.popen(command)
    output = fd.read()
    retval = fd.close()

    if retval == None:
        return true, output
    else:
        output = "Bad return value from gpg: %s \n" %retval + output
        raise ex.list_keys_error, output




def gpg_signfile(pgppassfile, pgpid, pgphomedir, file, outfile=''):
    """ Signs a single specified file if given a password file, 
        pgp key id and a pgphomedir """
    if not pgppassfile == None and not pgpid == None and not pgphomedir == None:
        if outfile == '':
            outfile = file+".asc"
        good_sign = 1
        try:
            rpm_stat = os.stat(file)
            asc_stat = os.stat(outfile)
            rpm_time = rpm_stat[8]
            asc_time = asc_stat[8]
            if rpm_time > asc_time:
                os.remove(outfile)
                good_sign = 0
        except OSError:
            good_sign = 0
            pass
        except:
            raise
        if not good_sign:
            command = "cat %s | " %pgppassfile +\
            "gpg --no-permission-warning --homedir %s " %pgphomedir +\
            "--detach-sign --armor --no-secmem-warning --no-tty --batch "+\
            "--default-key %s " %pgpid +\
            ' -o "%s" ' %outfile +\
            '--passphrase-fd 0 "%s"' %file
            fd = os.popen(command)
            fd.close()


