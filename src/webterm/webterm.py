"""

Configurazione di Apache
==============================


1. Abilitare i moduli

  /sbin/a2enmod proxy
  /sbin/a2enmod rewrite
  /sbin/a2enmod proxy_http
  /sbin/a2enmod proxy_wstunnel
  /sbin/a2enmod rewrite
  /sbin/a2enmod headers
  /etc/init.d/apache2 restart


2. Apache setup
------------------------------------------------------------------------


Define WEBTERM_BASEURL /webterm

<LocationMatch ${WEBTERM_BASEURL}>
    ProxyPass         http://localhost:3000
    ProxyPassReverse  https://localhost:3000
</LocationMatch>

<Location ${WEBTERM_BASEURL}/ws>
    ProxyPassMatch   ws://localhost:3000/ws$1
    RewriteEngine on
    RewriteCond ${HTTP:Upgrade} websocket [NC]
    RewriteCond ${HTTP:Connection} upgrade [NC]
    #RewriteRule .* ws:/localhost:3000/$1" [P,L]
    ProxyPassReverse  https://localhost:3000/ws/$1
</Location>



3. Webterm launch
------------------------------------------------------------------------

webterm --ssladdress=0.0.0.0 --port=3000 --origin=* --certfile=./ssl-cert-snakeoil.pem --keyfile=./ssl-cert-snakeoil.key --origin='https://192.168.1.20' --apikey=12345












OLD STUFF
------------------------------------------------------------------------



ProxyPassMatch   /webterm/ws  ws://localhost:3000/ws$1
ProxyPass        /webterm/    http://localhost:3000/
RewriteEngine on
RewriteCond ${HTTP:Upgrade} websocket [NC]
RewriteCond ${HTTP:Connection} upgrade [NC]
#RewriteRule .* ws:/localhost:3000/$1" [P,L]
#Header add Access-Control-Allow-Origin "*"
ProxyPassReverse /webterm https://localhost:3000/
ProxyRequests    off


Define WEBTERM_BASEURL /webterm

<LocationMatch ${WEBTERM_BASEURL}>
    ProxyPass         http://localhost:3000
    ProxyPassReverse  https://localhost:3000
</LocationMatch>

<Location ${WEBTERM_BASEURL}/ws>
    ProxyPassMatch    ws://localhost:3000/ws$1
    RewriteEngine     on
    RewriteCond       ${HTTP:Upgrade} websocket [NC]
    RewriteCond       ${HTTP:Connection} upgrade [NC]
    #RewriteRule      .* ws:/localhost:3000/$1" [P,L]
    ProxyPassReverse  https://localhost:3000/ws/$1
</Location>

"""

import os
import datetime

from tornado.options import define

from webssh.main import *
from webssh.handler	 import IndexHandler, WsockHandler

#----------------------------------------------------------------------#
#                                                                      #
#----------------------------------------------------------------------#

class CustomIndexHandler(IndexHandler):
    """
    Override "webssh" index
    """
    def initialize(self, *args, sessions_table=None, **kwargs):

        super().initialize(*args, **kwargs)

        self.sessions_table = sessions_table

    def check_session(self, sid):

        if sid not in self.sessions_table:
            self.send_error(401, message='Invalid SESSION ID')	
            return False
        
        s = self.sessions_table[sid]
        if s['expire'] < datetime.datetime.now():
            self.send_error(401, message='Expired session')	
            return False
            
        return True


    def get(self):

        #
        # STEP 1: check if the current session is valid
        #
        sid      = self.get_argument('sid', None)
        if not self.check_session(sid):
            return

        #
        # STEP 2: render index page
        #
        hostname = self.get_argument('hostname', '')
        port     = self.get_argument('port'    , 22)
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')
        
        return self.render('index.html', 
            debug   =self.debug,
            font    =self.font, 
            hostname=hostname,
            port    =port, 
            username=username,
            password=password,
        )
	
    def post(self):
        return super().post()
    
#----------------------------------------------------------------------#

class CustomWsockHandler(WsockHandler):
    """
    Override "webssh" websocket handler
    """
    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)

#----------------------------------------------------------------------#
#                                                                      #
#----------------------------------------------------------------------#

class BaseRestHandler(tornado.web.RequestHandler):
    """
    Base REST API handler
    """
    def initialize(self, *args, apikey=None, session_expire=None, **kwargs):
        super().initialize(*args, **kwargs)
        self.apikey         = apikey
        self.session_expire = session_expire

    def check_apikey(self):

        apikey = self.get_argument('apikey', default=None)

        if apikey is None or self.apikey != apikey:
                self.send_error(401, message='Invalid apikey')	
                return False

        return True

class CustomRestSessionsAddHandler(BaseRestHandler):

    def initialize(self, *args, sessions_table=None, **kwargs):
        super().initialize(*args, **kwargs)
        self.sessions_table = sessions_table

    def get(self):
		
        if not self.check_apikey():
            return
        
        sid = secret = self.get_argument('sid')
        
        session_expire = self.session_expire
        
        s = { 
            'sid'   : sid, 
            'expire': datetime.datetime.now() + datetime.timedelta(seconds=session_expire),
        }
        
        self.sessions_table[ sid ] = s 
        
        self.write( "ADDED " + str(s) )

    #def post(self):
	#
    #    self.check_apikey()
    #
    #    return super().post()

class CustomRestSessionsListHandler(BaseRestHandler):

    def initialize(self, *args, sessions_table=None, **kwargs):
        super().initialize(*args, **kwargs)
        self.sessions_table = sessions_table

    def get(self):

        if not self.check_apikey():
            return
		
        self.write(str( self.sessions_table ))

#----------------------------------------------------------------------#
#                                                                      #
#----------------------------------------------------------------------#

def make_handlers(loop, options):
	
    host_keys_settings = get_host_keys_settings(options)
    
    policy = get_policy_setting(options, host_keys_settings)
    
    apikey         = options.apikey
    session_expire = options.session_expire
    
    sessions_table = {}

    handlers = [
        #
        #
        #
        (r'/'  , CustomIndexHandler, dict(
                                          loop=loop, 
                                          policy=policy, 
                                          host_keys_settings=host_keys_settings,

                                          sessions_table=sessions_table,
		                                 )
		),
        (r'/ws', CustomWsockHandler, dict(
                                          loop=loop,
                                         )
        ),
        
        #
        # REST API
        #
        (r'/rest/sessions/'   , CustomRestSessionsListHandler, dict(
			                                                        apikey=apikey, 
			                                                        sessions_table=sessions_table,
			                                                        session_expire=session_expire,
		                                                           )
        ),
        (r'/rest/sessions/add', CustomRestSessionsAddHandler , dict(
		                                                            apikey=apikey, 
		                                                            sessions_table=sessions_table,
			                                                        session_expire=session_expire,
		                                                           )
		),
    ]

    return handlers


def webterm_main():
	
	#
	# DEFINE custom argument ARGV
	#
    define('apikey'        , default=None    , help='REST API KEY')
    define('session-expire', default=60*60*24, help='Session expire time (in seconds)')


    #
    # START
    #
    
    options.parse_command_line()

    check_encoding_setting(options.encoding)

    loop = tornado.ioloop.IOLoop.current()

    settings = get_app_settings(options)

	#
    # TEMPLATES DIR
    #
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    settings.update({
		'template_path': os.path.join(base_dir,'templates')
	})

    app = make_app(make_handlers(loop, options), settings )

    ssl_ctx = get_ssl_context(options)

    server_settings = get_server_settings(options)

    app_listen(app, options.port, options.address, server_settings)

    if ssl_ctx:
        server_settings.update(ssl_options=ssl_ctx)
        app_listen(app, options.sslport, options.ssladdress, server_settings)

    loop.start()


if __name__ == "__main__":    
    webterm_main()    
