#!/bin/sh
# Host tuning for the Minecraft server. Runs at boot via minecraft-perf.service.

# CPU governor: performance on every core that exists
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  [ -w "$g" ] && echo performance > "$g"
done

# Memory: keep the (page-cached) world in RAM, avoid swapping the JVM
echo 10 > /proc/sys/vm/swappiness
echo 5  > /proc/sys/vm/dirty_background_ratio
echo 10 > /proc/sys/vm/dirty_ratio
echo 50 > /proc/sys/vm/vfs_cache_pressure

# 5400rpm HDD (ST500LT012-9WS14): deadline scheduler + long readahead
SCHED=/sys/block/sda/queue/scheduler
grep -q 'mq-deadline' "$SCHED" 2>/dev/null && echo mq-deadline > "$SCHED"
echo 8192 > /sys/block/sda/queue/read_ahead_kb 2>/dev/null || true

# Paper 26.2 binds RCON to server-ip (now all interfaces) and ignores rcon.bind,
# so restrict RCON and Java to loopback + the home LAN.
iptables  -C INPUT -p tcp --dport 25575 ! -i lo -j DROP 2>/dev/null || iptables  -A INPUT -p tcp --dport 25575 ! -i lo -j DROP
ip6tables -C INPUT -p tcp --dport 25575 ! -i lo -j DROP 2>/dev/null || ip6tables -A INPUT -p tcp --dport 25575 ! -i lo -j DROP
iptables  -C INPUT -p tcp --dport 25565 ! -s 192.168.0.0/16 ! -i lo -j DROP 2>/dev/null || iptables -A INPUT -p tcp --dport 25565 ! -s 192.168.0.0/16 ! -i lo -j DROP
