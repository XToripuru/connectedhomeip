#
#    Copyright (c) 2021 Project CHIP Authors
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

"""
Handles linux-specific functionality for running test cases
"""

import logging
import os
import subprocess
import sys
import time

from .test_definition import ApplicationPaths

test_environ = os.environ.copy()


def EnsureNetworkNamespaceAvailability():
    if os.getuid() == 0:
        logging.debug("Current user is root")
        logging.warning("Running as root and this will change global namespaces.")
        return

    os.execvpe(
        "unshare", ["unshare", "--map-root-user", "-n", "-m", "python3",
                    sys.argv[0], '--internal-inside-unshare'] + sys.argv[1:],
        test_environ)


def EnsurePrivateState():
    logging.info("Ensuring /run is privately accessible")

    logging.debug("Making / private")
    if subprocess.run(["mount", "--make-private", "/"]).returncode != 0:
        logging.error("Failed to make / private")
        logging.error("Are you using --privileged if running in docker?")
        sys.exit(1)

    logging.debug("Remounting /run")
    if subprocess.run(["mount", "-t", "tmpfs", "tmpfs", "/run"]).returncode != 0:
        logging.error("Failed to mount /run as a temporary filesystem")
        logging.error("Are you using --privileged if running in docker?")
        sys.exit(1)


class IsolatedNetworkNamespace:
    """Helper class to create and remove network namespaces for tests."""

    # Commands for creating appropriate namespaces for a tool and app binaries
    # in the simulated isolated network.
    COMMANDS_SETUP = [
        # Create 2 virtual hosts: for app and for the tool
        "ip netns add app-{name_suffix}",
        "ip netns add tool-{name_suffix}",
        "ip netns add rpc-{name_suffix}",

        # Create links for switch to net connections
        "ip link add {app_link_name}-{name_suffix} type veth peer name eth-app-sw-{name_suffix}",
        "ip link add {tool_link_name}-{name_suffix} type veth peer name eth-tool-sw-{name_suffix}",
        "ip link add {rpc_link_name}-{name_suffix} type veth peer name eth-rpc-sw-{name_suffix}",

        # Link the connections together
        "ip link set {app_link_name}-{name_suffix} netns app-{name_suffix}",
        "ip link set {tool_link_name}-{name_suffix} netns tool-{name_suffix}",
        "ip link set {rpc_link_name}-{name_suffix} netns rpc-{name_suffix}",

        # Bridge all the connections together.
        "ip link add name br1-{name_suffix} type bridge",
        "ip link set br1-{name_suffix} up",
        "ip link set eth-app-sw-{name_suffix} master br1-{name_suffix}",
        "ip link set eth-tool-sw-{name_suffix} master br1-{name_suffix}",
        "ip link set eth-rpc-sw-{name_suffix} master br1-{name_suffix}",
    ]

    # Bring up application connection link.
    COMMANDS_APP_LINK_UP = [
        "ip netns exec app-{name_suffix} ip addr add {app_link_addr}/24 dev {app_link_name}-{name_suffix}",
        "ip netns exec app-{name_suffix} ip link set dev {app_link_name}-{name_suffix} up",
        "ip netns exec app-{name_suffix} ip link set dev lo up",
        "ip link set dev eth-app-sw-{name_suffix} up",
        # Force IPv6 to use ULAs that we control.
        "ip netns exec app-{name_suffix} ip -6 addr flush {app_link_name}-{name_suffix}",
        "ip netns exec app-{name_suffix} ip -6 a add {app_link_addr_ipv6}/64 dev {app_link_name}-{name_suffix}",

    ]

    # Bring up tool (controller) connection link.
    COMMANDS_TOOL_LINK_UP = [
        "ip netns exec tool-{name_suffix} ip addr add {tool_link_addr}/24 dev {tool_link_name}-{name_suffix}",
        "ip netns exec tool-{name_suffix} ip link set dev {tool_link_name}-{name_suffix} up",
        "ip netns exec tool-{name_suffix} ip link set dev lo up",
        "ip link set dev eth-tool-sw-{name_suffix} up",
        # Force IPv6 to use ULAs that we control.
        "ip netns exec tool-{name_suffix} ip -6 addr flush {tool_link_name}-{name_suffix}",
        "ip netns exec tool-{name_suffix} ip -6 a add {tool_link_addr_ipv6}/64 dev {tool_link_name}-{name_suffix}",
    ]

    # Bring up RPC connection link.
    COMMANDS_RPC_LINK_UP = [
        "ip netns exec rpc-{name_suffix} ip addr add {rpc_link_addr}/24 dev {rpc_link_name}-{name_suffix}",
        "ip netns exec rpc-{name_suffix} ip link set dev {rpc_link_name}-{name_suffix} up",
        "ip netns exec rpc-{name_suffix} ip link set dev lo up",
        "ip link set dev eth-rpc-sw-{name_suffix} up",
        # Force IPv6 to use ULAs that we control.
        "ip netns exec rpc-{name_suffix} ip -6 addr flush {rpc_link_name}-{name_suffix}",
        "ip netns exec rpc-{name_suffix} ip -6 a add {rpc_link_addr_ipv6}/64 dev {rpc_link_name}-{name_suffix}",
    ]

    # Commands for removing namespaces previously created.
    COMMANDS_TERMINATE = [
        "ip link set br1-{name_suffix} down",
        "ip link delete br1-{name_suffix}",

        "ip link delete eth-rpc-sw-{name_suffix}",
        "ip link delete eth-tool-sw-{name_suffix}",
        "ip link delete eth-app-sw-{name_suffix}",

        "ip netns del rpc-{name_suffix}",
        "ip netns del tool-{name_suffix}",
        "ip netns del app-{name_suffix}",
    ]

    def __init__(self, name_suffix, index, setup_app_link_up=True, setup_tool_link_up=True,
                 app_link_name='eth-app', tool_link_name='eth-tool',
                 unshared=False):

        if not unshared:
            # If not running in an unshared network namespace yet, try
            # to rerun the script with the 'unshare' command.
            EnsureNetworkNamespaceAvailability()
        else:
            EnsurePrivateState()

        self.name_suffix = name_suffix
        self.rpc_link_addr = '10.10.10.5'
        self.app_link_addr = '10.10.10.1'
        self.tool_link_addr = '10.10.10.2'
        self.app_link_addr_ipv6 = 'fd00:0:1:1::3'
        self.tool_link_addr_ipv6 = 'fd00:0:1:1::2'
        self.rpc_link_addr_ipv6 = 'fd00:0:1:1::1'
        self.app_link_name = app_link_name
        self.tool_link_name = tool_link_name
        self.rpc_link_name = 'eth-rpc'

        self.setup()
        if setup_app_link_up:
            self.setup_app_link_up(wait_for_dad=False)
        if setup_tool_link_up:
            self.setup_tool_link_up(wait_for_dad=False)

        self.setup_rpc_link_up(wait_for_dad=False)
        self._wait_for_duplicate_address_detection()

    def _wait_for_duplicate_address_detection(self):
        # IPv6 does Duplicate Address Detection even though
        # we know ULAs provided are isolated. Wait for 'tentative'
        # address to be gone.
        logging.info('Waiting for IPv6 DaD to complete (no tentative addresses)')
        for _ in range(100):  # wait at most 10 seconds
            if 'tentative' not in subprocess.check_output(['ip', 'addr'], text=True):
                logging.info('No more tentative addresses')
                break
            time.sleep(0.1)
        else:
            logging.warning("Some addresses look to still be tentative")

    def setup(self):
        for command in self.COMMANDS_SETUP:
            self.run(command)

    def setup_app_link_up(self, wait_for_dad=True):
        for command in self.COMMANDS_APP_LINK_UP:
            self.run(command)
        if wait_for_dad:
            self._wait_for_duplicate_address_detection()

    def setup_tool_link_up(self, wait_for_dad=True):
        for command in self.COMMANDS_TOOL_LINK_UP:
            self.run(command)
        if wait_for_dad:
            self._wait_for_duplicate_address_detection()

    def setup_rpc_link_up(self, wait_for_dad=True):
        for command in self.COMMANDS_RPC_LINK_UP:
            self.run(command)
        if wait_for_dad:
            self._wait_for_duplicate_address_detection()

    def run(self, command: str):
        command = command.format(app_link_name=self.app_link_name,
                                 tool_link_name=self.tool_link_name,
                                 rpc_link_name=self.rpc_link_name,
                                 name_suffix=self.name_suffix,
                                 app_link_addr=self.app_link_addr,
                                 tool_link_addr=self.tool_link_addr,
                                 rpc_link_addr=self.rpc_link_addr,
                                 app_link_addr_ipv6=self.app_link_addr_ipv6,
                                 tool_link_addr_ipv6=self.tool_link_addr_ipv6,
                                 rpc_link_addr_ipv6=self.rpc_link_addr_ipv6)
        logging.debug("Executing: %s", command)
        if subprocess.run(command.split()).returncode != 0:
            logging.error("Failed to execute '%s'" % command)
            logging.error("Are you using --privileged if running in docker?")
            sys.exit(1)

    def terminate(self):
        for command in self.COMMANDS_TERMINATE:
            self.run(command)

    def paths_with_network_namespaces(self, paths: ApplicationPaths) -> ApplicationPaths:
        """
        Returns a copy of paths with updated command arrays to invoke the
        commands in an appropriate network namespace.
        """
        return ApplicationPaths(
            chip_tool='ip netns exec tool-{}'.format(self.name_suffix).split() + paths.chip_tool,
            all_clusters_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.all_clusters_app,
            lock_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.lock_app,
            fabric_bridge_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.fabric_bridge_app,
            ota_provider_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.ota_provider_app,
            ota_requestor_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.ota_requestor_app,
            tv_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.tv_app,
            lit_icd_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.lit_icd_app,
            microwave_oven_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.microwave_oven_app,
            rvc_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.rvc_app,
            network_manager_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.network_manager_app,
            energy_gateway_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.energy_gateway_app,
            energy_management_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.energy_management_app,
            bridge_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.bridge_app,
            chip_repl_yaml_tester_cmd='ip netns exec tool-{}'.format(self.name_suffix).split() + paths.chip_repl_yaml_tester_cmd,
            chip_tool_with_python_cmd='ip netns exec tool-{}'.format(self.name_suffix).split() + paths.chip_tool_with_python_cmd,
            closure_app='ip netns exec app-{}'.format(self.name_suffix).split() + paths.closure_app,
        )
