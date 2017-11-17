import threading, io, time, random, enum, collections
 
START_BYTE = b'<'
STOP_BYTE = b'>'
EMPTY_BYTE = b''
 
class Type (enum.Enum):
    MESSAGE = 0;
    ACK = 1;
    DONE = 2;
 
class Ack (enum.Enum):
    WAITING = 0;
    ACK_OK = 1;
    ACK_FAIL = 2;
 
# Sends and recieves messages from router
class Host(threading.Thread):
    def __init__(self, threadID, router):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self._numTX = 3
        self._rxQueue = collections.deque()
        self._rxLock = threading.Lock()
        self._router = router
        self._rxDone = False
 
    def getRXLock(self):
        return self._rxLock
 
    def getRXQueue(self):
        return self._rxQueue
     
    def readBuffer(self):
        cur_message = []
        while len(self._rxQueue) > 0:
            cur_byte = self._rxQueue.popleft()
            if len(cur_message) == 0 and cur_byte != ord(START_BYTE):
                print("Thread:", self.threadID,  "Didn't find start byte!!")
                break
            elif cur_byte == ord(STOP_BYTE):
                cur_message.append(cur_byte)
                pass # send ack
                break
            else:
                cur_message.append(cur_byte)
        return cur_message
         
    def transmit(self):
        if self._numTX > 0:
            with self._router.getRXLock():
                self._numTX -= 1
                rxQueue = self._router.getRXQueue()
                address = random.randint(1,self._router.numClients())

                # Creates a random message and filters out the start/stop bytes from it
                message = [random.randint(ord('!'),ord('~')) for _ in range(random.randint(1,20))]
                message = list(filter(lambda x: x != ord(START_BYTE) and x != ord(STOP_BYTE), message))

                checksum = (ord(START_BYTE) + self.threadID + address + Type.MESSAGE.value + sum(message) + self.threadID) % 256
                output = [ord(START_BYTE)] + [self.threadID] + [address] + [Type.MESSAGE.value] + message + [checksum] + [ord(STOP_BYTE)]
                for byte in output:
                    rxQueue.append(byte)

    # I'm actually a bit proud of this function, since it is concise and works well in this class and the subclass :)
    def transmitDone(self, thread):
        with thread.getRXLock():
            rxQueue = thread.getRXQueue()
            done_message = [ord(START_BYTE)] + [self.threadID] + [thread.threadID] + [Type.DONE.value] + [ord(STOP_BYTE)]
            for byte in done_message:
                rxQueue.append(byte)

    def run(self):
         
        while self._numTX > 0 or not self._rxDone:
           
            #print('running RXTX')  
            self.transmit()
            with self._rxLock:
                while True:
                    message = self.readBuffer()
                    if len(message) > 0:
                        message_from = message[1]
                        message_to = message[2]
                        message_type = message[3]
                        if len(message) == 0:
                            break
                        if message_type == Type.DONE.value:
                            self._rxDone = True
                            break
                        if message_type == Type.MESSAGE.value: 
                            print('From:', message_from, 'To:', message_to, 'Message:', ''.join(list(map(chr, message[4:-2]))))
                    else:
                        break
            if (self._numTX == 0):
                self.transmitDone(self._router)
                self._numTX -= 1
                print('Thread ', self.threadID, 'sent done to router')
            #print('sleeping Host')
            #time.sleep(0.1)

# Recieves and forwards messages from clients in clientList
# I haven't designed these classes very well, the function signatures for overidden methods 
# (__init__ and transmit) are different and Router only reuses readBuffer from RXTX
class Router(Host):
    def __init__(self, threadID, clientList):
        super().__init__(threadID, self)
        self._clientList = clientList
        self._doneTX = set()
      
    def numClients(self):
        return len(self._clientList)-1

    def transmit(self, message, destination):
        with self._clientList[destination].getRXLock():
            rxQueue = self._clientList[destination].getRXQueue()
            #print('sending message to client!')
            #print('Message: ', message)
            for byte in message:
                rxQueue.append(byte)
          
    def run(self):
 
        while len(self._doneTX) < len(self._clientList) - 1 or len(self._rxQueue) > 0:
            #print('starting router, done: ', len(self._doneTX))

            with self._rxLock:
                print('Running Router, queue length:', len(self.getRXQueue()))
                message = self.readBuffer()
                if len(message) > 0:
                    if message[3] == Type.DONE.value:
                        print('Received DONE from thread', message[1])
                        self._doneTX.add(message[1])
                    else:
                        self.transmit(message, message[2])

            #print('sleeping router')
            #time.sleep(0.01)

        for client in self._clientList[1:]:
            self.transmitDone(client)
        
        print('Router DONE!')
 
threadList = []
threadList.append(Router(0,threadList))
for i in range(1,5):
    threadList.append(Host(i, threadList[0]))
for thread in threadList:
    thread.start()
