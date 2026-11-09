#!/usr/bin/env python3
# net_echo_ws_server —— net_test 的 WebSocket 回声服务端（系统 Python 运行）：
# TCP 分帧回声的 Web 形态（pygame.net Web 端 = WebSocket 同协议——4 字节
# 大端长度前缀帧在 WS 二进制消息内）。纯 stdlib 手写握手+帧编解码。
import base64
import hashlib
import socket
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def ws_recv(conn):
    """读一帧（返回 payload 或 None=关）"""
    h = conn.recv(2)
    if len(h) < 2:
        return None
    op = h[0] & 0x0F
    masked = h[1] & 0x80
    n = h[1] & 0x7F
    if n == 126:
        n = struct.unpack(">H", conn.recv(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", conn.recv(8))[0]
    mask = conn.recv(4) if masked else b"\0\0\0\0"
    data = b""
    while len(data) < n:
        chunk = conn.recv(min(65536, n - len(data)))
        if not chunk:
            return None
        data += chunk
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    if op == 0x8:  # close
        return None
    return data  # 0x1 文本 / 0x2 二进制均回声


def handle(c, addr):
    print("[ws-echo] handshake", addr, flush=True)
    req = b""
    while b"\r\n\r\n" not in req:
        chunk = c.recv(4096)
        if not chunk:
            c.close()
            return
        req += chunk
    key = ""
    for line in req.decode("latin1").split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    c.sendall(
        ("HTTP/1.1 101 Switching Protocols\r\n"
         "Upgrade: websocket\r\nConnection: Upgrade\r\n"
         f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
    print("[ws-echo] open", addr, flush=True)
    try:
        while True:
            msg = ws_recv(c)
            if msg is None:
                break
            # 回声为二进制帧（opcode 0x2，服务端帧不掩码）
            n = len(msg)
            head = bytes([0x82])
            if n < 126:
                head += bytes([n])
            elif n < 65536:
                head += bytes([126]) + struct.pack(">H", n)
            else:
                head += bytes([127]) + struct.pack(">Q", n)
            c.sendall(head + msg)
    except OSError:
        pass
    print("[ws-echo] closed", addr, flush=True)


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 9002))
srv.listen(4)
print("[ws-echo] listening ws://127.0.0.1:9002", flush=True)
while True:
    c, addr = srv.accept()
    handle(c, addr)
