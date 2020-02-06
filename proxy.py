import sys
import os
import time
import socket
import select

port = 8888

# get cache
if(os.path.exists("cache.txt")):
    f = open("cache.txt")
    cache = f.read()
    cache = eval(cache)
    f.close()
else:
    cache = {} 

#cache = {'path' : [[responses], time last modified]}

#getting cache limit parameter
try:
    cacheLimit = int(sys.argv[1])
except:
    print("invalid format")
    exit(0)

#creating socket in order to receive the request from the client 
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(0)
sock.bind(('localhost', port))
sock.listen(1)

#setting up select and socket bindings
inputs = [sock]
outputs = []
message = {}

socked = {}

counter = 0
end = False

#Keeps running
while inputs:
    #checks if any data is ready
    read, write, execu = select.select(inputs, outputs, inputs)
    
    #goes through all the sockets which are ready to read
    for x in read:
        if x is sock: 
            connection, client_address = x.accept()
            inputs.append(connection)
        else:
            try:
                data = x.recv(4096)
            except:
                data = b""
            
            #getting request from client
            if data and b"GET" in data[0:5]: 
                #modify request to improve handling
                data = data.replace(b"Connection: keep-alive",b"Connection: close")
                data = data.replace(b"Accept-Encoding: gzip, deflate",b"Accept-Encoding: identity")

                aa = data.split(b'\r\n')
                aa = aa[2:]
                aa = b'\r\n'.join(aa)

                ar = data.split()  

                #split the get request and format it into the required format
                overall = ar[1].split(b'/')
                host = overall[1] #parse the string to get the hostname 
                if len(overall) >= 3:
                    get = b'/'.join(overall[2:]) #get the host request sud
                else:
                    get = b"/"

                #ignore the favicon image
                if b"favicon.ico" == host:
                    x.close()
                    inputs.remove(x)
                    if x in outputs:
                        outputs.remove(x)
                    continue

                #modify the request made by the client and cocatenate all the strings together   
                final_result = (b"GET /" + get + b" HTTP/1.1" + b"\r\n"+b"Host: " + host+b"\r\n"+aa) 

                #path of the request
                path = host + get


                currentTime = time.time()
                #sending cached response
                if (cache.get(path) and  currentTime - cache.get(path)[1] <= cacheLimit):
                    response = cache.get(path)[0]

                    outputs.append(x)
                    message.setdefault(x, [[], None, None])
                    message[x][0] = response
                    message[x][1] = path
                    message[x][2] = True
                #sending fresh response
                else:                 
                    try:
                        #create the second socket required to retrieve the response 
                        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
                        sock2.connect((host, 80)) 
                        
                        #bind the response to the client socket
                        outputs.append(sock2)
                        message.setdefault(sock2, [[], None, None])
                        message[sock2][0].append(final_result)
                        message[sock2][1] = path
                        message[sock2][2] = False

                        #bind this socket to the client socket
                        socked[sock2] = x
                    except:
                        pass

            #getting response from web server
            elif data:
                response = data
                # keep reading the response from the webserver until it is finished as we read 4096 bytes everytime 
                while len(response) > 0:
                    path = message.get(x)[1]
                    
                    #bind the response to the client socket
                    outputs.append(socked.get(x))
                    message.setdefault(socked.get(x), [[], None, None])
                    message[socked.get(x)][0].append(response) 
                    message[socked.get(x)][1] = path
                    message[socked.get(x)][2] = False
                    
                    #update the cache
                    cache.setdefault(path, [[], None])
                    cache.get(path)[0].append(response)
                    cache.get(path)[1] = time.time()

                    #get more data
                    response = x.recv(4096)

                #close and remove socket once done reading from it
                if x in message:
                    del message[x]
                if x in socked:
                    del socked[x]
                if x in outputs:
                    outputs.remove(x)
                inputs.remove(x)
                x.close()
            else:
                #close and remove socket since it is empty
                if x in message:
                    del message[x]
                if x in socked:
                    del socked[x]
                if x in outputs:
                    outputs.remove(x)
                inputs.remove(x)
                x.close()
    
    #goes through all the sockets which are ready to write
    for w in write:
        #getting information binded to the socket
        messages = message.get(w, [[]])[0][:]
        path = message.get(w, [[], None])[1]
        cached = message.get(w, [[], None, False])[2]

        #checking for error
        if not messages or not path:
            continue

        firstResponse = messages[0]

        #modifying html response to include a notification box
        if firstResponse.find(b"<body") != -1: #body tag is in the first response
             #find the body tag in the html code of the website 
            bodyIndex = firstResponse.find(b"<body")
            closingIndex = firstResponse.find(b">", bodyIndex)

            #creating the text of the notification
            if(cached):
                begin = b"CACHED VERSION AS OF:"
                timed = cache.get(path)[1]
            else:
                begin = b"FRESH VERSION AT:"
                timed = time.time()
               
            #Modify the time format
            text = begin+str.encode(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timed)))
            notification = b"\n <p style=\"z-index:9999; position:fixed; top:20px; left:20px;"+b"width:200px;height:100px; background-color:yellow; padding:10px; font-weight:bold;\">"+text+b"</p>"
            
            #append the notification box into the html code
            firstResponse = firstResponse[:closingIndex+1] + notification + firstResponse[closingIndex+1:]
            addLength = len(notification)
            
            #calculate the current content length
            clStart = firstResponse.find(b"Content-Length: ")
            clEnd = firstResponse.find(b"\r\n", clStart)
            currentLength = int(firstResponse[clStart+16:clEnd])
            
            #modify the content length to include length of the notification code
            newLength = currentLength + addLength
            newLength = str.encode(str(newLength))
            firstResponse = firstResponse[:clStart] + b"Content-Length: " + newLength + firstResponse[clEnd:] 

            #update messages array with modified response
            messages[0] = firstResponse
        else: #body tag is not in the first response
            mod = False

            #going through each response to find the body tag
            for i in range(1, len(messages)):
                msg = messages[i]

                bodyIndex = msg.find(b"<body")

                if bodyIndex == -1:
                    continue

                mod = True

                closingIndex = msg.find(b">", bodyIndex)
                
                #creating the text of the notification
                if(cached):
                    begin = b"CACHED VERSION AS OF:"
                    timed = cache.get(path)[1]
                else:
                    begin = b"FRESH VERSION AT:"
                    timed = time.time()
                    
                
                #Modify the time format
                text = begin+str.encode(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timed)))
                notification = b"\n <p style=\"z-index:9999; position:fixed; top:20px; left:20px;"+b"width:200px;height:100px; background-color:yellow; padding:10px; font-weight:bold;\">"+text+b"</p>"
                
               #append the notification box into the html code 
                msg = msg[:closingIndex+1] + notification + msg[closingIndex+1:]
                addLength = len(notification)

                #calculate the current content length
                clStart = firstResponse.find(b"Content-Length: ")
                clEnd = firstResponse.find(b"\r\n", clStart)
                currentLength = int(firstResponse[clStart+16:clEnd])
                
                #modify the content length to include length of the notification code
                newLength = currentLength + addLength
                newLength = str.encode(str(newLength))
                firstResponse = firstResponse[:clStart] + b"Content-Length: " + newLength + firstResponse[clEnd:]
                break 

            if mod:
                #update messages array with modified response
                messages[0] = firstResponse        
                messages[i] = msg
        
        #send all the data to client
        for m in messages[:]:  
            try:
                #send each message over to the client 
                w.sendall(m)
            except:
                continue
                
        #socket is done writing and ready to be read
        inputs.append(w)
        outputs.remove(w)
        
    #handling exceptional errors
    for x in execu:
        #close and remove exceptional socket
        if x in message:
            del message[x]
        if x in socked:
            del socked[x]
        if x in outputs:
            outputs.remove(x)
        if x in inputs:
            inputs.remove(x)
        x.close()
    
    #save cache
    f = open("cache.txt", "w")
    f.write(str(cache))
    f.close()




