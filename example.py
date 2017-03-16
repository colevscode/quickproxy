import os
import shlex
import subprocess

import quickproxy3

'''
A simple example of how to use quickproxy. To try it, first start up the http
server like so:

> python example.py httpserv &

Then you can startup the proxy like this:

> python example.py &

Finally test it with a request:

> curl localhost:8080

Your request to the proxy running on port 8080 will be fetched from the http
server on 4040 according to the request modifications applied in the callback.

To shut down the servers just run `fg` and ^C twice.
'''


def main():
    def callback(response):
        response.port = 4040
        return response

    quickproxy3.run_proxy(port=8080, req_callback=callback)


def httpserv():
    cmd = "python -m SimpleHTTPServer %d" % 4040
    cwd = os.path.dirname(os.path.realpath(__file__)) + "/tests"
    subprocess.call(shlex.split(cmd), cwd=cwd)


if __name__ == '__main__':

    import sys

    if len(sys.argv) > 1:
        globals()[sys.argv[1]]()
    else:
        main()
