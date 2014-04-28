#!/usr/bin/env python

import sys, string, os, re
import help, cmdline, config, log

true, false = 1, 0

# Exceptions
class SwupException(Exception):
    def __init__(self, value=None):
        self.value = value
    def __str__(self):
        return self.value

class ConfigException(SwupException): pass
class CmdlineException(SwupException): pass
class SetupException(SwupException): pass
class ImportKeyException(SwupException): pass
class ListKeysException(SwupException): pass


def parse_argv(argv):
    '''Parse command line arguments. Return dictionary with switch as key.'''
    try:
        argdict = cmdline.parse(argv)
    except cmdline.unknown, option:
        raise CmdlineException, "Unknown option: %s" % option
    except cmdline.wrong_number_arguments, switch:
        raise CmdlineException, "Wrong number of arguments for switch: %s"\
              % switch
    except cmdline.too_many_operations, (operation1, operation2):
        raise CmdlineException, "Too many operations: %s %s" %\
              (operation1, operation2)
    except cmdline.too_few_operations, message:
        raise CmdlineException, "Too few operations: %s" % message
    return argdict


def import_key(filename, gnupgdir):
    '''Given a local filename that contains a gnupg key and the dictionary
    in which the keyring is stored, import key into keyring.'''
    if os.path.isfile(filename):
        try:
            import gpg
            (retval, output) = gpg.import_key(filename, gnupgdir)
            sys.stdout.write("Import of key(s) succeded.\n")
        except gpg.key_import_failure, errmsg:
            raise ImportKeyException, errmsg
    else:
        raise ImportKeyException, "No such file '%s'" % filename


def list_keys(gnupgdir):
    '''Given a directory where the gnupg keyring is stored, list the keys
    in the keyring.'''
    try:
        import gpg
        (retval, output) = gpg.list_keys(gnupgdir)
        sys.stdout.write(output)
    except gpg.list_keys_failure, errmsg:
        raise ListKeysException, errmsg
    
    
def setup(argdict):
    '''Analyze argument dictionary, return (mode, args, config)
    where mode is a string, args is a list of strings and config is
    a dictionary of configuration variables with variable name as key.'''
	
    # did user request help or version info?
    if argdict.has_key('--help'):
        return ('help', None, None)
    if argdict.has_key('--version'):
        return ('version', None, None)

    # get config
    if argdict.has_key('--config-file'):
	config_file = argdict['--config-file'][0]
    else:
	config_file = config.DEFAULT_CONFIG_FILE

    configuration = None
    try:
	configuration = config.parse(config_file)
    except config.ConfigParseError, message:
        raise SetupException, '%s\n%s' % \
              ('Error in config file %s.' % config_file,
               'Parser said %s.' % message)

    # merge command line options with config
    if argdict.has_key('--silent'):
	configuration['loglevel'] = log.LOGLEVEL_SILENT 
    elif argdict.has_key('--quiet'):
        configuration['loglevel'] = log.LOGLEVEL_QUIET
    elif argdict.has_key('--verbose'):
        configuration['loglevel'] = log.LOGLEVEL_VERBOSE
    else:
        configuration['loglevel'] = log.LOGLEVEL_NORMAL
        
    if argdict.has_key('--no-flush-cache'):
	configuration['flush_cache'] = 'no'
    if argdict.has_key('--repository-URI'):
	configuration['sites'] = [('0', argdict['--repository-URI'][0],
				       '.*')]
    if argdict.has_key('--gnupg-dir'):
	configuration['gnupgdir'] = argdict['--gnupg-dir'][0]
    if argdict.has_key('--save-to'):
        todir = argdict['--save-to'][0]
        if not os.path.isdir( todir ):
            raise SetupException, "No such directory '%s'" % todir
        else:
            configuration['save_to'] = todir
        
    if argdict.has_key('--import-key'):
	filename = argdict['--import-key'][0]
        return ('import_key', filename, configuration)


    if argdict.has_key('--list-keys'):
        return ('list_keys', None, configuration)


    poll_only = false
    download_only = false

    if argdict.has_key('--poll-only'):
	configuration['poll_only'] = 'yes'
    if argdict.has_key('--download-only'):
	configuration['download_only'] = 'yes'
	configuration['flush_cache'] = 'no'

    packages = []

    if argdict.has_key('--package'):
	packages.extend(argdict['--package'])
    if argdict.has_key('--package-file'):
	try:
	    package_file = open(argdict['--package-file'][0])
	    package_file_list = package_file.readlines()
	    #package_file_list.remove('')
	    packages.extend(package_file_list)
	    package_file.close()
	except IOError: 
            raise SetupException, "Unable to open file: %s" %\
                  argdict['--package-file'][0]

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
            raise SetupException, "Unable to open URI-file: %s" %\
                  argdict['--package-file'][0]

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
            raise SetupException, \
                  'You need to specify at least one package to install.'
        return ('install', packages, configuration)
    
    elif argdict.has_key('--list-latest'):
        return ('list_latest', None, configuration)

    elif argdict.has_key('--list-new'):
        return ('list_new', None, configuration)

    else:
        raise SetupExeption, "This should not happen."


def main(argv):
    'Main interface. Takes list of command line arguments as argument.'

    # Parse the command line arguments.
    try:
        argdict = parse_argv(argv)
    except CmdlineException, errmsg:
        sys.stderr.write('%s\n' % errmsg)
        sys.exit(2)

    # Setup the configuration and get the mode in which we are supposed to
    # run.
    try:
        mode, args, config = setup(argdict)
    except SetupException, errmsg:
        sys.stderr.write('%s\n' % errmsg)
        sys.exit(2)

    # Check for the simpler modes that does not involve the upgrade module.
    if mode == 'help':
        help.helpme()
        sys.exit(0)
    elif mode == 'version':
        help.version()
        sys.exit(0)
    elif mode == 'import_key':
        try:
            import_key(args, config['gnupgdir'])
            sys.exit(0)
        except ImportKeyException, errmsg:
            sys.stderr.write('%s\n' % errmsg)
            sys.exit(2)
    elif mode == 'list_keys':
        try:
            list_keys(config['gnupgdir'])
            sys.exit(0)
        except ListKeysException, errmsg:
            sys.stderr.write('%s\n' % errmsg)
            sys.exit(1)

    # The mode requires the upgrade module. Initialize an upgrade agent
    # and run.

    import upgrade
    agent = None
    try:
        if mode == 'upgrade_normal':
            agent = upgrade.Upgrade(config)
        elif mode == 'upgrade_package':
            agent = upgrade.upgrade_package(args, config)
        elif mode == 'install':
            agent = upgrade.install_package(args, config)
        elif mode == 'list_latest':
            agent = upgrade.list_latest(config)
        elif mode == 'list_new':
            agent = upgrade.list_new(config)
    except upgrade.UpgradeException, err:
        sys.stderr.write('Failed to initialize: %s\n' % err)
        sys.exit(1)
        
    try:
        if agent:
            agent.run()
        else:
            sys.stderr.write('This should never happen.\n')
    except upgrade.UpgradeException:
        sys.exit(1)

    # All went ok if we got here. Exit normally.
    sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])







