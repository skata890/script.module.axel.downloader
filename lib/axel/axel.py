'''
    axel downloader XBMC Addon
    Copyright (C) 2013 Eldorado
    
    This class takes a given direct http file link and attempt to download in
    multiple connections as specified. Each connection runs under it's own thread, separate from the main task.
    
    File size is taken into consideration and split into logical chunks, downloaded in order of priority.
    
    File is written to disk according to priority. Writting is done in it's own single thread separate from main.
    
    HTTP error detection is included, most common errors will cause the chunk to be re-added back to the queue

    	- 503 error is interpreted as a connection denied indicating that we are trying to open too many than the host allows, 
    	  the chunk will be sent back into the queue and the thread will finish, reducing the number of running threads/connections by 1
    
      - socket time out error will cause chunk to be sent back into queue and retried   
    
    Created by: Eldorado
    
    Credits: Bstrdsmkr and the rest of the XBMCHub dev's
    
    
*To-Do:
-
-

'''

import Queue
import threading
import urllib2
import socket
import os
#from downloader import Downloader
import common

#Create queue objects
workQ = Queue.PriorityQueue()
resultQ = Queue.PriorityQueue()
        
class AxelDownloader:

    '''
    This is the main class to import

        - 
    '''  

    def __init__(self, num_connections=2, chunk_size=2000000):
        '''
        Class init      
        
        Kwargs:
            num_connections (int): number of connections/threads to attempt to open for downloading
            chunk_size (int): size in bytes for each file 'chunk' to be downloaded per connection
        '''

        #Class variables
        self.num_conn = num_connections
        self.chunk_size = chunk_size

        self.http_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; '
                'en-US; rv:1.9.2) Gecko/20100115 Firefox/3.6',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Accept': 'text/xml,application/xml,application/xhtml+xml,'
                'text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
            'Accept-Language': 'en-us,en;q=0.5',
        }
        
        common.addon.log('Axel Downloader Intitialized')


    def __get_file_size(self, url):
        '''
        Gets file size in bytes from server
        
        Args:
            url (str): full url of file to download
        '''  
        
        request = urllib2.Request(url, None, self.http_headers)
        
        try:
            data = urllib2.urlopen(request)
            content_length = data.info()['Content-Length']
        except urllib2.URLError, e:
            common.addon.log_error('http connection error attempting to retreive file size: %s' % str(e))
            return False
            
        return content_length
    
    
    def __save_file(self, out_file):
        '''
        Processes items in resultQ and saves each queue/chunk to disk

        Args:
            file_dest (str): full path to save location - EXCLUDING file_name
            file_name (str): name of saved file
        '''

        while True:
        	
            try:
  
                #Grab items from queue to process
                block_num, start_block, chunk_block = resultQ.get()
    
                #Write downloaded blocks to file
                common.addon.log('Writing block #%d starting byte: %d size: %d' % (block_num, start_block, len(chunk_block)), 2)
                out_fd = open(out_file, "r+b")      
                out_fd.seek(start_block, 0)
                out_fd.write(chunk_block)
                out_fd.close()
    
                #Tell queue that this task is done
                resultQ.task_done()

            except Exception, e:
                common.addon.log_error('Failed writing block #%d :'  % (block_num, e))        
                
                #Put chunk back into queue, mark this one done
                resultQ.task_done()
                resultQ.put([block_num, start_block, chunk_block])    


    def __build_workq(self, file_link):
        '''
        Determine file size
        
        Build work queue items based on chunk_size

        Args:
            file_link (str): direct link to file including file name
            
        '''
        
        #Retreive file size
        remaining = int(self.__get_file_size(file_link))
        common.addon.log('Retrieved File Size: %d' % remaining, 2) 
             
        # Split file size into chunks
        # Add each chunk to a queue spot to be downloaded individually
        # Using counter i to determine chunk # / priority
        start_block = 0
        chunk_block = self.chunk_size
        i = 0
        
        while chunk_block > 0:
 
            #Add chunk to work queue       
            workQ.put([i, file_link, start_block, chunk_block])
        
            #Increment starting byte
            start_block += chunk_block
            
            #Reduce remaining bytes by size of chunk
            if remaining >= chunk_block:
                remaining -= chunk_block
        
            #If remaining is less than size of chunk, we want the final chunk to be what's left
            if remaining < chunk_block:
                chunk_block = remaining
        
            #Increment i - used to set queue priority
            i += 1
    

    def download(self, file_link, file_dest, file_name=''):
        '''
        Main function to perform download
              
        Args:
            file_link (str): direct link to file including file name
            file_dest (str): full path to save location - EXCLUDING file_name
        Kwargs:
            file_name (str): name of saved file - name will be pulled from file_link if not supplied
        ''' 
   
        # Create output file with a .part extension to indicate partial download
        # TO-DO: add better file check if exists and creation
        out_file = os.path.join(file_dest, file_name)
        part_file = out_file + ".part"
        out_fd = os.open(out_file, os.O_CREAT | os.O_WRONLY)
        os.close(out_fd)
               
        # Ccreate a worker thread pool
        for i in range(self.num_conn):
            t = Downloader()
            t.start()
        common.addon.log('Worker threads initialized', 2)
        
        # Save downloaded chunks to file as they enter the resultQ
        # Put process into it's own thread
        st = threading.Thread(target=self.__save_file, args = (out_file, ))
        st.start()

        common.addon.log('Result thread initialized')            
        
        #Build workQ items
        self.__build_workq(file_link)
        
        common.addon.log('Worker Queue Built', 2) 
          
        # Wait for the queues to finish - join to close all threads when done
        workQ.join()
        common.addon.log('Worker Queue successfully joined', 2)
        resultQ.join()
        common.addon.log('Result Queue successfully joined', 2)
        
        #Rename file from .part to intended name
        #os.rename(part_file, out_file)



class Downloader(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        self.http_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; '
                'en-US; rv:1.9.2) Gecko/20100115 Firefox/3.6',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Accept': 'text/xml,application/xml,application/xhtml+xml,'
                'text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
            'Accept-Language': 'en-us,en;q=0.5',
        }
        self.block_size = 1024

    def run(self):
        '''
        Override threads run() method to do our download work
        '''
        
        while True:
            block_num, url, start, length = workQ.get()
            common.addon.log('Starting Worker Queue #: %d starting: %d length: %d' % (block_num, start, length), 2)

            #Download the file
            result = self.__download_file(block_num, url, start, length)

            #Check result status            
            if result == True:
                #Tell queue that this task is done
                common.addon.log('Worker Queue #: %d downloading finished' % block_num, 2)
                
                #Mark queue task as done
                workQ.task_done()

            #503 - Likely too many connection attempts
            elif result == "503":

                common.addon.log('503 error - Breaking from loop, closing thread - Queue #: %d' % block_num, 0)
                
                #Mark queue task as done
                workQ.task_done()
                
                #Put chunk back into workQ then break from loop/end thread
                workQ.put([block_num, url, start, length])
                break

            else:
                #Mark queue task as done
                workQ.task_done()
            
                #Put chunk back into workQ
                common.addon.log('Re-adding block back into Queue - Queue #: %d' % block_num, 0)
                workQ.put([block_num, url, start, length])

 
    def __download_file(self, block_num, url, start, length):        

        request = urllib2.Request(url, None, self.http_headers)
        if length == 0:
            return None
        request.add_header('Range', 'bytes=%d-%d' % (start, start + length))

        #TO-DO: Add more url type error checks
        while 1:
            try:
                data = urllib2.urlopen(request)
            except urllib2.URLError, e:
                common.addon.log_error("Connection failed: %s" % e)
                return str(e.code)                
            else:
                break

        #Init working variables
        curr_chunk = ''
        remaining_blocks = length

        #Read data blocks in specific size 1 at a time until we have the full chunk_block size
        while remaining_blocks > 0:

            if remaining_blocks >= self.block_size:
                fetch_size = self.block_size
            else:
                fetch_size = int(remaining_blocks)
                
            try:
                data_block = data.read(fetch_size)
                if len(data_block) == 0:
                    common.addon.log("Connection: 0 sized block fetched. Retrying.", 0)
                    return "no_block"
                if len(data_block) != fetch_size:
                    common.addon.log("Connection: len(data_block) != length. Retrying.", 0)
                    return "mismatch_block"

            except socket.timeout, s:
                common.addon.log_error("Connection timed out with msg: %s" % s)
                return "timeout"
            except Exception, e:
                common.addon.log_error("Error occured retreiving data: %s" % e)
                return "data_error"

            remaining_blocks -= fetch_size
            curr_chunk += data_block

        common.addon.log('Adding to result Queue #: %d' % block_num, 2)
        resultQ.put([block_num, start, curr_chunk])
        return True