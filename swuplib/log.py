# -*- python -*-
# $Id: log.py,v 1.17 2005/06/13 09:04:18 christht Exp $

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
        
import os, sys, string, syslog, time
#Initialize Log level constants
LOGLEVEL_PROGRESS = -1
LOGLEVEL_SILENT = 0
LOGLEVEL_QUIET = 1
LOGLEVEL_NOTTY = 2
LOGLEVEL_NORMAL = 5
LOGLEVEL_VERBOSE = 8

# A class for logging messages to file, or the syslog.
# Input: path & filename for the swup logfile
class log:
    def __init__( self, loglevel, is_interactive_logged=True ):
        self.is_interactive_logged = is_interactive_logged
        self.isatty_stdout = sys.stdout.isatty()    #Checks File descriptor existence
        self.isatty_stderr = sys.stderr.isatty()    
        self.loglevel = loglevel

    def _write_stdout(self, message):
        ''' Writes a message to stdout with the system's encoding, or
        with ISO-8859-1 if python can't figure out the encoding'''
        try:
            sys.stdout.write(message)
            try:
                sys.stdout.flush()
            except IOError:
                pass
        except UnicodeError:  
            encoding = 'iso-8859-1'
            sys.stdout.write(message.encode(encoding))
            try:
                sys.stdout.flush()
            except IOError:
                pass
        except:
            raise

    def _write_stderr(self, message):
        ''' Writes a message to stderr with the system's encoding, or
        with ISO-8859-1 if python can't figure out the encoding'''
        try:
            sys.stderr.write(message)
            sys.stderr.flush()
        except UnicodeEncodeError:  
            encoding = 'iso-8859-1'
            sys.stderr.write(message.encode(encoding))
            sys.stderr.flush()
        except:
            raise

    # Write a message to the syslog
    def write_syslog( self, message, priority = syslog.LOG_INFO ):
        syslog.openlog( "swup", 1 , 168 ) 
        #Write to the system logger.
        syslog.syslog ( priority, message )
        syslog.closelog()

    #Wrapper functions to log using various LOG priorities to syslog
    def write_syslog_emerg( self, message ):
        self.write_syslog( message, syslog.LOG_EMERG )

    def write_syslog_alert( self, message ):
        self.write_syslog( message, syslog.LOG_ALERT )

    def write_syslog_crit( self, message ):
        self.write_syslog( message, syslog.LOG_CRIT )

    def write_syslog_err( self, message ):
        self.write_syslog( message, syslog.LOG_ERR )

    def write_syslog_warning( self, message ):
        self.write_syslog( message, syslog.LOG_WARNING )

    def write_syslog_notice( self, message ):
        self.write_syslog( message, syslog.LOG_NOTICE )

    def write_syslog_info( self, message ):
        self.write_syslog( message, syslog.LOG_INFO )

    def write_syslog_debug( self, message ):
        self.write_syslog( message, syslog.LOG_DEBUG )

        
    def write_stdout( self, message, newline=True ):
        ''' Write a message to stdout'''
        if self.loglevel > LOGLEVEL_SILENT: #If silent don't write
            if newline:
                message = "%s\n" %message
            self._write_stdout(message)
        else :
            # no output if log level is silent
            pass

    def write_stdout_info( self, message, newline=True ):
        if self.loglevel > LOGLEVEL_QUIET: #If quiet don't write
            if newline:
                message = "%s\n" %message
            self._write_stdout(message)
        else :
            # no output
            pass
        

    def write_stdout_verbose( self, message, newline=True ):
        if self.loglevel >= LOGLEVEL_VERBOSE: #Write if Verbose logging selected
            if newline:
                message = "%s\n" %message
            self._write_stdout(message)
        else:
            # no verbose output
            pass


    def write_tty( self, message ):
        if self.isatty_stdout and self.loglevel > LOGLEVEL_NOTTY:
            self._write_stdout(message)
        
    def write_stderr( self, message ):
        '''Write a message to stderr'''
        message = "%s\n" %message
        self._write_stderr(message)

    def write_progress( self, message ):
        '''Write a progress message to stdout'''
        if self.loglevel == LOGLEVEL_PROGRESS:
            message = "%s\n" %message
            self._write_stdout(message)
