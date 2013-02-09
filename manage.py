#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright © 2011-2013, RokuSigma Inc. and contributors as an unpublished
# work. See AUTHORS for details.
#
# RokuSigma Inc. (the “Company”) Confidential
#
# NOTICE: All information contained herein is, and remains the property of the
# Company. The intellectual and technical concepts contained herein are
# proprietary to the Company and may be covered by U.S. and Foreign Patents,
# patents in process, and are protected by trade secret or copyright law.
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from the
# Company. Access to the source code contained herein is hereby forbidden to
# anyone except current Company employees, managers or contractors who have
# executed Confidentiality and Non-disclosure agreements explicitly covering
# such access.
#
# The copyright notice above does not evidence any actual or intended
# publication or disclosure of this source code, which includes information
# that is confidential and/or proprietary, and is a trade secret, of the
# Company. ANY REPRODUCTION, MODIFICATION, DISTRIBUTION, PUBLIC PERFORMANCE,
# OR PUBLIC DISPLAY OF OR THROUGH USE OF THIS SOURCE CODE WITHOUT THE EXPRESS
# WRITTEN CONSENT OF THE COMPANY IS STRICTLY PROHIBITED, AND IN VIOLATION OF
# APPLICABLE LAWS AND INTERNATIONAL TREATIES. THE RECEIPT OR POSSESSION OF
# THIS SOURCE CODE AND/OR RELATED INFORMATION DOES NOT CONVEY OR IMPLY ANY
# RIGHTS TO REPRODUCE, DISCLOSE OR DISTRIBUTE ITS CONTENTS, OR TO MANUFACTURE,
# USE, OR SELL ANYTHING THAT IT MAY DESCRIBE, IN WHOLE OR IN PART.
#

#
# gae-path
# Written by Nik Graf @nikgraf
# <https://github.com/nikgraf/gae-path>
#
import os
import sys

def build_possible_paths():
    """ Returns a list of possible paths where App Engine SDK could be. First
    look within the project for a local copy, then look in PATH and where the
    Unix and Mac OS X SDK installers place it. """
    dir_path = os.path.abspath(os.path.dirname(__file__))
    app_dir = os.path.dirname(os.path.dirname(dir_path))
    paths = [os.path.join(app_dir, '.google_appengine'),
            '/usr/local/google_appengine',
            '/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine']
    for path in os.environ.get('PATH', '').replace(';', ':').split(':'):
        path = path.rstrip(os.sep)
        if path.endswith('google_appengine'):
            paths.append(path)
    try:
        # If on windows, look for where the Windows SDK installed it.
        from win32com.shell import shell
        from win32com.shell import shellcon
        id_list = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_PROGRAM_FILES)
        program_files = shell.SHGetPathFromIDList(id_list)
        paths.append(os.path.join(program_files, 'Google','google_appengine'))
    except ImportError, e:
        # Not windows.
        pass
    return paths

def gae_sdk_path():
    """ Returns the App Engine SDK Path """
    paths = build_possible_paths()
    # Loop through all possible paths and look for the SDK dir.
    sdk_path = None
    for possible_path in paths:
        possible_path = os.path.realpath(possible_path)
        if os.path.exists(possible_path):
            sdk_path = possible_path
            break
    if sdk_path is None:
        # The SDK could not be found in any known location.
        sys.stderr.write('The Google App Engine SDK could not be found!\n'
              'Visit http://code.google.com/p/app-engine-patch/'
              ' for installation instructions.\n')
        sys.exit(1)
    return sdk_path

def add_gae_sdk_path():
    """ Try to import the appengine code from the system path. """
    try:
        from google.appengine.api import apiproxy_stub_map
    except ImportError, e:
        # Hack to fix reports of import errors on Ubuntu 9.10.
        if 'google' in sys.modules:
            del sys.modules['google']
        sys.path = [gae_sdk_path()] + sys.path

#
# Based loosely on code from flask-engine
# By Zach Williams <git@zachwill.com>
# <https://github.com/zachwill/flask-engine>
#
def find_gae_sdk():
    """ Correct any ImportError caused from being unable to find Google App
    Engine's SDK. These normally occur when trying to run the application from
    the commandline and/or when testing. """
    add_gae_sdk_path()
    path = gae_sdk_path()
    for path in [path + "/lib/yaml/lib",
                 path + "/lib/fancy_urllib",
                 path + "/lib/webob"]:
        if path not in sys.path:
            sys.path.append(path)

def adjust_sys_path(dir_name='lib'):
    """ Patch sys.path to add pre-packaged dependencies from the lib directory.
    Google App Engine has a hard limit on no more than 1,000 files per project,
    and third-party packages count towards that limit. With just a few large
    depenendencies you can max out the number of files very quickly. The
    solution is to package external dependencies as zip files which the Python
    interpreter can read (see this project's Makefile), and add these zip files
    to the Python path. """
    PROJECT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    LIBRARY_DIRECTORY = os.path.join(PROJECT_DIRECTORY, dir_name)
    if LIBRARY_DIRECTORY not in sys.path:
        sys.path.insert(0, LIBRARY_DIRECTORY)
    for zippackage in os.listdir(LIBRARY_DIRECTORY):
        pkg_path = os.path.join(LIBRARY_DIRECTORY, zippackage)
        if pkg_path not in sys.path: # protect against multiple-import
            sys.path.insert(0, pkg_path)

# ===----------------------------------------------------------------------===

find_gae_sdk()
adjust_sys_path()
from src import app

_debugged_app = None
if 'SERVER_SOFTWARE' in os.environ and os.environ['SERVER_SOFTWARE'].startswith('Dev'):
    global _debugged_app
    from werkzeug import DebuggedApplication
    if _debugged_app is None:
        _debugged_app = DebuggedApplication(app.wsgi_app, evalex=True)
    app.wsgi_app = _debugged_app

from flask.ext.script import Manager, Option
manager = Manager(app, with_default_commands=False)

# ===----------------------------------------------------------------------===

from flask.ext.script import Shell, prompt, prompt_pass

class RemoteShell(Shell):
    description = (
            u"Runs a interactive Python shell using Google App Engine's "
            u"remote_api."
        )

    HISTORY_PATH = os.path.expanduser('~/.remote_api_shell_history')
    DEFAULT_PATH = r'/_ah/remote_api'

    def get_options(self, *args, **kwargs):
        return (
            Option('-s', '--server',
                   dest='server',
                   default=None,
                   help=u"The hostname your app is deployed on. Defaults to "
                        u" <app_id>.appspot.com."),
            Option('-p', '--path',
                   dest='path',
                   default=r'/_ah/remote_api',
                   help=(u"The path on the server to the remote_api handler. "
                         u"Defaults to %s.") % self.DEFAULT_PATH),
            Option('--secure',
                   dest='secure',
                   default=False,
                   action='store_true',
                   help=u"Use HTTPS when communicating with the server."),
        ) + super(RemoteShell, self).get_options(*args, **kwargs)

    def run(self, server, path, secure, *args, **kwargs):
        appid = None

        if server is None and appid:
            server = '%s.appspot.com' % appid

        def _auth_func():
            return (prompt('Username', default='admin'),
                    prompt_pass('Password'))

        import atexit
        try:
            import readline
        except ImportError:
            readline = None

        from google.appengine.ext.remote_api import remote_api_stub
        from google.appengine.tools import appengine_rpc
        remote_api_stub.ConfigureRemoteApi(
            appid, path, _auth_func, servername=server, save_cookies=True,
            secure=secure, rpc_server_factory=appengine_rpc.HttpRpcServer)
        remote_api_stub.MaybeInvokeAuthentication()

        os.environ['SERVER_SOFTWARE'] = 'Development (remote_api_shell)/1.0'

        if not appid:
            appid = os.environ['APPLICATION_ID']
        sys.ps1 = '%s> ' % appid

        if readline is not None:
            readline.parse_and_bind('tab: complete')
            atexit.register(lambda: readline.write_history_file(self.HISTORY_PATH))
            if os.path.exists(self.HISTORY_PATH):
                readline.read_history_file(self.HISTORY_PATH)

        if '' not in sys.path:
            sys.path.insert(0, '')

        return super(RemoteShell, self).run(*args, **kwargs)

BANNER = (
        u"App Engine remote_api shell\n"
        u"Python %s"
    ) % sys.version
manager.add_command('shell', RemoteShell(banner=BANNER))

# ===----------------------------------------------------------------------===

if __name__ == '__main__':
    manager.run()

#
# End of File
#
