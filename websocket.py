#!/usr/bin/python

# WebSocket code by mumrah, adjusted appropriately
# Original code here: https://gist.github.com/512987

import time
import struct
import socket
import hashlib
import sys
import re
import logging
import threading
import emotiv

from select import select

try:
    headset = emotiv.Emotiv()
except:
    headset = emotiv.Emotiv(simulation='sample_data')

callbacks = []
queue = []

def reader():
    while True:
        try:
            packet = headset.read()
            queue.append(packet)
            time.sleep(1)
        except:
            headset = emotiv.Emotiv(simulation='sample_data')

def broadcaster():
    while True:
        if len(queue):
            packet = queue.pop(0)
            for callback in callbacks:
                callback(packet)
    
class WebSocket(object):
    handshake = (
        "HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
        "Upgrade: WebSocket\r\n"
        "Connection: Upgrade\r\n"
        "WebSocket-Origin: %(origin)s\r\n"
        "WebSocket-Location: ws://%(bind)s:%(port)s/\r\n"
        "Sec-Websocket-Origin: %(origin)s\r\n"
        "Sec-Websocket-Location: ws://%(bind)s:%(port)s/\r\n"
        "\r\n"
    )
    def __init__(self, client, server):
        self.client = client
        self.server = server
        self.handshaken = False
        self.header = ""
        self.data = ""
        self.compressed = True
        callbacks.append(self.callback)
        
    def feed(self, data):
        if not self.handshaken:
            self.header += data
            if self.header.find('\r\n\r\n') != -1:
                parts = self.header.split('\r\n\r\n', 1)
                self.header = parts[0]
                if self.dohandshake(self.header, parts[1]):
                    print("Handshake successful")
                    self.handshaken = True           
        else:
            self.data += data
            validated = []
            msgs = self.data.split('\xff')
            self.data = msgs.pop()
            for msg in msgs:
                if msg[0] == '\x00':
                    self.onmessage(msg[1:]) 
                    
    def dohandshake(self, header, key=None): 
        digitRe = re.compile(r'[^0-9]')
        spacesRe = re.compile(r'\s')
        part_1 = part_2 = origin = None
        for line in header.split('\r\n')[1:]:
            name, value = line.split(': ', 1)
            if name.lower() == "sec-websocket-key1":
                key_number_1 = int(digitRe.sub('', value))
                spaces_1 = len(spacesRe.findall(value))
                if spaces_1 == 0:
                    return False
                if key_number_1 % spaces_1 != 0:
                    return False
                part_1 = key_number_1 / spaces_1
            elif name.lower() == "sec-websocket-key2":
                key_number_2 = int(digitRe.sub('', value))
                spaces_2 = len(spacesRe.findall(value))
                if spaces_2 == 0:
                    return False
                if key_number_2 % spaces_2 != 0:
                    return False
                part_2 = key_number_2 / spaces_2
            elif name.lower() == "origin":
                origin = value
        if part_1 and part_2:
            challenge = struct.pack('!I', part_1) + struct.pack('!I', part_2) + key
            response = hashlib.md5(challenge).digest()
            handshake = WebSocket.handshake + response
        else:
            logging.warning("Not using challenge + response")
            handshake = WebSocket.handshake

        handshake = handshake % {'origin': origin, 'port': self.server.port, 'bind': self.server.bind }
        self.client.send(handshake)
        return True

    def callback(self, packet):
        self.send(packet.tostring())
        
    def send(self, data):
        self.client.send("\x00"+data+"\xff")
        
    def close(self):
        callbacks.remove(self.callback)
        self.client.close()      

class WebSocketServer(object):
    def __init__(self, bind, port, cls):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.socket.bind((bind, port))
        self.bind = bind
        self.port = port
        self.cls = cls
        self.connections = {}
        self.listeners = [self.socket]
        self.running = True
        self.listen()

    def listen(self, backlog=5):
        self.socket.listen(backlog)
        print("WebSocket server listening on %s" % self.port)
        while self.running:
            rList, wList, xList = select(self.listeners, self.listeners, self.listeners, 1)
            for ready in rList:
                if ready == self.socket:
                    print("New client connection")
                    client, address = self.socket.accept()
                    fileno = client.fileno()
                    print("Client: %s %s" % (client, address))
                    self.listeners.append(fileno)
                    self.connections[fileno] = self.cls(client, self)
                else:
                    print("Client ready for reading %s" % ready)
                    client = self.connections[ready].client

                    data = client.recv(1024)
            
                    fileno = client.fileno()

                    if data:
                        self.connections[fileno].feed(data)
                    else:
                        print("Closing client %s" % ready)
                        self.connections[fileno].close()
                        del self.connections[fileno]
                        self.listeners.remove(ready)
            for failed in xList:
                if failed == self.socket:
                    logging.error("Socket broke")
                    for fileno, conn in self.connections:
                        conn.close()
                    self.running = False

def main(port):
    threading.Thread(target = reader).start()
    threading.Thread(target = broadcaster).start()
    server = WebSocketServer("0.0.0.0", port, WebSocket) 

if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except:
        main(8080)
