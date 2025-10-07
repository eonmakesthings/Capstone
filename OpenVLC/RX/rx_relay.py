#!/usr/bin/env python3
import socket
import time

# Parameters
BIND_IP = "192.168.0.2"   # BeagleBone’s IP
BIND_PORT = 10001
PACKET_SIZE = 800
REPORT_INTERVAL = 3  # seconds

DEST_IP = "turtlebot"     # Hostname of TurtleBot (resolves via /etc/hosts or mDNS)
DEST_PORT = 10001

# Create UDP socket for receiving
recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind((BIND_IP, BIND_PORT))

# Create UDP socket for sending (relay)
send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("Listening on {}:{} (UDP, {} packets)...".format(BIND_IP, BIND_PORT, PACKET_SIZE))

start_time = time.time()
last_report = start_time
recv_packets = 0

buffer = ""
inside_message = False

try:
    while True:
        data, addr = recv_sock.recvfrom(PACKET_SIZE)
        recv_packets += 1

        # Decode packet text and strip padding spaces
        chunk = data.decode("utf-8", errors="ignore").strip()

        # Handle possible START marker
        if "<START>" in chunk:
            buffer = ""
            inside_message = True
            start_idx = chunk.find("<START>") + len("<START>")
            chunk = chunk[start_idx:]

        if inside_message:
            if "<END>" in chunk:
                end_idx = chunk.find("<END>")
                buffer += chunk[:end_idx]

                # Print locally
                print("[{}] MESSAGE RECEIVED: {}".format(addr[0], buffer))

                # Relay message to TurtleBot
                full_msg = "<START>" + buffer + "<END>"
                send_sock.sendto(full_msg.encode("utf-8"), (DEST_IP, DEST_PORT))
                print("Relayed message to {}:{}".format(DEST_IP, DEST_PORT))

                # Reset for next message
                buffer = ""
                inside_message = False
            else:
                buffer += chunk

        # Periodic stats
        now = time.time()
        if now - last_report >= REPORT_INTERVAL:
            elapsed = now - start_time
            print("--- Report @ {:.1f}s: received {} packets ---".format(elapsed, recv_packets))
            last_report = now

except KeyboardInterrupt:
    print("\nStopping relay...")

finally:
    recv_sock.close()
    send_sock.close()
