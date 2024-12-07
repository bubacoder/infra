#!/usr/bin/env python3

import http.server
import socketserver
import http.client
from urllib.parse import urlparse, urlunparse


class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.proxy_request()

    def do_POST(self):
        self.proxy_request()

    def do_PUT(self):
        self.proxy_request()

    def do_DELETE(self):
        self.proxy_request()

    def proxy_request(self):
        # Parse the URL
        parsed_url = urlparse(self.path)
        target_host = parsed_url.hostname
        target_port = parsed_url.port or (80 if parsed_url.scheme == 'http' else 443)

        print("\nParsed URL:")
        print(parsed_url)

        # Read the content length
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None

        # Create headers for the target request
        headers = {key: value for key, value in self.headers.items()}

        print("\nHeaders:")
        print(headers)

        print("\nBody:")
        print(post_data)

        print(f"\nSending request to: https://{target_host}:{target_port}{parsed_url.path}")
        return

        # Create the connection to the target server
        conn = http.client.HTTPConnection(target_host, target_port)

        # Make the request to the target server
        conn.request(self.command, urlunparse(parsed_url._replace(scheme='', netloc='')), body=post_data, headers=headers)
        target_response = conn.getresponse()

        # Send the response back to the client
        self.send_response(target_response.status, target_response.reason)
        for header, value in target_response.getheaders():
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(target_response.read())


# Setting up the HTTP Proxy Server
PORT = 8888
Handler = ProxyHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving HTTP Proxy on port {PORT}")
    httpd.serve_forever()
