"""
Ping Collector

Implements ping-based network connectivity testing with Windows-specific optimizations.
"""

import asyncio
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class PingCollector:
    """Collector for ping-based network testing"""

    def __init__(self):
        self.default_timeout = 5  # seconds
        self.default_count = 4    # number of ping packets

    async def ping_async(self, host: str, count: int = None, timeout: int = None) -> Dict[str, Any]:
        """
        Perform asynchronous ping test

        Args:
            host: Target host (IP or hostname)
            count: Number of ping packets (default: 4)
            timeout: Timeout in seconds (default: 5)

        Returns:
            Dictionary with ping results
        """
        count = count or self.default_count
        timeout = timeout or self.default_timeout

        try:
            # Build ping command for Windows
            cmd = self._build_ping_command(host, count, timeout)

            # Execute ping command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return self._parse_ping_output(stdout, host)
            else:
                return {
                    'success': False,
                    'host': host,
                    'error': f"Ping failed with code {process.returncode}",
                    'output': stdout,
                    'stderr': stderr
                }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'host': host,
                'error': f"Ping timed out after {timeout} seconds",
                'timeout': timeout
            }
        except Exception as e:
            logger.error(f"Error pinging {host}: {e}")
            return {
                'success': False,
                'host': host,
                'error': str(e)
            }

    def _build_ping_command(self, host: str, count: int, timeout: int) -> List[str]:
        """
        Build ping command for Windows

        Args:
            host: Target host
            count: Number of packets
            timeout: Timeout in seconds

        Returns:
            Command as list of strings
        """
        # Windows ping command format
        cmd = [
            'ping',
            '-n', str(count),      # Number of packets
            '-w', str(timeout * 1000),  # Timeout in milliseconds
            host
        ]

        return cmd

    def _parse_ping_output(self, output: str, host: str) -> Dict[str, Any]:
        """
        Parse Windows ping command output

        Args:
            output: Ping command output
            host: Target host

        Returns:
            Parsed ping results
        """
        try:
            lines = output.strip().split('\n')

            # Extract statistics
            stats = {}
            reply_times = []
            packet_loss = 0
            ttl = None

            for line in lines:
                # Parse reply lines
                if line.strip().startswith('Reply from'):
                    reply_info = self._parse_reply_line(line)
                    if reply_info:
                        reply_times.append(reply_info['time_ms'])
                        if reply_info.get('ttl'):
                            ttl = reply_info['ttl']

                # Parse packet loss
                if 'packet loss' in line.lower() or 'lost' in line.lower():
                    packet_loss = self._parse_packet_loss(line)

                # Parse final statistics
                if 'Minimum' in line and 'Maximum' in line and 'Average' in line:
                    stats = self._parse_statistics_line(line)

            # Calculate results
            if reply_times:
                avg_time = sum(reply_times) / len(reply_times)
                min_time = min(reply_times)
                max_time = max(reply_times)
                jitter = self._calculate_jitter(reply_times)
            else:
                avg_time = min_time = max_time = jitter = None

            success = len(reply_times) > 0

            return {
                'success': success,
                'host': host,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'packets_sent': len(reply_times) + packet_loss,
                'packets_received': len(reply_times),
                'packet_loss_percent': packet_loss,
                'response_times': reply_times,
                'min_response_time_ms': min_time,
                'max_response_time_ms': max_time,
                'avg_response_time_ms': avg_time,
                'jitter_ms': jitter,
                'ttl': ttl,
                'raw_output': output,
                'additional_data': {
                    'jitter': jitter,
                    'ttl': ttl
                }
            }

        except Exception as e:
            logger.error(f"Error parsing ping output for {host}: {e}")
            return {
                'success': False,
                'host': host,
                'error': f"Failed to parse ping output: {str(e)}",
                'raw_output': output
            }

    def _parse_reply_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ping reply line

        Args:
            line: Reply line from ping output

        Returns:
            Parsed reply info or None
        """
        try:
            # Windows format: "Reply from 8.8.8.8: bytes=32 time=15ms TTL=118"
            # Or: "Reply from 8.8.8.8: bytes=32 time=15ms"
            pattern = r'Reply from [\d.]+: bytes=\d+ time=(\d+)ms(?: TTL=(\d+))?'
            match = re.search(pattern, line)

            if match:
                time_ms = int(match.group(1))
                ttl = int(match.group(2)) if match.group(2) else None

                return {
                    'time_ms': time_ms,
                    'ttl': ttl
                }

            return None

        except Exception as e:
            logger.debug(f"Failed to parse reply line: {line} - {e}")
            return None

    def _parse_packet_loss(self, line: str) -> int:
        """
        Parse packet loss percentage from ping output

        Args:
            line: Line containing packet loss information

        Returns:
            Packet loss percentage
        """
        try:
            # Windows format: "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)"
            pattern = r'\((\d+)%.*loss\)'
            match = re.search(pattern, line)

            if match:
                return int(match.group(1))

            return 0

        except Exception:
            return 0

    def _parse_statistics_line(self, line: str) -> Dict[str, float]:
        """
        Parse statistics line from ping output

        Args:
            line: Statistics line

        Returns:
            Dictionary with min, max, average times
        """
        try:
            # Windows format: "Minimum = 14ms, Maximum = 16ms, Average = 15ms"
            pattern = r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms'
            match = re.search(pattern, line)

            if match:
                return {
                    'min': float(match.group(1)),
                    'max': float(match.group(2)),
                    'avg': float(match.group(3))
                }

            return {}

        except Exception:
            return {}

    def _calculate_jitter(self, response_times: List[float]) -> Optional[float]:
        """
        Calculate jitter (variation in response times)

        Args:
            response_times: List of response times in milliseconds

        Returns:
            Jitter in milliseconds or None
        """
        if len(response_times) < 2:
            return None

        try:
            # Calculate standard deviation of response times
            avg = sum(response_times) / len(response_times)
            variance = sum((time - avg) ** 2 for time in response_times) / len(response_times)
            jitter = variance ** 0.5

            return round(jitter, 2)

        except Exception:
            return None

    async def ping_batch(self, hosts: List[str], count: int = None, timeout: int = None) -> List[Dict[str, Any]]:
        """
        Ping multiple hosts concurrently

        Args:
            hosts: List of hosts to ping
            count: Number of ping packets per host
            timeout: Timeout in seconds

        Returns:
            List of ping results for each host
        """
        if not hosts:
            return []

        tasks = []
        for host in hosts:
            task = asyncio.create_task(self.ping_async(host, count, timeout))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'host': hosts[i],
                    'error': str(result)
                })
            else:
                processed_results.append(result)

        return processed_results

    def get_supported_metrics(self) -> List[str]:
        """
        Get list of metrics supported by this collector

        Returns:
            List of metric names
        """
        return ['ping']

    def validate_host(self, host: str) -> bool:
        """
        Validate host format for ping

        Args:
            host: Host to validate

        Returns:
            True if host appears valid
        """
        if not host or len(host.strip()) == 0:
            return False

        host = host.strip()

        # Basic validation - can be enhanced
        # IP address format (basic check)
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
            return True

        # Hostname format (basic check)
        if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$', host):
            return True

        return len(host) > 0

    async def test_connectivity(self, host: str) -> Dict[str, Any]:
        """
        Quick connectivity test with single ping

        Args:
            host: Host to test

        Returns:
            Connectivity test result
        """
        result = await self.ping_async(host, count=1, timeout=3)

        if result['success']:
            return {
                'connectivity': 'good',
                'host': host,
                'response_time_ms': result.get('avg_response_time_ms'),
                'timestamp': result['timestamp']
            }
        else:
            return {
                'connectivity': 'failed',
                'host': host,
                'error': result.get('error', 'Unknown error'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }