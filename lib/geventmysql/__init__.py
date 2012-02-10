# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#this is a dbapi/mysqldb compatible wrapper around the lowlevel
#client in client.py

#TODO weak ref on connection in cursor


import sys
import logging
import exceptions

import gevent
TaskletExit = gevent.GreenletExit

from datetime import datetime, date
from geventmysql import client

threadsafety = 1
apilevel = "2.0"
paramstyle = "format"

default_charset = sys.getdefaultencoding()

class Error(exceptions.StandardError): pass
class Warning(exceptions.StandardError): pass
class InterfaceError(Error): pass
class DatabaseError(Error): pass
class InternalError(DatabaseError): pass
class OperationalError(DatabaseError): pass
class ProgrammingError(DatabaseError): pass
class IntegrityError(DatabaseError): pass
class DataError(DatabaseError): pass
class NotSupportedError(DatabaseError): pass

class TimeoutError(DatabaseError): pass

class Cursor(object):
    log = logging.getLogger('Cursor')

    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.closed = False
        self._close_result()
        
    def _close_result(self):
        #make sure any previous resultset is closed correctly
        
        if self.result is not None:
            #make sure any left over resultset is read from the db, otherwise
            #the connection would be in an inconsistent state
            try:
                while True:
                    self.result_iter.next()
            except StopIteration:
                pass #done
            self.result.close()

        self.description = None
        self.result = None
        self.result_iter = None
        self.lastrowid = None
        self.rowcount = -1
        
    def _escape_string(self, s, replace = {'\0': '\\0', '\n': '\\n', '\r': '\\r', '\\': '\\\\', "'": "\\'", '"': '\\"', '\x1a': '\\Z'}):
        """take from mysql src code:"""
        #TODO how fast is this?, do this in C/pyrex?
        get = replace.get
        return "".join([get(ch, ch) for ch in s])

            
    def _wrap_exception(self, e, msg):
        self.log.exception(msg)
        if isinstance(e, gevent.Timeout):
            return TimeoutError(msg + ': ' + str(e))
        else:
            return Error(msg + ': ' + str(e))
        
    def execute(self, qry, args = []):
        #print repr(qry),  repr(args), self.connection.charset
        if self.closed:
            raise ProgrammingError('this cursor is already closed')

        if type(qry) == unicode:
            #we will only communicate in 8-bits with mysql
            qry = qry.encode(self.connection.charset)

        try:
            self._close_result() #close any previous result if needed
            #substitute arguments
            params = []
            for arg in args:
                if type(arg) == str:
                    params.append("'%s'" % self._escape_string(arg))
                elif type(arg) == unicode:
                    params.append("'%s'" % self._escape_string(arg).encode(self.connection.charset))
                elif isinstance(arg, (int, long, float)):
                    params.append(str(arg))
                elif arg is None:
                    params.append('null')
                elif isinstance(arg, datetime):
                    params.append("'%s'" % arg.strftime('%Y-%m-%d %H:%M:%S'))
                elif isinstance(arg, date):
                    params.append("'%s'" % arg.strftime('%Y-%m-%d'))
                else:
                    assert False, "unknown argument type: %s %s" % (type(arg), repr(arg))

            qry = qry % params
            result = self.connection.client.query(qry)
            
            #process result if nescecary
            if isinstance(result, client.ResultSet):
                self.description = tuple(((name, type_code, None, None, None, None, None) for name, type_code, charsetnr in result.fields))
                self.result = result
                self.result_iter = iter(result)
                self.lastrowid = None
                self.rowcount = -1
            else:
                self.rowcount, self.lastrowid = result
                self.description = None
                self.result = None

        except TaskletExit:
            raise
        except Exception, e:
            raise self._wrap_exception(e, "an error occurred while executing qry %s" % (qry, ))
        
    def fetchall(self):
        try:
            return list(self.result_iter)
        except TaskletExit:
            raise
        except Exception, e:
            raise self._wrap_exception(e, "an error occurred while fetching results")
            
    def fetchone(self):
        try:
            return self.result_iter.next()
        except StopIteration:
            return None
        except TaskletExit:
            raise
        except Exception, e:
            raise self._wrap_exception(e, "an error occurred while fetching results")
    
    def close(self):
        if self.closed: 
            raise ProgrammingError("cannot cursor twice")
        
        try:
            self._close_result()
            self.closed = True
        except TaskletExit:
            raise
        except Exception, e:
            raise self._wrap_exception(e, "an error occurred while closing cursor")
        
class Connection(object):
    
    def __init__(self, *args, **kwargs):

        self.kwargs = kwargs.copy()
        
        if not 'autocommit' in self.kwargs:
            #we set autocommit explicitly to OFF as required by python db api, because default of mysql would be ON
            self.kwargs['autocommit'] = False
        else:
            pass #user specified explictly what he wanted for autocommit

        
        if 'charset' in self.kwargs:
            self.charset = self.kwargs['charset']
            if 'use_unicode' in self.kwargs and self.kwargs['use_unicode'] == True:
                pass #charset stays in args, and triggers unicode output in low-level client
            else:
                del self.kwargs['charset']
        else:
            self.charset = default_charset

        self.client = client.Connection() #low level mysql client
        self.client.connect(*args, **self.kwargs)
        
        self.closed = False
    
    def close(self):
        #print 'dbapi Connection close'
        if self.closed: 
            raise ProgrammingError("cannot close connection twice")
        
        try:
            self.client.close()
            del self.client
            self.closed = True
        except TaskletExit:
            raise
        except Exception, e:
            msg = "an error occurred while closing connection: "
            self.log.exception(msg)
            raise Error(msg + str(e))
            
    def cursor(self):
        if self.closed: 
            raise ProgrammingError("this connection is already closed")
        return Cursor(self)
    
    def get_server_info(self):
        return self.client.server_version

    def rollback(self):
        self.client.rollback()
    
    def commit(self):
        self.client.commit()
    
    @property
    def socket(self):
        return self.client.socket
    
def connect(*args, **kwargs):
    return Connection(*args, **kwargs) 
    
Connect = connect

