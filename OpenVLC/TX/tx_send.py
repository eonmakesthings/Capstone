#!/usr/bin/env python3
import socket
import time

# Parameters
DEST_IP = "192.168.0.2"
DEST_PORT = 10001
PACKET_SIZE = 800      # bytes
BANDWIDTH = 400000     # bits per second

# Calculate packets per second
packets_per_sec = BANDWIDTH / float(PACKET_SIZE * 8)
delay = 1.0 / packets_per_sec

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("Ready to send messages to {}:{} ({}B packets at {:.1f} kbps)...".format(
    DEST_IP, DEST_PORT, PACKET_SIZE, BANDWIDTH / 1000.0))

try:
    while True:
        user_msg = input("\nEnter message to send (or 'quit' to exit): ")
        if user_msg.lower() == "quit":
            break

        full_msg = "<START>" + user_msg + "<END>"

        # Encode and split into packets
        full_bytes = full_msg.encode("utf-8")
        packets = []
        for i in range(0, len(full_bytes), PACKET_SIZE):
            chunk = full_bytes[i:i + PACKET_SIZE]
            if len(chunk) < PACKET_SIZE:
                chunk = chunk.ljust(PACKET_SIZE, b" ")  # pad with spaces
            packets.append(chunk)

        # Send packets
        sent_packets = 0
        for pkt in packets:
            sock.sendto(pkt, (DEST_IP, DEST_PORT))
            sent_packets += 1
            time.sleep(delay)

        print("Message sent. ({} packets)".format(sent_packets))

except KeyboardInterrupt:
    print("\nExiting sender...")

finally:
    sock.close()
