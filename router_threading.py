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
    def __init__(self, threadID, router, waiting=False):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self._numTX = 100
        self._rxQueue = collections.deque()
        self._rxLock = threading.Lock()
        self._txEvent = threading.Event()
        self._router = router 
        self._clientList = [router] 
        self._prevMessage = None
        self._rxDone = False
        self._waitToStart = waiting

    def getTXEvent(self):
        return self._txEvent

    def getRXLock(self):
        return self._rxLock
 
    def getRXQueue(self):
        return self._rxQueue
     
    def readBuffer(self):
        all_messages = []
        cur_message = []
        with self._rxLock:
            while len(self._rxQueue) > 0:
                cur_byte = self._rxQueue.popleft()
                if len(cur_message) == 0 and cur_byte != ord(START_BYTE):
                    print("Thread:", self.threadID,  "Didn't find start byte!!")
                    break
                elif cur_byte == ord(STOP_BYTE):
                    cur_message.append(cur_byte)
                    all_messages.append(cur_message)
                    cur_message = []
                else:
                    cur_message.append(cur_byte)
        return all_messages 

    def createMessage(self):
        rxQueue = self._router.getRXQueue()
        address = random.randint(1,self._router.numClients())
        # Creates a random message and filters out the start/stop bytes from it
        message = [random.randint(ord('!'),ord('~')) for _ in range(random.randint(1,20))]
        message = list(filter(lambda x: x != ord(START_BYTE) and x != ord(STOP_BYTE), message))
        checksum = (ord(START_BYTE) + self.threadID + address + Type.MESSAGE.value + sum(message) + self.threadID) % 256
        output = [ord(START_BYTE)] + [self.threadID] + [address] + [Type.MESSAGE.value] + message + [checksum] + [ord(STOP_BYTE)]
        self._prevMessage = output
        return output

    def transmit(self, message, destination):
        client = self._clientList[destination]
        with client.getRXLock():
            rxQueue = self._clientList[destination].getRXQueue()
            for byte in message:
                rxQueue.append(byte)
        client.getTXEvent().set()

    def transmitTypeDecorator(self, messageType, toThreadID, destination=None):
        if destination == None:
            destination = toThreadID
        message = [ord(START_BYTE)] + [self.threadID] + [toThreadID] + [messageType.value] + [ord(STOP_BYTE)]
        print(messageType.name, 'going to', destination)
        self.transmit(message, destination)

    def run(self):
        if self._waitToStart:
            self._txEvent.wait(timeout=1)

        while self._numTX > 0 or not self._rxDone:
            self._txEvent.clear()

            print('Running Host', self.threadID)  
            if self._numTX > 0:
                self._numTX -= 1
                self.transmit(self.createMessage(), 0)
            else:
                self._router.getTXEvent().set()
            messages = self.readBuffer()
            for message in messages:
                message_from = message[1]
                message_to = message[2]
                message_type = message[3]
                if message_type == Type.DONE.value:
                    self._rxDone = True
                if message_type == Type.MESSAGE.value: 
                    print('From:', message_from, 'To:', message_to, 'Message:', ''.join(list(map(chr, message[4:-2]))))
                    #self.transmitTypeDecorator(Type.ACK, message_from, self._router.threadID)
            if (self._numTX == 0):
                self.transmitTypeDecorator(Type.DONE, self._router.threadID)
                self._numTX -= 1
                print('Thread ', self.threadID, 'sent done to router')
                
            self._txEvent.wait(timeout=1)

        print('Stopping thread', self.threadID)


class Router(Host):
    def __init__(self, threadID, clientList, waiting=False):
        super().__init__(threadID, self, waiting)
        self._clientList = clientList
        self._doneTX = set()
      
    def numClients(self):
        return len(self._clientList)-1

    def run(self):
        if self._waitToStart:
            self._txEvent.wait(timeout=1)
         
        while len(self._doneTX) < self.numClients() or len(self._rxQueue) > 0:
            self._txEvent.clear() 

            print('Running Router, queue length:', len(self.getRXQueue()), 'done:', len(self._doneTX))
            messages = self.readBuffer()
            for message in messages:
                if message[3] == Type.DONE.value:
                    print('Received DONE from thread', message[1])
                    self._doneTX.add(message[1])
                    if len(self._doneTX) < self.numClients():
                        wakethreadID = random.choice(list(set(range(1,self.numClients()+1)) - self._doneTX))
                        self._clientList[wakethreadID].getTXEvent().set()
                else:
                    print('router transmitting to Host', message[2])
                    self.transmit(message, message[2])

            print('Router should be waiting')
            self._txEvent.wait(timeout=1)

        for clientID in range(len(self._clientList)):
            self.transmitTypeDecorator(Type.DONE, clientID)
        
        print('Router DONE!')
 
numHosts = 5   
threadList = [None]*(numHosts+1)

threadList[0] = Router(0,threadList, True)
for i in range(1,numHosts):
    threadList[i] = Host(i, threadList[0], True)
threadList[numHosts] = Host(numHosts, threadList[0])
for thread in threadList:
    thread.start()
