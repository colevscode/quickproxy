import os
import pprint
import sys
import urllib.parse
from copy import copy

import tornado.httpclient
import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web

__all__ = ['run_proxy', 'RequestObj', 'ResponseObj']

DEFAULT_CALLBACK = lambda r: r


class Bunch(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def __str__(self):
        return str(self.__dict__)


class RequestObj(Bunch):
    '''
    An HTTP request object that contains the following request attributes:

    protocol: either 'http' or 'https'
    host: the destination hostname of the request
    port: the port for the request
    path: the path of the request ('/index.html' for example)
    query: the query string ('?key=value&other=value')
    fragment: the hash fragment ('#fragment')
    method: request method ('GET', 'POST', etc)
    username: always passed as None, but you can set it to override the user
    password: None, but can be set to override the password
    body: request body as a string
    headers: a dictionary of header / value pairs
        (for example {'Content-Type': 'text/plain', 'Content-Length': 200})
    follow_redirects: true to follow redirects before returning a response
    validate_cert: false to turn off SSL cert validation
    context: a dictionary to place data that will be accessible to the response
    '''
    pass


class ResponseObj(Bunch):
    '''
    An HTTP response object that contains the following request attributes:

    code: response code, such as 200 for 'OK'
    headers: the response headers
    pass_headers: a list or set of headers to pass along in the response. All
        other headeres will be stripped out. By default this includes:
        ('Date', 'Cache-Control', 'Server', 'Content-Type', 'Location')
    body: response body as a string
    context: the context object from the request
    '''

    def __init__(self, **kwargs):
        kwargs.setdefault('code', 200)
        kwargs.setdefault('headers', {})
        kwargs.setdefault('pass_headers', True)
        kwargs.setdefault('body', '')
        kwargs.setdefault('context', {})
        super(ResponseObj, self).__init__(**kwargs)


def _make_proxy(methods, req_callback, resp_callback, err_callback, debug_level=0):
    class ProxyHandler(tornado.web.RequestHandler):

        SUPPORTED_METHODS = methods

        def make_requestobj(self, request):
            '''
            creates a request object for this request
            '''

            # get url for request
            # surprisingly, tornado's HTTPRequest sometimes
            # has a uri field with the full uri (http://...)
            # and sometimes it just contains the path. :(

            url = request.uri
            if not url.startswith('http'):
                url = "{proto}://{netloc}{path}".format(
                    proto=request.protocol,
                    netloc=request.host,
                    path=request.uri
                )

            parsedurl = urllib.parse.urlparse(url)

            # create request object

            requestobj = RequestObj(
                method=request.method,
                protocol=parsedurl.scheme,
                username=None,
                password=None,
                host=parsedurl.hostname,
                port=parsedurl.port or 80,
                path=parsedurl.path,
                query=parsedurl.query,
                fragment=parsedurl.fragment,
                body=request.body,
                headers=request.headers,
                follow_redirects=False,
                validate_cert=True,
                context={}
            )

            return requestobj, parsedurl

        def make_request(self, obj, parsedurl):
            '''
            converts a request object into an HTTPRequest
            '''

            obj.headers["Host"] = obj.host

            if obj.username or parsedurl.username or \
                    obj.password or parsedurl.password:

                auth = "{username}:{password}@".format(
                    username=obj.username or parsedurl.username,
                    password=obj.password or parsedurl.password
                )

            else:
                auth = ''

            url = "{proto}://{auth}{host}{port}{path}{query}{frag}"
            url = url.format(
                proto=obj.protocol,
                auth=auth,
                host=obj.host,
                port=(':' + str(obj.port)) if (obj.port and obj.port != 80) else '',
                path='/' + obj.path.lstrip('/') if obj.path else '',
                query='?' + obj.query.lstrip('?') if obj.query else '',
                frag=obj.fragment
            )

            req = tornado.httpclient.HTTPRequest(
                url=url,
                method=obj.method,
                body=obj.body,
                headers=obj.headers,
                follow_redirects=obj.follow_redirects,
                allow_nonstandard_methods=True
            )

            return req

        def handle_request(self, request):

            if debug_level >= 4:
                print("<<<<<<<< REQUEST <<<<<<<<")
                pprint.pprint(request.__dict__)

            requestobj, parsedurl = self.make_requestobj(request)

            if debug_level >= 3:
                print("<<<<<<<< REQUESTOBJ <<<<<<<<")
                pprint.pprint(requestobj.__dict__)

            if debug_level >= 1:
                debugstr = "serving request from %s:%d%s " % (requestobj.host,
                                                              requestobj.port or 80,
                                                              requestobj.path)

            modrequestobj = req_callback(requestobj)

            if isinstance(modrequestobj, ResponseObj):
                self.handle_response(modrequestobj)
                return

            if debug_level >= 1:
                print(f"{debugstr} to {modrequestobj.host}:{modrequestobj.port or 80}{modrequestobj.path}")

            outreq = self.make_request(modrequestobj, parsedurl)

            if debug_level >= 2:
                print(">>>>>>>> REQUEST >>>>>>>>")
                print(f"{outreq.method} {outreq.url}")
                for k, v in list(outreq.headers.items()):
                    print(f"{k}: {v}")

            # send the request
            def _resp_callback(response):
                self.handle_response(response, context=modrequestobj.context)

            client = tornado.httpclient.AsyncHTTPClient()
            try:
                client.fetch(outreq, _resp_callback)
            except tornado.httpclient.HTTPError as e:
                if hasattr(e, 'response') and e.response:
                    self.handle_response(e.response,
                                         context=modrequestobj.context,
                                         error=True)
                else:
                    self.set_status(500)
                    self.write('Internal server error:\n' + str(e))
                    self.finish()

        def handle_response(self, response, context={}, error=False):

            if not isinstance(response, ResponseObj):
                if debug_level >= 4:
                    print("<<<<<<<< RESPONSE <<<<<<<")
                    pprint.pprint(response.__dict__)

                responseobj = ResponseObj(
                    code=response.code,
                    headers=response.headers,
                    pass_headers=True,
                    body=response.body,
                    context=context,
                )
            else:
                responseobj = response

            if debug_level >= 3:
                print("<<<<<<<< RESPONSEOBJ <<<<<<<")
                responseprint = copy(responseobj)
                responseprint.body = "-- body content not displayed --"
                pprint.pprint(responseprint.__dict__)

            if not error:
                mod = resp_callback(responseobj)
            else:
                mod = err_callback(responseobj)

            # set the response status code

            if mod.code == 599:
                self.set_status(500)
                self.write('Internal server error. Server unreachable.')
                self.finish()
                return

            self.set_status(mod.code)

            # set the response headers

            if type(mod.pass_headers) == bool:
                headers = list(mod.headers.keys()) if mod.pass_headers else []
            else:
                headers = mod.pass_headers
            for header in headers:
                v = mod.headers.get(header)
                if v:
                    self.set_header(header, v)

            if debug_level >= 2:
                print(">>>>>>>> RESPONSE >>>>>>>")
                for k, v in list(self._headers.items()):
                    print(f"{k} {v}")

            # set the response body

            if mod.body:
                self.write(mod.body)

            self.finish()

        @tornado.web.asynchronous
        def get(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def options(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def head(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def put(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def patch(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def post(self):
            self.handle_request(self.request)

        @tornado.web.asynchronous
        def delete(self):
            self.handle_request(self.request)

    return ProxyHandler


def run_proxy(port,
              methods=['GET', 'POST'],
              req_callback=DEFAULT_CALLBACK,
              resp_callback=DEFAULT_CALLBACK,
              err_callback=DEFAULT_CALLBACK,
              test_ssl=False,
              start_ioloop=True,
              debug_level=0):
    """
    Run proxy on the specified port.

    methods: the HTTP methods this proxy will support
    req_callback: a callback that is passed a RequestObj that it should
        modify and then return
    resp_callback: a callback that is given a ResponseObj that it should
        modify and then return
    err_callback: in the case of an error, this callback will be called.
        there's no difference between how this and the resp_callback are
        used.
    test_ssl: if true, will wrap the socket in an self signed ssl cert
    start_ioloop: if True (default), the tornado IOLoop will be started
        immediately.
    debug_level: 0 no debug, 1 basic, 2 verbose
    """

    app = tornado.web.Application([
        (r'.*', _make_proxy(methods=methods,
                            req_callback=req_callback,
                            resp_callback=resp_callback,
                            err_callback=err_callback,
                            debug_level=debug_level)),
    ])

    if test_ssl:
        this_dir, this_filename = os.path.split(__file__)
        kwargs = {
            "ssl_options": {
                "certfile": os.path.join(this_dir, "data", "test.crt"),
                "keyfile": os.path.join(this_dir, "data", "test.key"),
            }
        }
    else:
        kwargs = {}

    http_server = tornado.httpserver.HTTPServer(app, **kwargs)
    http_server.listen(port)
    ioloop = tornado.ioloop.IOLoop.instance()
    if start_ioloop:
        print(f"Starting HTTP proxy on port {port}")
        ioloop.start()
    return app


if __name__ == '__main__':
    port = 8888
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print(f"Starting HTTP proxy on port {port}")
    run_proxy(port)
