# -*- python -*-
# $Id: swup.py,v 1.75 2005/07/20 14:41:58 christht Exp $

#  Copyright 2001 - 2003 Trustix AS - <http://www.trustix.com>
#  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


import sys, string, os, re, errno
from swuplib import cmdline
from swuplib import config
from swuplib import log
from swuplib import help
from swuplib import ex
from swuplib import utils


def parse_argv(argv):
    '''Parse command line arguments. Return dictionary with switch as key.'''
    try:
        argdict = cmdline.parse(argv)
    except ex.cmdline_unknown_error, option:
        raise ex.cmdline_error, "Unknown option: %s" % option
    except ex.wrong_number_of_args_error, switch:
        raise ex.cmdline_error, "Wrong number of arguments for switch: %s"\
              % switch
    except ex.too_many_operations_error, operations:
        raise ex.cmdline_error, "Too many operations:\n%s" %operations
    except ex.too_few_operations_error, message:
        raise ex.cmdline_error, "Too few operations: %s" % message
    except:
        raise
    return argdict

def import_key(filenames, gnupgdir):
    '''Given a list of local filenames that contains gnupg key(s) and the 
    dictionary in which the keyring is stored, import key(s) into keyring.'''
    for filename in filenames:
        if os.path.isfile(filename):
            try:
                from swuplib import gpg
                (retval, output) = gpg.import_key(filename, gnupgdir)
                sys.stdout.write("Import of key(s) succeded.\n")
            except ex.import_key_error, errmsg:
                raise ex.import_key_error, errmsg
            except:
                raise
        else:
            raise ex.import_key_error, "No such file '%s'" % filename

def delete_key(keyids, gnupgdir):
    '''Deletes key(s) from keyring.'''
    try:
        from swuplib import gpg
        for keyid in keyids:
            (retval, output) = gpg.delete_key(keyid, gnupgdir)
    except ex.delete_key_error, errmsg:
       raise ex.delete_key_error, errmsg
    except:
        raise

def list_keys(gnupgdir, keyring=""):
    '''Given a directory where the gnupg keyring is stored, list the keys
    in the keyring.'''
    try:
        from swuplib import gpg
        (retval, output) = gpg.list_keys(gnupgdir, keyring)
        sys.stdout.write(output)
    except ex.list_keys_error, errmsg:
        raise ex.list_keys_error, errmsg
    except:
        raise

def lock_ignored(config):
    if config.has_key('ignore_lock') and config['ignore_lock'] == "yes":
        return True
    return False

def check_lock(config):
    if os.path.exists(os.path.join(config['cachedir'],'.lock')):
        fd = open(os.path.join(config['cachedir'],'.lock'))
        input = fd.readline().strip()
        fd.close()
        try:
            pid = int(input)
        except ValueError:
            #this means that a lockfile exists, but contains no pid
            #probably swup died before it wrote the pid.
            return False
        except:
            raise
        if pid_isrunning(pid):
            return pid
    return False

def pid_isrunning(pid):
    ''' Returns true if given pid is running, else false. '''
    try:
        os.kill(pid, 0)
        return 1
    except OSError, err:
         return err.errno == errno.EPERM

def set_lock(config):
    if lock_ignored(config):
        return True
    cachedir = config['cachedir']
    lockfile = os.path.join(os.path.join(cachedir,'.lock'))
    pid = check_lock(config)
    if not pid:
        if not os.path.isdir(cachedir):
            os.makedirs(cachedir)
        fd = open(lockfile, 'w')
        fd.write(str(os.getpid()))
        fd.close()
        return True
    else:
        message = \
"""Error: Lockfile %s exists. Exiting. 

Swup seems to be running with pid %s.
The file may be manually removed, but only do this if you are sure that you
are not running any other swup processeses.
""" %(lockfile,pid)
        sys.stderr.write(message)

    return False

def remove_lock(config):
    if lock_ignored(config):
        return True
    lockfile = os.path.join(os.path.join(config['cachedir'],'.lock'))
    if os.path.exists(lockfile):
        try:
            os.remove(lockfile)
        except IOError:
            return False
        except:
            raise
    return True
    
    
def setup(argdict):
    '''Analyze argument dictionary, return (mode, args, config)
    where mode is a string, args is a list of strings and config is
    a dictionary of configuration variables with variable name as key.'''

    # did user request help or version info?
    if argdict.has_key('--help'):
        return ('help', None, None)
    if argdict.has_key('--version'):
        return ('version', None, None)
    if argdict.has_key('--copyright'):
        return ('copyright', None, None)

    elif argdict.has_key('--config-file'):
        config_file = argdict['--config-file'][0]
    else:
        config_file = config.DEFAULT_CONFIG_FILE

    silent = 0
    full = True
    if argdict.has_key('--silent'):
        silent = 1
    # Some operations does not require location of latest.rdf:
    if argdict.has_key('--import-key') or \
        argdict.has_key('--delete-key') or \
        argdict.has_key('--list-keys'):
        full = False
    configuration = None
    try:
        configuration = config.parse(config_file, silent, full)
    except ex.io_error, errmsg:
        raise ex.setup_error, 'Unable to open config file: %s' % errmsg
    except ex.no_null_class_found_error, errmsg:
        if not argdict.has_key('--repository-URI'):
            raise ex.setup_error, str(errmsg)
    except ex.parse_error, message:
        raise ex.setup_error, '%s\n%s' % \
              ('Error in config file %s.' % config_file,
               'Parser said %s.' % message)
    except:
        raise

    # merge command line options with config
    if argdict.has_key('--silent'):
        configuration['loglevel'] = log.LOGLEVEL_SILENT 
    elif argdict.has_key('--quiet'):
        configuration['loglevel'] = log.LOGLEVEL_QUIET
    elif argdict.has_key('--notty'):
        configuration['loglevel'] = log.LOGLEVEL_NOTTY
    elif argdict.has_key('--verbose'):
        configuration['loglevel'] = log.LOGLEVEL_VERBOSE
    else:
        configuration['loglevel'] = log.LOGLEVEL_NORMAL
        
    if argdict.has_key('--stage'):
        configuration['loglevel'] = log.LOGLEVEL_PROGRESS

    if argdict.has_key('--repository-URI'):
        configuration['sites'] = []
        for uri in argdict['--repository-URI']:
            if not utils.is_absolute(uri):
                msg = "URI not supported:\n%s\n" %uri
                msg += "SWUP only understands: "
                msg += "http:// https:// ftp:// file://\n"
                sys.stderr.write(msg)
            else:
                configuration['sites'].append((0, uri, '.*', "cmdline", 1))
    #
    # Let's check the various sites submitted before we go on:
    #
    if not configuration['sites']:
        message = "No sites found.\n"\
            +"Please update the configuration or submit "\
            +"a site using the\n--repository-URI option."
        raise ex.setup_error, message
    null_found = False
    for site in configuration['sites']:
        pri = site[0]
        if pri == 0:
            null_found = True
    if not null_found:
        message = "No valid 'class = 0' sites found.\n"\
            +"Please update the configuration or submit "\
            +"a site using the\n--repository-URI option."
        raise ex.setup_error, message
    
        
    if argdict.has_key('--gnupg-dir'):
        configuration['gnupgdir'] = argdict['--gnupg-dir'][0]
        
    if argdict.has_key('--root'):
        newroot = argdict['--root'][0]
        configuration['root'] = newroot
        #
        # Make all used directories use root:
        #
        cd = "./%s" %configuration['cachedir']
        td = "./%s" %configuration['tmpdir']
        gd = "./%s" %configuration['gnupgdir']
        configuration['cachedir'] = os.path.normpath(os.path.join(newroot,cd))
        configuration['tmpdir'] = os.path.normpath(os.path.join(newroot,td))
        configuration['gnupgdir'] = os.path.normpath(os.path.join(newroot,gd))
        configuration['listsdir'] = \
            os.path.join(configuration['cachedir'], 'lists')
        configuration['md5sumfile'] = \
            os.path.join(configuration['cachedir'], 'md5sums')
        
    if argdict.has_key('--save-to'):
        todir = argdict['--save-to'][0]
        if not os.path.isdir( todir ):
            raise ex.setup_error, "No such directory '%s'" % todir
        else:
            configuration['save_to'] = todir
        

    if argdict.has_key('--ignore-lock'):
        configuration['ignore_lock'] = 'yes'
    else:
        configuration['ignore_lock'] = 'no'

    if argdict.has_key('--ignore-filter'):
        configuration['ignore_filter'] = 'yes'
    else:
        configuration['ignore_filter'] = 'no'

    if argdict.has_key('--ignore-manual-upgrade'):
        configuration['ignore_manual_upgrade'] = 'yes'
    else:
        configuration['ignore_manual_upgrade'] = 'no'

    if argdict.has_key('--local-first'):
        configuration['local_first'] = 'yes'

    if argdict.has_key('--force'):
        configuration['force'] = 'yes'

    poll_only = False
    download_only = False

    configuration['no_swupgrade'] = False
    if argdict.has_key('--poll-only'):
        configuration['poll_only'] = 'yes'
        configuration['no_swupgrade'] = True
    if argdict.has_key('--download-only'):
        configuration['download_only'] = 'yes'
        configuration['no_swupgrade'] = True

    if argdict.has_key('--download-first'):
        configuration['download_first'] = 'yes'

    if argdict.has_key('--import-key'):
        filenames = argdict['--import-key']
        return ('import_key', filenames, configuration)

    if argdict.has_key('--delete-key'):
        keyids = argdict['--delete-key']
        return ('delete_key', keyids, configuration)


    if argdict.has_key('--list-keys'):
        return ('list_keys', None, configuration)

    #
    # Stages:
    #
    if argdict.has_key('--stage'):
        configuration['stage'] = True
        configuration['download_first'] = 'yes'

    packages = []

    if argdict.has_key('--install'):
        packages.extend(argdict['--install'])
    if argdict.has_key('--remove'):
        packages.extend(argdict['--remove'])
    if argdict.has_key('--upgrade'):
        packages.extend(argdict['--upgrade'])
    if argdict.has_key('--package'):
        if len(packages) < 1:
            packages.extend(argdict['--package'])
    if argdict.has_key('--package-file'):
        try:
            package_file = open(argdict['--package-file'][0])
            package_file_list = package_file.readlines()
            #package_file_list.remove('')
            packages.extend(package_file_list)
            package_file.close()
        except IOError: 
            raise ex.setup_error, "Unable to open file: %s" %\
                argdict['--package-file'][0]
        except:
            raise

    if argdict.has_key('--package-URI'):
        packages.extend(argdict['--package-URI'])

    if argdict.has_key('--package-URI-file'):
        try:
            package_uri_file = \
            open(argdict['--package-URI-file'][0])
            package_uri_file_list = package_uri_file.readlines()
            #package_uri_file_list.remove("")
            packages.extend(package_uri_file_list)
            package_uri_file.close()
        except IOError: 
            raise ex.setup_error, "Unable to open URI-file: %s" %\
                argdict['--package-file'][0]
        except:
            raise

    # prettify list
    for i in range(len(packages)):
        packages[i] = string.strip(packages[i])

    # create the installation object

    if argdict.has_key('--upgrade'):
        if packages == []:
            mode = 'upgrade_normal'
        else:
            mode = 'upgrade_package'
        return (mode, packages, configuration)

    elif argdict.has_key('--install'):
        if packages == []:
            raise ex.setup_error, \
                  'You need to specify at least one package to install.'
        return ('install', packages, configuration)

    elif argdict.has_key('--remove'):
        if packages == []:
            raise ex.setup_error, \
                  'You need to specify at least one package to remove.'
        return ('remove', packages, configuration)

    elif argdict.has_key('--search-package'):
        searchpattern = argdict['--search-package'][0]
        return ('search_package', searchpattern, configuration)

    elif argdict.has_key('--search-resource'):
        searchpattern = argdict['--search-resource'][0]
        return ('search_resource', searchpattern, configuration)

    elif argdict.has_key('--search-file'):
        searchpattern = argdict['--search-file'][0]
        return ('search_file', searchpattern, configuration)
    
    elif argdict.has_key('--list-latest'):
        return ('list_latest', None, configuration)

    elif argdict.has_key('--list-new'):
        return ('list_new', None, configuration)
        
    # Sometime in the future this should go away
    elif argdict.has_key('--list-prospect'):
        return ('list_new', None, configuration)
        
    elif argdict.has_key('--list-alien'):
        return ('list_alien', None, configuration)
        
    elif argdict.has_key('--list-upgrade'):
        return ('list_upgrade', None, configuration)
        
    elif argdict.has_key('--list-downgrade'):
        return ('list_downgrade', None, configuration)
    
    elif argdict.has_key('--flush-cache'):
        return ('flush_cache', None, configuration)

    elif argdict.has_key('--remove-lock'):
        return ('remove_lock', None, configuration)

    elif argdict.has_key('--describe'):
        configuration['descriptor'] = argdict['--describe'][0]
        return ('describe', None, configuration)
    
    elif argdict.has_key('--what-provides'):
        configuration['descriptor'] = argdict['--what-provides'][0]
        return ('what_provides', None, configuration)

    else:
        raise ex.setup_error, "Setup failed to detect mode!\nThis should not happen."


def main(argv):
    'Main interface. Takes list of command line arguments as argument.'
    swupgrade = False
    autoboot = False

    # Parse the command line arguments.
    try:
        argdict = parse_argv(argv)
    except ex.cmdline_error, errmsg:
        sys.stderr.write('%s\n' % errmsg)
        sys.exit(2)
    except:
        raise

    # Setup the configuration and get the mode in which we are supposed to
    # run.
    try:
        mode, args, config = setup(argdict)
    except ex.setup_error, errmsg:
        sys.stderr.write('%s\n' % errmsg)
        sys.exit(2)
    except:
        raise

    # Check for the simpler modes that does not involve the upgrade module.
    if mode == 'help':
        help.helpme()
        sys.exit(0)
    elif mode == 'version':
        help.version()
        sys.exit(0)
    elif mode == 'copyright':
        help.copyright()
        sys.exit(0)
    elif mode == 'remove_lock':
        remove_lock(config)
        sys.exit(0)
    elif mode == 'import_key':
        if set_lock(config):
            try:
                import_key(args, config['gnupgdir'])
                remove_lock(config)
                sys.exit(0)
            except ex.import_key_error, errmsg:
                sys.stderr.write('%s\n' % errmsg)
                remove_lock(config)
                sys.exit(2)
            except:
                remove_lock(config)
                raise
    elif mode == 'delete_key':
        if set_lock(config):
            try:
                delete_key(args, config['gnupgdir'])
                remove_lock(config)
                sys.exit(0)
            except ex.delete_key_error, errmsg:
                sys.stderr.write('%s\n' % errmsg)
                remove_lock(config)
                sys.exit(2)
            except:
                remove_lock(config)
                raise
    elif mode == 'list_keys':
        try:
            list_keys(config['gnupgdir'], config['keyring'])
            sys.exit(0)
        except ex.list_keys_error, errmsg:
            sys.stderr.write('%s\n' % errmsg)
            sys.exit(1)
        except:
            raise

    # The mode requires the upgrade module. Initialize an upgrade agent
    # and run.

    import upgrade
    from swuplib import download
    agent = None
    try:
        if mode == 'upgrade_normal':
            if not set_lock(config):
                sys.exit(1)
            agent = upgrade.Upgrade(config)
        elif mode == 'upgrade_package':
            if not set_lock(config):
                sys.exit(1)
            config['local_first'] = "yes"
            agent = upgrade.upgrade_package(args, config)
        elif mode == 'install':
            if not set_lock(config):
                sys.exit(1)
            agent = upgrade.install_package(args, config)
        elif mode == 'remove':
            if not set_lock(config):
                sys.exit(1)
            from erase import Erase
            agent = Erase(args, config)
        elif mode == 'list_latest':
            agent = upgrade.list_latest(config)
        elif mode == 'list_new':
            agent = upgrade.list_new(config)
        elif mode == 'list_alien':
            agent = upgrade.list_alien(config)
        elif mode == 'list_upgrade':
            agent = upgrade.list_upgrade(config)
        elif mode == 'list_downgrade':
            agent = upgrade.list_downgrade(config)
        elif mode == 'search_package':
            agent = upgrade.search_package(args, config)
        elif mode == 'search_resource':
            agent = upgrade.search_resource(args, config)
        elif mode == 'search_file':
            agent = upgrade.search_file(args, config)
        elif mode == 'flush_cache':
            if not set_lock(config):
                sys.exit(1)
            agent = download.Flush( config )
        elif mode == 'describe':
            agent = upgrade.describe( config )
        elif mode == 'what_provides':
            agent = upgrade.what_provides( config )
    except ex.upgrade_error, err:
        sys.stderr.write('Failed to initialize: %s\n' % err)
        sys.exit(1)
    except:
        raise
    
    try:
        if agent:
            result = agent.run()
            remove_lock(config)
            if result == 1:
                swupgrade = True
                #
                # Swup was upgraded, most likely with close friends only.
                # Let's flush cache before we restart swup:
                #
                agent = download.Flush( config )
                agent.run()
            elif result == 2:
                autoboot = True
        else:
            sys.stderr.write('No agent! This should never happen.\n')
    except KeyboardInterrupt:
        remove_lock(config)
        raise KeyboardInterrupt
    except ex.upgrade_error:
        remove_lock(config)
        sys.exit(1)
    except:
        remove_lock(config)
        raise

    # All went ok if we got here. Exit normally.
    if swupgrade and not config['no_swupgrade']:
        return (1, None)
    elif autoboot and config['auto_reboot'] == "yes":
        return (2, config['reboot_delay'])
    else:
        return (0, None)


if __name__ == '__main__':
    main(sys.argv[1:])

