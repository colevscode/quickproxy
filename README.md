quickproxy
==========

A lightweight, asynchronous, programmable HTTP proxy for python. Built with Tornado.

## Use

#### A simple proxy:

	import quickproxy
	quickproxy.run_proxy(port=8080)


#### A reverse proxy:

This proxy will fetch responses from an AWS s3 bucket with the same ID as the request's hostname.

	def callback(request):
		request.host = request.host+".s3-website-us-east-1.amazonaws.com"
		request.port = 80
		return request

	quickproxy.run_proxy(port=8080, req_callback=callback)


## Reference

Quickproxy exposes just one function:

	run_proxy(port,
              methods=['GET', 'POST'], 
              req_callback=DEFAULT_CALLBACK,
              resp_callback=DEFAULT_CALLBACK,
              err_callback=DEFAULT_CALLBACK,
              start_ioloop=True)

It runs a proxy on the specified port. You can pass the following parameters to configure quickproxy:

- methods: the HTTP methods this proxy will support

- req_callback: a callback that is passed a RequestObj that it should
    modify and then return. By default this is the identity function.

- resp_callback: a callback that is given a ResponseObj that it should
    modify and then return. By default this is the identity function.

- err_callback: in the case of an error, this callback will be called.
    there's no difference between how this and the resp_callback are 
    used. By default this is the identity function.

- start_ioloop: if True (default), the tornado IOLoop will be started 
    immediately.


### Request callback functions

The request callback should receive a RequestObj and return a RequestObj.

	request_callback(requestobj)
		return requestobj

The RequestObj is a python object with the following attributes that can be modified before it is returned:

- protocol: either 'http' or 'https'

- host: the destination hostname of the request

- port: the port for the request

- path: the path of the request ('/index.html' for example)

- parameters: the parameter string at the end of the path ('/path;parameter')

- query: the query string ('?key=value&other=value')

- fragment: the hash fragment ('#fragment')

- method: request method ('GET', 'POST', etc)

- username: always passed as None, but you can set it to override the user

- password: None, but can be set to override the password

- body: request body as a string

- headers: a dictionary of header / value pairs 
    (for example {'Content-Type': 'text/plain', 'Content-Length': 200})

- follow_redirects: true to follow redirects before returning a response


### Response callback functions

The response and error callbacks should receive a ResponseObj and return a ResponseObj, similar to the request callback above.

The ResponseObj is a python object with the following attributes that can be modified before it is returned:

- code: response code, such as 200 for 'OK'

- headers: the response headers 

- pass_headers: a list or set of headers to pass along in the response. All
    other headers will be stripped out. By default this includes:

    `('Date', 'Cache-Control', 'Server', 'Content-Type', 'Location')`

- body: response body as a string


## Credits

Much of this code was adopted from Senko's tornado-proxy:

https://github.com/senko/tornado-proxy

...which is itself based on the code by Bill Janssen posted to: http://groups.google.com/group/python-tornado/msg/7bea08e7a049cf26

