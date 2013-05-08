'''
    AxelProxy XBMC Addon
    Copyright (C) 2013 Eldorado

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
    MA 02110-1301, USA.
'''

import re
import urllib2
import sys
import traceback
import socket
import base64
import hashlib
import os
import time
import threading
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

import axel
import common


http_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; '
        'en-US; rv:1.9.2) Gecko/20100115 Firefox/3.6',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
    'Accept': 'text/xml,application/xml,application/xhtml+xml,'
        'text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
    'Accept-Language': 'en-us,en;q=0.5',
    }
    
class MyHandler(BaseHTTPRequestHandler):

           
    #Handles a HEAD request
    def do_HEAD(self):
        # Only send the head
        print "HEAD request"

    #Handles a GET request.
    def do_GET(self):
        print "GET request"
        # Send head and video
        self.answer_request()


    #Handle incoming requests
    def answer_request(self):
        try:

            #Pull apart request path
            request_path=self.path[1:]       
            request_path=re.sub(r"\?.*","",request_path)

            #If a range was sent in with the header
            requested_range=self.headers.getheader("Range")

            print 'REQUEST PATH: %s' % request_path
            print 'REQUEST RANGE: %s' % requested_range

            #Expecting url to be sent in base64 encoded - saves any url issues with XBMC
            (file_url,file_name)=self.decode_B64_url(request_path)

            #Send file request
            self.handle_send_request(file_url, file_name, requested_range)
        
            #If a request to stop is sent, shut down the proxy
            if request_path=="stop":
                sys.exit()

        except:
            #Print out a stack trace
            traceback.print_exc()

            #Close output stream file
            self.wfile.close()
            return

        #Close output stream file
        self.wfile.close()

    
    def handle_send_request(self, file_url, file_name, s_range):

        #Check if file has been cached yet
        # - Grab file info if it has
        # - Else Save file info to cache
        file_dest = common.profile_path
        
        cached = self.get_from_cache(file_name)
        if cached:
            (file_size, file_name) = cached
        else:
            file_size=int(self.get_file_size(file_url))
            self.save_to_cache(file_name, (file_size, file_name))

        (hrange, crange) = self.get_range_request(s_range, file_size)
        
        print 'REQUESTING %s and %s' % (hrange, crange)
        
        # Do we have to send a normal response or a range response?
        if s_range:
            self.send_response(206)
            self.send_header("Content-Range",crange)
        else:
            #Send back 200 reponse - OK
            self.send_response(200)

        #Set response type values
        rtype="application/x-msvideo"
        etag=self.generate_ETag(file_url)

        content_size= file_size - hrange
        
        #Send http response headers
        self.send_http_headers(file_name, rtype, content_size , etag)

        #Send the video file
        self.send_video(self.wfile, file_url, file_dest, file_name, hrange)


    def send_video(self, file_out, file_link, file_dest, file_name, start_byte):
        print 'Starting download at byte: %d' % start_byte
        
        full_path = os.path.join(common.profile_path, file_name)
        
        import axel
        axel = axel.AxelDownloader()

        
        dt = threading.Thread(target=axel.download, args = (file_link, file_dest, file_name))
        dt.start()
        
        try:
            #Opening file
            
            time.sleep(10)

            print 'FILE DEST: %s' % full_path
            out_fd = open(full_path, "rb")
            out_fd.seek(start_byte)
            file_out.write(out_fd.read())
            file_out.flush()
            out_fd.close()
        except Exception, e:
            print 'Exception sending file: %s' % e
            pass
        

    def get_file_size(self, url):
        request = urllib2.Request(url, None, http_headers)
        data = urllib2.urlopen(request)
        content_length = data.info()['Content-Length']
        return content_length


    #Set and reply back standard set of headers including file information
    def send_http_headers(self, file_name, content_type, content_size , etag):
        print "Sending headers"
        try:
            self.send_header("Content-Disposition", "inline; filename=\"" + file_name.encode('iso-8859-1', 'replace')+"\"")
        except:
            pass
        self.send_header("Content-type", content_type)
        self.send_header("Last-Modified","Wed, 21 Feb 2000 08:43:39 GMT")
        self.send_header("ETag",etag)
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Cache-Control","public, must-revalidate")
        self.send_header("Cache-Control","no-cache")
        self.send_header("Pragma","no-cache")
        self.send_header("features","seekable,stridable")
        self.send_header("client-id","12345")
        self.send_header("Content-Length", str(content_size))
        self.end_headers()


    #Generate a unique hash tag
    def generate_ETag(self, url):
        md=hashlib.md5()
        md.update(url)
        return md.hexdigest()


    def get_range_request(self, hrange, file_size):
        if hrange==None:	
            hrange=0
            crange=None
        else:
            try:
                #Get the byte value from the request string.
                hrange=str(hrange)
                hrange=int(hrange.split("=")[1].split("-")[0])
                #Build range string
                crange="bytes "+str(hrange)+"-" +str(int(file_size)-1)+"/"+str(file_size)
            except:
                # Failure to build range string? Create a 0- range.
                hrange=0
                crange="bytes 0-"
        return (hrange, crange)


    def decode_B64_url(self, b64):
        url = base64.b64decode(b64)
        file_name = url.split('/')[-1]
        return (url, file_name )


    def get_from_cache(self, name):
        global file_cache
        try:
            return file_cache[name]
        except:
            return None


    def save_to_cache(self, name, details):
        global file_cache
        try:
            file_cache[name]=details
        except Exception, e:
            print 'Error attempting to save to cache: %s', e
            pass


class Server(HTTPServer):
    """HTTPServer class with timeout."""

    def get_request(self):
        """Get the request and client address from the socket."""
        # 10 second timeout
        self.socket.settimeout(5.0)
        result = None
        while result is None:
            try:
                result = self.socket.accept()
            except socket.timeout:
                pass
        # Reset timeout on the new socket
        result[0].settimeout(1000)
        return result

class ThreadedHTTPServer(ThreadingMixIn, Server):
    """Handle requests in a separate thread."""

#Address and IP for Proxy to listen on
HOST_NAME = '127.0.0.1'
PORT_NUMBER = 64653

#Init file_cache - stores file information for repeat requests
global file_cache
file_cache={}

if __name__ == '__main__':  
    socket.setdefaulttimeout(10)
    server_class = ThreadedHTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
    print "AxelProxy Downloader Starting - %s:%s" % (HOST_NAME, PORT_NUMBER)
    while(True):
        httpd.handle_request()
    httpd.server_close()
    print "AxelProxy Downloader Stopping %s:%s" % (HOST_NAME, PORT_NUMBER)
