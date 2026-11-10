# net_echo_server —— net_test 的回声服务端（系统 Python 运行，非引擎侧）：
# TCP 127.0.0.1:9001 分帧回声（4 字节大端长度前缀——与 pygame.net 同帧
# 格式）+ 可选 UDP 9051 端口自环由客户端自己完成（不经服务端）。
import socket
import struct
import threading

MAX_FRAME = 16 * 1024 * 1024


def handle(c, addr):
    print("[echo] connected", addr, flush=True)
    try:
        while True:
            head = b""
            while len(head) < 4:
                chunk = c.recv(4 - len(head))
                if not chunk:
                    return
                head += chunk
            (n,) = struct.unpack(">I", head)
            if n > MAX_FRAME:
                return
            body = b""
            while len(body) < n:
                chunk = c.recv(min(65536, n - len(body)))
                if not chunk:
                    return
                body += chunk
            print(f"[echo] {addr} 收到 {len(body)}B: {body[:120]!r}", flush=True)
            payload = b"echo:" + body
            c.sendall(struct.pack(">I", len(payload)) + payload)
    except OSError:
        pass
    finally:
        print("[echo] closed", addr, flush=True)


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 9001))  # 0.0.0.0：同网段真机/模拟器宿主直连
srv.listen(4)
print("[echo] listening 0.0.0.0:9001", flush=True)
while True:
    c, addr = srv.accept()
    threading.Thread(target=handle, args=(c, addr), daemon=True).start()
