# -*- python -*-
# $Id: log.py,v 1.4 2001/03/20 11:40:18 olafb Exp $

#  Copyright 2001 Trustix As - <http://www.trustix.com>
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
        
import os, sys, string, syslog, time
true, false = 1, 0

LOGLEVEL_SILENT = 0
LOGLEVEL_QUIET = 1
LOGLEVEL_NORMAL = 5
LOGLEVEL_VERBOSE = 8
    
class LogException(Exception):
    def __init__(self, value=None):
        self.value = value
    def __str__(self):
        return self.value

class IOException(LogException): pass

# A class for logging messages to file, or the syslog.
# Input: path & filename for the swup logfile
class log:
    def __init__( self, log_file_name, loglevel,
                  is_interactive_logged=true ):
        self.logfile = log_file_name
        self.is_interactive_logged = is_interactive_logged
        self.isatty_stdout = sys.stdout.isatty()
        self.isatty_stderr = sys.stderr.isatty()
        self.loglevel = loglevel
        
    #Write a log message to the swup log file
    def write_log( self,  message ):
        if (not self.is_interactive_logged) and self.isatty_stdout:
            return
        try:
            file = open( self.logfile, "a" )
        except IOError, errmsg:
            raise IOException, 'Can not open file for writing. %s' %\
                  self.logfile
        time_t = time.localtime(time.time())
        timestamp = time.strftime( "%a %d %b %Y %H:%M:%S", time_t )
        log_message = timestamp + " " + message + "\n"
        file.write( log_message )
        file.flush()
        file.close()

    # Write a message to the syslog
    def write_syslog( self, message, priority = syslog.LOG_INFO ):
        # should we write the pid in the syslog message?
        syslog.openlog( "swup" ) #, options, facility )
        syslog.syslog ( priority, message )
        syslog.closelog()

    def write_syslog_emerg( self, message ):
        self.write_syslog( message, priority = syslog.LOG_EMERG )

    def write_syslog_alert( self, message ):
        self.write_syslog( message, priority = syslog.LOG_ALERT )

    def write_syslog_crit( self, message ):
        self.write_syslog( message, priority = syslog.LOG_CRIT )

    def write_syslog_err( self, message ):
        self.write_syslog( message, priority = syslog.LOG_ERR )

    def write_syslog_warning( self, message ):
        self.write_syslog( message, priority = syslog.LOG_WARNING )

    def write_syslog_notice( self, message ):
        self.write_syslog( message, priority = syslog.LOG_NOTICE )

    def write_syslog_info( self, message ):
        self.write_syslog( message, priority = syslog.LOG_INFO )

    def write_syslog_debug( self, message ):
        self.write_syslog( message, priority = syslog.LOG_DEBUG )

        
    #write a message to stdout
    def write_stdout( self, message, newline=true ):
        if self.loglevel > LOGLEVEL_SILENT:
            if newline:
                message = message + '\n'
            sys.stdout.write( message )
            sys.stdout.flush()
        else :
            # no output
            pass

    def write_stdout_info( self, message, newline=true ):
        if self.loglevel > LOGLEVEL_QUIET:
            if newline:
                message = message + '\n'
            sys.stdout.write( message )
            sys.stdout.flush()
        else :
            # no output
            pass
        

    def write_stdout_verbose( self, message, newline=true ):
        if self.loglevel >= LOGLEVEL_VERBOSE:
            if newline:
                message = message + '\n'
            sys.stdout.write( message )
            sys.stdout.flush()
        else:
            # no verbose output
            pass


    def write_tty( self, message ):
        if self.isatty_stdout and self.loglevel > LOGLEVEL_QUIET:
            sys.stdout.write( message )
            sys.stdout.flush()
        
    #write a message to stderr
    def write_stderr( self, message ):
            sys.stderr.write( message +'\n' )
            sys.stderr.flush()


