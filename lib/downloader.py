import threading

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

    def run(self):
        while True:
            block_num, url, start, length = workQ.get()
            print 'Starting Queue #: %s' % block_num
            print start
            print length

            #Download the file
            result = self.__download_file(block_num, url, start, length)

            
            if result == True:
                #Tell queue that this task is done
                print 'Queue #: %s finished' % block_num

            #503 - Likely too many connection attempts
            elif result == "503":

                print 'Breaking from loop, closing thread - Queue #: %d' % block_num
                
                #Mark queue task as done
                workQ.task_done()
                
                #Put chunk back into workQ then break from loop/end thread
                workQ.put([block_num, url, start, length])
                break

            else:
                #Put chunk back into workQ
                print 'Re-adding block to Queue - Queue #: %d' % block_num
                workQ.put([block_num, url, start, length])

            #Mark queue task as done
            workQ.task_done()

 
    def __download_file(self, block_num, url, start, length):        

        request = urllib2.Request(url, None, headers)
        if length == 0:
            return None
        request.add_header('Range', 'bytes=%d-%d' % (start, start + length))

        #TO-DO: Better error checks and send back specific status code
        while 1:
            try:
                data = urllib2.urlopen(request)
            except urllib2.URLError, e:
                print "Connection failed: %s" % e
                return str(e.code)                
            else:
                break

        chunk = ''
        block_size = 1024
        remaining_blocks = length

        #TO-DO: Clean up while loop - don't call run() - exit loop and re-add to queue
        #       Set specific status codes and return to be checked in run()
        while remaining_blocks > 0:

            if remaining_blocks >= block_size:
                fetch_size = block_size
            else:
                fetch_size = int(remaining_blocks)
                
            try:
                data_block = data.read(fetch_size)
                if len(data_block) == 0:
                    print "Connection: 0 sized block fetched. Retrying."
                    return "no_block"
                if len(data_block) != fetch_size:
                    print "Connection: len(data_block) != length. Retrying."
                    return "mismatch_block"

            except socket.timeout, s:
                print "Connection timed out with msg: %s" % s
                return "timeout"
            except Exception, e:
                print "Error occured retreiving data: %s" % e
                return "data_error"

            remaining_blocks -= fetch_size
            chunk += data_block

        print 'Putting into resultQ Queue #: %d' % block_num
        resultQ.put([block_num, start, chunk])
        return True