import unittest

import os
import time
import shlex
import urllib2
import threading
import subprocess

import tornado.ioloop

import quickproxy


TEST_HTTP_SERVER_PORT = 29281
TEST_HTTP_PROXY_PORT = 30292
TEST_HTTP_REVPROXY_PORT = 30293


class IOLoopRunner(threading.Thread):

    def __init__(self, fn):
        self.ioloop = tornado.ioloop.IOLoop.instance()
        self.fn = fn
        super(IOLoopRunner, self).__init__()

    def run(self):
        self.fn()
        self.ioloop.start()

    def join(self):
        self.ioloop.add_callback(lambda x: x.stop(), self.ioloop)
        super(IOLoopRunner, self).join()


class TestQuickProxy(unittest.TestCase):

    def setUp(self):
        # cd to the test folder
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        # start a simple python fileserver for this folder
        cmd = "python -m SimpleHTTPServer %d" % TEST_HTTP_SERVER_PORT
        self.httpserver = subprocess.Popen(shlex.split(cmd))

        # give it a second to start
        time.sleep(1) 


    def tearDown(self):
        os.kill(self.httpserver.pid, 15)
        time.sleep(1)
        os.kill(self.httpserver.pid, 9)


    def makeRequest(self, port, path, proxy_port=None):
        requrl = 'http://localhost:%d/%s' % (port, path.strip('/'))
        proxy = {}
        if proxy_port:
            proxy = {'http': 'localhost:%d' % proxy_port}
        proxy_support = urllib2.ProxyHandler(proxy)
        opener = urllib2.build_opener(proxy_support)
        return opener.open(requrl).read()


    def test_proxy(self):

        def setup_proxy():
            quickproxy.run_proxy(port=TEST_HTTP_PROXY_PORT,
                                 start_ioloop=False)

        proxy = IOLoopRunner(setup_proxy)
        proxy.start()

        resp = self.makeRequest(port=TEST_HTTP_SERVER_PORT,
                                path='test.html',
                                proxy_port=TEST_HTTP_PROXY_PORT)   

        proxy.join()

        self.assertEqual(resp, open("test.html").read())


    def test_reverse_proxy(self):

        def req_callback(request):
            request.port = TEST_HTTP_SERVER_PORT
            return request

        def setup_proxy():
            quickproxy.run_proxy(port=TEST_HTTP_REVPROXY_PORT,
                                 req_callback=req_callback,
                                 start_ioloop=False)

        proxy = IOLoopRunner(setup_proxy)
        proxy.start()

        resp = self.makeRequest(port=TEST_HTTP_REVPROXY_PORT,
                                path='test.html')   

        proxy.join()

        self.assertEqual(resp, open("test.html").read())


if __name__ == '__main__':
    unittest.main()