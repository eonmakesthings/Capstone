#!/usr/bin/env python3
import socket
import threading
import re
import math
from functools import partial

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

from geometry_msgs.msg import Twist, TwistStamped
from irobot_create_msgs.action import DriveDistance, RotateAngle


# =========================
# Defaults & Help Text
# =========================
DEFAULT_PORT = 10001
DEFAULT_BIND_IP = "0.0.0.0"

COMMAND_HELP = """
Commands:
  drive forward <meters> [speed <mps>]
  drive backward <meters> [speed <mps>]
  rotate clockwise <degrees> [speed <radps>]
  rotate counterclockwise <degrees> [speed <radps>]
  vel <linear_x_mps> <angular_z_radps>
  stop

Examples:
  drive forward 0.5 speed 0.25
  rotate clockwise 90
  vel 0.2 -0.3
"""


def clamp(val, lo, hi):
    return max(lo, min(val, hi))


def strip_wrappers(text: str) -> str:
    """
    Remove optional framing like <START>...<END> (case-insensitive)
    and collapse whitespace.
    """
    t = text.strip()
    # remove surrounding quotes if sender added them
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1]
    # strip start/end markers anywhere at the edges
    t = re.sub(r'^\s*<\s*start\s*>\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*<\s*end\s*>\s*$', '', t, flags=re.IGNORECASE)
    # normalize whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t


class TurtleBotEthernetBridge(Node):
    def __init__(self):
        super().__init__('turtlebot_ethernet_bridge')

        # ---- Parameters ----
        self.declare_parameter('bind_ip', DEFAULT_BIND_IP)
        self.declare_parameter('bind_port', DEFAULT_PORT)
        # Jazzy prefers stamped messages; default True
        self.declare_parameter('use_twist_stamped', True)
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('default_drive_speed', 0.25)  # m/s
        self.declare_parameter('default_rot_speed', 0.8)     # rad/s
        self.declare_parameter('drive_action', '/drive_distance')
        self.declare_parameter('rotate_action', '/rotate_angle')

        self.bind_ip = self.get_parameter('bind_ip').get_parameter_value().string_value
        self.bind_port = int(self.get_parameter('bind_port').get_parameter_value().integer_value or DEFAULT_PORT)
        self.use_twist_stamped = self.get_parameter('use_twist_stamped').get_parameter_value().bool_value
        self.cmd_vel_topic = self.get_parameter('cmd_vel_topic').get_parameter_value().string_value
        self.default_drive_speed = float(self.get_parameter('default_drive_speed').get_parameter_value().double_value)
        self.default_rot_speed = float(self.get_parameter('default_rot_speed').get_parameter_value().double_value)
        self.drive_action_name = self.get_parameter('drive_action').get_parameter_value().string_value
        self.rotate_action_name = self.get_parameter('rotate_action').get_parameter_value().string_value

        # ---- QoS: RELIABLE for Create 3 velocity subscriber ----
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ---- Publisher for velocity ----
        if self.use_twist_stamped:
            self.vel_pub = self.create_publisher(TwistStamped, self.cmd_vel_topic, qos)
            self.get_logger().info(f'Publishing TwistStamped on {self.cmd_vel_topic}')
        else:
            self.vel_pub = self.create_publisher(Twist, self.cmd_vel_topic, qos)
            self.get_logger().info(f'Publishing Twist on {self.cmd_vel_topic}')

        # ---- Action clients ----
        self.drive_client = ActionClient(self, DriveDistance, self.drive_action_name)
        self.rotate_client = ActionClient(self, RotateAngle, self.rotate_action_name)

        # ---- UDP setup ----
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.bind_ip, self.bind_port))
        except OSError as e:
            self.get_logger().error(f'Failed to bind UDP socket on {self.bind_ip}:{self.bind_port} - {e}')
            raise

        self.get_logger().info(
            f'Listening for commands on {self.bind_ip}:{self.bind_port} (UDP)\n' + COMMAND_HELP
        )

        # ---- Background threads ----
        self._shutdown = False
        threading.Thread(target=self._wait_for_action_servers, daemon=True).start()
        self.listener_thread = threading.Thread(target=self._udp_loop, daemon=True)
        self.listener_thread.start()

    # -------- Action server readiness --------
    def _wait_for_action_servers(self):
        while not self._shutdown and not self.drive_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().warn(f'Waiting for {self.drive_action_name} action server...')
        while not self._shutdown and not self.rotate_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().warn(f'Waiting for {self.rotate_action_name} action server...')
        self.get_logger().info('Action servers ready.')

    # -------- UDP receive loop --------
    def _udp_loop(self):
        self.get_logger().info('UDP listener running.')
        while not self._shutdown:
            try:
                data, addr = self.sock.recvfrom(4096)
            except OSError:
                break
            raw = data.decode('utf-8', errors='ignore')
            text = strip_wrappers(raw)
            if not text:
                continue
            self.get_logger().info(f'Recv from {addr}: "{text}"')
            self._handle_command(text, addr)

    # -------- Command parser/dispatcher --------
    def _handle_command(self, text: str, addr):
        # stop
        if text in ('stop', 'e-stop', 'estop'):
            self._publish_velocity(0.0, 0.0)
            self._reply(addr, 'ok: stopped')
            return

        # vel <vx> <wz>
        m = re.match(r'^(?:vel|velocity)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*$', text, re.I)
        if m:
            vx = clamp(float(m.group(1)), -0.6, 0.6)
            wz = clamp(float(m.group(2)), -2.0, 2.0)
            self._publish_velocity(vx, wz)
            self._reply(addr, f'ok: vel {vx:.3f} {wz:.3f}')
            return

        # drive forward/backward <meters> [speed <mps>]
        m = re.match(
            r'^(?:drive)\s+(forward|backward)\s+([+-]?\d+(?:\.\d+)?)'
            r'(?:\s+speed\s+([+-]?\d+(?:\.\d+)?))?\s*$', text, re.I
        )
        if m:
            direction = m.group(1).lower()
            meters = float(m.group(2))
            speed = float(m.group(3)) if m.group(3) is not None else self.default_drive_speed
            meters = abs(meters) if direction == 'forward' else -abs(meters)
            speed = clamp(speed, 0.05, 0.5)
            self._send_drive_distance(meters, speed, addr)
            return

        # rotate clockwise/counterclockwise <degrees> [speed <radps>]
        m = re.match(
            r'^(?:rotate)\s+(clockwise|counterclockwise|anticlockwise)\s+([+-]?\d+(?:\.\d+)?)'
            r'(?:\s+speed\s+([+-]?\d+(?:\.\d+)?))?\s*$', text, re.I
        )
        if m:
            sense = m.group(1).lower()
            degrees = float(m.group(2))
            rot_speed = float(m.group(3)) if m.group(3) is not None else self.default_rot_speed
            radians = math.radians(abs(degrees))
            if sense == 'clockwise':  # right-hand rule z-up: CW negative
                radians = -radians
            rot_speed = clamp(rot_speed, 0.1, 1.5)
            self._send_rotate_angle(radians, rot_speed, addr)
            return

        # not matched
        self._reply(addr, 'error: could not parse command\n' + COMMAND_HELP)

    # -------- Velocity publisher --------
    def _publish_velocity(self, vx: float, wz: float):
        if self.use_twist_stamped:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.twist.linear.x = vx
            msg.twist.angular.z = wz
        else:
            msg = Twist()
            msg.linear.x = vx
            msg.angular.z = wz
        self.vel_pub.publish(msg)

    # -------- DriveDistance --------
    def _send_drive_distance(self, meters: float, speed: float, addr):
        if not self.drive_client.wait_for_server(timeout_sec=0.5):
            self._reply(addr, f'error: {self.drive_action_name} server not ready')
            return

        goal = DriveDistance.Goal()
        goal.distance = float(meters)
        goal.max_translation_speed = float(speed)

        self.get_logger().info(f'DriveDistance: {meters:.3f} m @ {speed:.2f} m/s')
        fut = self.drive_client.send_goal_async(goal)
        fut.add_done_callback(partial(self._drive_goal_sent, addr=addr))

    def _drive_goal_sent(self, future, addr):
        goal_handle = future.result()
        if not goal_handle or not goal_handle.accepted:
            self._reply(addr, 'error: drive goal rejected')
            return
        self._reply(addr, 'ok: drive goal accepted')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(partial(self._drive_result, addr=addr))

    def _drive_result(self, future, addr):
        _ = future.result().result
        self._reply(addr, 'ok: drive done')

    # -------- RotateAngle --------
    def _send_rotate_angle(self, radians: float, rot_speed: float, addr):
        if not self.rotate_client.wait_for_server(timeout_sec=0.5):
            self._reply(addr, f'error: {self.rotate_action_name} server not ready')
            return

        goal = RotateAngle.Goal()
        goal.angle = float(radians)
        goal.max_rotation_speed = float(rot_speed)

        self.get_logger().info(f'RotateAngle: {math.degrees(radians):.1f} deg @ {rot_speed:.2f} rad/s')
        fut = self.rotate_client.send_goal_async(goal)
        fut.add_done_callback(partial(self._rotate_goal_sent, addr=addr))

    def _rotate_goal_sent(self, future, addr):
        goal_handle = future.result()
        if not goal_handle or not goal_handle.accepted:
            self._reply(addr, 'error: rotate goal rejected')
            return
        self._reply(addr, 'ok: rotate goal accepted')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(partial(self._rotate_result, addr=addr))

    def _rotate_result(self, future, addr):
        _ = future.result().result
        self._reply(addr, 'ok: rotate done')

    # -------- Reply to sender (optional ack over UDP) --------
    def _reply(self, addr, text: str):
        try:
            self.sock.sendto((text + '\n').encode('utf-8'), addr)
        except Exception:
            pass

    # -------- Shutdown --------
    def destroy_node(self):
        self._shutdown = True
        try:
            self.sock.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = TurtleBotEthernetBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
