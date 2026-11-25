import socket, struct, sys

HOST, PORT = "127.0.0.1", 25575
pw = sys.argv[1]
cmds = sys.argv[2:]


def send(sock, rid, typ, body):
    data = body.encode() + b"\x00\x00"
    sock.sendall(struct.pack("<iii", len(data) + 8, rid, typ) + data)


def recv(sock):
    raw = b""
    while len(raw) < 4:
        c = sock.recv(4 - len(raw))
        if not c:
            raise EOFError
        raw += c
    (ln,) = struct.unpack("<i", raw)
    body = b""
    while len(body) < ln:
        c = sock.recv(ln - len(body))
        if not c:
            raise EOFError
        body += c
    rid, typ = struct.unpack("<ii", body[:8])
    return rid, typ, body[8:-2].decode(errors="replace")


s = socket.create_connection((HOST, PORT), timeout=15)
send(s, 1, 3, pw)
rid, typ, txt = recv(s)
if rid == -1:
    print("AUTH_FAIL")
    sys.exit(2)
for c in cmds:
    send(s, 2, 2, c)
    rid, typ, txt = recv(s)
    print("> " + c)
    print(txt)
