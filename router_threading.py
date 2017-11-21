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
        self._txEvent = threading.Event()
        self._router = router 
        self._clientList = [router] 
        self._prevMessage = None
        self._rxDone = False

    def getTXEvent(self):
        return self._txEvent

    def getRXLock(self):
        return self._rxLock
 
    def getRXQueue(self):
        return self._rxQueue
     
    def readBuffer(self):
        cur_message = []
        all_messages = []
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

    '''
    def transmitEventDecorator(self, message, destination):
        self.transmit(message, destination)
        # Wait for router to acknowledge ack
        while not self._txEvent.wait(timeout=None):
            self.transmitEventDecorator(self._prevMessage, 0)
    '''

    def transmitTypeDecorator(self, messageType, toThreadID, destination=None):
        if not destination:
            destination = toThreadID
        message = [ord(START_BYTE)] + [self.threadID] + [toThreadID] + [messageType] + [ord(STOP_BYTE)]
        self.transmit(message, destination)

    def run(self):
        while self._numTX > 0 or not self._rxDone:
           
            #print('running Host', self.threadID)  
            #print(self._numTX, self._rxDone)
            if self._numTX > 0:
                self._numTX -= 1
                print('thread', self.threadID, 'transmitting')
                self.transmit(self.createMessage(), 0)
                self._txEvent.wait(timeout=1)              
            messages = self.readBuffer()
            for message in messages:
                if len(message) == 0:
                    continue
                message_from = message[1]
                message_to = message[2]
                message_type = message[3]
                if message_type == Type.DONE.value:
                    self._rxDone = True
                if message_type == Type.MESSAGE.value: 
                    print('From:', message_from, 'To:', message_to, 'Message:', ''.join(list(map(chr, message[4:-2]))))
                    #transmitTypeDecorator(Type.ACK.value, message_from, self._router.threadID)
                    
            if (self._numTX == 0):
                self.transmitTypeDecorator(Type.DONE.value, self._router.threadID)
                self._numTX -= 1
                print('Thread ', self.threadID, 'sent done to router')
            #print('sleeping Host')
            #time.sleep(0.1)


class Router(Host):
    def __init__(self, threadID, clientList):
        super().__init__(threadID, self)
        self._clientList = clientList
        self._doneTX = set()
      
    def numClients(self):
        return len(self._clientList)-1

    def run(self):
 
        while len(self._doneTX) < len(self._clientList) - 1 or len(self._rxQueue) > 0:
            print('Running Router, queue length:', len(self.getRXQueue()), 'done:', len(self._doneTX))
            messages = self.readBuffer()
            print(len(messages))
            for message in messages:
                print(message)
                if message[3] == Type.DONE.value:
                    print('Received DONE from thread', message[1])
                    self._doneTX.add(message[1])
                #elif message[3] == Type.ACK.value:
                    #print('clearing tx')
                    #self._clientList[message[2]].getTXEvent().set()
                else:
                    print('router transmitting to Host', message[2])
                    self.transmit(message, message[2])

            #print('sleeping router')
            #time.sleep(0.01)

        for clientID in range(len(self._clientList)):
            self.transmitTypeDecorator(Type.DONE.value, clientID)
        
        print('Router DONE!')
 
threadList = []
threadList.append(Router(0,threadList))
for i in range(1,5):
    threadList.append(Host(i, threadList[0]))
for thread in threadList:
    thread.start()
