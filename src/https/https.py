import urllib2
import httplib
import socket
import ssl

class VerifiedHTTPSConnection(httplib.HTTPSConnection):
    """ VerifiedHTTPSConnection checks the certificate while connecting.  """
    certificateFile  = None

    def connect(self):
        """ Connect wraps the socket and checks the certificate. """
        # overrides the version in httplib so that we do
        #    certificate verification
        sock = socket.create_connection((self.host, self.port), self.timeout)
        if hasattr(self, '_tunnel_host') and self._tunnel_host:
            self.sock = sock
            self._tunnel()
        # wrap the socket using verification with the root
        #    certs in trusted_root_certs
        self.sock = ssl.wrap_socket(sock,
                                    self.key_file,
                                    self.cert_file,
                                    cert_reqs=ssl.CERT_REQUIRED,
                                    ca_certs=VerifiedHTTPSConnection.certificateFile)


class VerifiedHTTPSHandler(urllib2.HTTPSHandler):
    """ HTTPSHandler that uses the VerifiedHTTPSConnection to handle https connections. """ 

    def __init__(self, connection_class = VerifiedHTTPSConnection):
        self.specialized_conn_class = connection_class
        urllib2.HTTPSHandler.__init__(self)
    
    def https_open(self, req):
        """ Open a https connection using the specialized connect class. """
        return self.do_open(self.specialized_conn_class, req)
