import sys
import urlparse
from copy import copy

import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web
import tornado.httpclient

__all__ = ['run_proxy']

DEFAULT_CALLBACK = lambda r: r


class Bunch:
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
    pass



def _make_proxy(methods, req_callback, resp_callback, err_callback, debug_level=0):

    class ProxyHandler(tornado.web.RequestHandler):

        SUPPORTED_METHODS = methods


        def handle_request(self, request):

            # surprisingly, tornado's HTTPRequest sometimes
            # has a uri field with the full uri (http://...)
            # and sometimes it just contains the path. :(

            if debug_level >= 3:
                import pprint;
                print "<<<<<<<< REQUEST <<<<<<<<"
                pprint.pprint(request.__dict__)

            url = request.uri
            if not url.startswith(u'http'):
                url = u"{proto}://{netloc}{path}".format(
                    proto=request.protocol,
                    netloc=request.host,
                    path=request.uri
                )

            parsed = urlparse.urlparse(url)

            requestobj = RequestObj(
                method=request.method,
                protocol=parsed.scheme,
                username=None,
                password=None,
                host=parsed.hostname,
                port=parsed.port,
                path=parsed.path,
                query=parsed.query,
                fragment=parsed.fragment,
                body=request.body,
                headers=request.headers,
                follow_redirects=False,
                context={}
            )

            if debug_level >= 1:
                import pprint;
                print "<<<<<<<< REQUESTOBJ <<<<<<<<"
                pprint.pprint(requestobj.__dict__)


            mod = req_callback(requestobj)

            mod.headers["Host"] = mod.host

            if mod.username or parsed.username or \
                mod.password or parsed.password:

                auth = u"{username}:{password}@".format(
                    username=mod.username or parsed.username,
                    password=mod.password or parsed.password
                )

            else:
                auth = ''

            url = u"{proto}://{auth}{host}{port}{path}{query}{frag}"
            url = url.format(
                proto=mod.protocol,
                auth=auth,
                host=mod.host,
                port=(u':' + str(mod.port)) if mod.port else u'',
                path=u'/'+mod.path.lstrip(u'/') if mod.path else u'',
                query=u'?'+mod.query.lstrip(u'?') if mod.query else u'',
                frag=mod.fragment
            )

            req = tornado.httpclient.HTTPRequest(
                url=url,
                method=mod.method, 
                body=mod.body,
                headers=mod.headers, 
                follow_redirects=mod.follow_redirects,
                allow_nonstandard_methods=True
            )

            if debug_level >= 2:
                import pprint;
                print ">>>>>>>> REQUEST >>>>>>>>"
                pprint.pprint(req.__dict__)

            def _resp_callback(response):
                self.handle_response(response, context=mod.context)

            client = tornado.httpclient.AsyncHTTPClient()
            try:
                client.fetch(req, _resp_callback)
            except tornado.httpclient.HTTPError as e:
                if hasattr(e, 'response') and e.response:
                    self.handle_response(e.response, 
                                         context=mod.context,
                                         error=True)
                else:
                    self.set_status(500)
                    self.write('Internal server error:\n' + str(e))
                    self.finish()


        def handle_response(self, response, context={}, error=False):

            if debug_level >= 3:
                import pprint;
                print "<<<<<<<< RESPONSE <<<<<<<"
                pprint.pprint(response.__dict__)

            responseobj = ResponseObj(
                code=response.code,
                headers=response.headers,
                pass_headers=('Date', 'Cache-Control', 'Server',
                    'Content-Type', 'Location'),
                body=response.body,
                context=context,
            )

            if debug_level >= 1:
                import pprint;
                print "<<<<<<<< RESPONSEOBJ <<<<<<<"
                responseprint = copy(responseobj)
                responseprint.body = "-- body content not displayed --"
                pprint.pprint(responseprint.__dict__)

            if not error:
                mod = resp_callback(responseobj)
            else:
                mod = err_callback(responseobj)

            # set the response status code

            self.set_status(mod.code)

            # set the response headers

            if hasattr(mod, 'pass_headers') and mod.pass_headers:
                headers = mod.pass_headers
            else:
                headers = mod.headers.keys()
            for header in headers:
                v = mod.headers.get(header)
                if v:
                    self.set_header(header, v)

            if debug_level >= 2:
                import pprint;
                print ">>>>>>>> RESPONSE >>>>>>>"
                pprint.pprint(self.__dict__)            

            # set the response body

            if mod.body:
                self.write(mod.body)

            self.finish()


        @tornado.web.asynchronous
        def get(self):
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
    app.listen(port)
    ioloop = tornado.ioloop.IOLoop.instance()
    if start_ioloop:
        ioloop.start()
    return app


if __name__ == '__main__':
    port = 8888
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print ("Starting HTTP proxy on port %d" % port)
    run_proxy(port)