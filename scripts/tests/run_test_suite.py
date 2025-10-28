#!/usr/bin/env -S python3 -B

# Copyright (c) 2021 Project CHIP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
import logging
import os
import pickle
import subprocess
import sys
import typing
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

import chiptest
import click
import coloredlogs
from chiptest.glob_matcher import GlobMatcher
from chiptest.runner import Application
from chiptest.test_definition import TestRunTime, TestTag
from chipyaml.paths_finder import PathsFinder

# If running on Linux platform load the Linux specific code.
if sys.platform == "linux":
    import chiptest.linux

DEFAULT_CHIP_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..'))


class ManualHandling(enum.Enum):
    INCLUDE = enum.auto()
    SKIP = enum.auto()
    ONLY = enum.auto()


# Supported log levels, mapping string values required for argument
# parsing into logging constants
__LOG_LEVELS__ = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'fatal': logging.FATAL,
}


@dataclass
class RunContext:
    root: str
    tests: typing.List[chiptest.TestDefinition]
    in_unshare: bool
    chip_tool: str
    dry_run: bool
    runtime: TestRunTime

    # If not empty, include only the specified test tags
    include_tags: set(TestTag) = field(default_factory={})

    # If not empty, exclude tests tagged with these tags
    exclude_tags: set(TestTag) = field(default_factory={})


@click.group(chain=True)
@click.option(
    '--log-level',
    default='info',
    type=click.Choice(__LOG_LEVELS__.keys(), case_sensitive=False),
    help='Determines the verbosity of script output.')
@click.option(
    '--dry-run',
    default=False,
    is_flag=True,
    help='Only print out shell commands that would be executed')
@click.option(
    '--target',
    default=['all'],
    multiple=True,
    help='Test to run (use "all" to run all tests)'
)
@click.option(
    '--target-glob',
    default='',
    help='What targets to accept (glob)'
)
@click.option(
    '--target-skip-glob',
    default='',
    help='What targets to skip (glob)'
)
@click.option(
    '--no-log-timestamps',
    default=False,
    is_flag=True,
    help='Skip timestaps in log output')
@click.option(
    '--root',
    default=DEFAULT_CHIP_ROOT,
    help='Default directory path for CHIP. Used to copy run configurations')
@click.option(
    '--internal-inside-unshare',
    hidden=True,
    is_flag=True,
    default=False,
    help='Internal flag for running inside a unshared environment'
)
@click.option(
    '--include-tags',
    type=click.Choice(TestTag.__members__.keys(), case_sensitive=False),
    multiple=True,
    help='What test tags to include when running. Equivalent to "exlcude all except these" for priority purpuses.',
)
@click.option(
    '--exclude-tags',
    type=click.Choice(TestTag.__members__.keys(), case_sensitive=False),
    multiple=True,
    help='What test tags to exclude when running. Exclude options takes precedence over include.',
)
@click.option(
    '--runner',
    type=click.Choice(['matter_repl_python', 'chip_tool_python', 'darwin_framework_tool_python'], case_sensitive=False),
    default='chip_tool_python',
    help='Run YAML tests using the specified runner.')
@click.option(
    '--chip-tool',
    help='Binary path of chip tool app to use to run the test')
@click.pass_context
def main(context, dry_run, log_level, target, target_glob, target_skip_glob,
         no_log_timestamps, root, internal_inside_unshare, include_tags, exclude_tags, runner, chip_tool):
    # Ensures somewhat pretty logging of what is going on
    log_fmt = '%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s'
    if no_log_timestamps:
        log_fmt = '%(levelname)-7s %(message)s'
    coloredlogs.install(level=__LOG_LEVELS__[log_level], fmt=log_fmt)

    runtime = TestRunTime.CHIP_TOOL_PYTHON
    if runner == 'matter_repl_python':
        runtime = TestRunTime.MATTER_REPL_PYTHON
    elif runner == 'darwin_framework_tool_python':
        runtime = TestRunTime.DARWIN_FRAMEWORK_TOOL_PYTHON

    if chip_tool is not None:
        chip_tool = Application(kind='tool', path=Path(chip_tool))
    else:
        if not runtime == TestRunTime.MATTER_REPL_PYTHON:
            paths_finder = PathsFinder()
            if runtime == TestRunTime.CHIP_TOOL_PYTHON:
                chip_tool_path = paths_finder.get('chip-tool')
            else:  # DARWIN_FRAMEWORK_TOOL_PYTHON
                chip_tool_path = paths_finder.get('darwin-framework-tool')

            if chip_tool_path is not None:
                chip_tool = Application(kind='tool', path=Path(chip_tool_path)).wrap_with(('python3',))

    if include_tags:
        include_tags = set([TestTag.__members__[t] for t in include_tags])

    if exclude_tags:
        exclude_tags = set([TestTag.__members__[t] for t in exclude_tags])

    # Figures out selected test that match the given name(s)
    if runtime == TestRunTime.MATTER_REPL_PYTHON:
        all_tests = [test for test in chiptest.AllReplYamlTests()]
    elif runtime == TestRunTime.DARWIN_FRAMEWORK_TOOL_PYTHON:
        all_tests = [test for test in chiptest.AllDarwinFrameworkToolYamlTests()]
    else:
        all_tests = [test for test in chiptest.AllChipToolYamlTests()]

    tests = all_tests

    # If just defaults specified, do not run manual and in development
    # Specific target basically includes everything
    if 'all' in target and not include_tags and not exclude_tags:
        exclude_tags = {
            TestTag.MANUAL,
            TestTag.IN_DEVELOPMENT,
            TestTag.FLAKY,
            TestTag.EXTRA_SLOW,
            TestTag.PURPOSEFUL_FAILURE,
        }

        if runtime == TestRunTime.MATTER_REPL_PYTHON:
            exclude_tags.add(TestTag.CHIP_TOOL_PYTHON_ONLY)

    if 'all' not in target:
        tests = []
        for name in target:
            targeted = [test for test in all_tests if test.name.lower()
                        == name.lower()]
            if len(targeted) == 0:
                logging.error("Unknown target: %s" % name)
            tests.extend(targeted)

    if target_glob:
        matcher = GlobMatcher(target_glob.lower())
        tests = [test for test in tests if matcher.matches(test.name.lower())]

    if len(tests) == 0:
        logging.error("No targets match, exiting.")
        logging.error("Valid targets are (case-insensitive): %s" %
                      (", ".join(test.name for test in all_tests)))
        exit(1)

    if target_skip_glob:
        matcher = GlobMatcher(target_skip_glob.lower())
        tests = [test for test in tests if not matcher.matches(
            test.name.lower())]

    tests.sort(key=lambda x: x.name)

    context.obj = RunContext(root=root, tests=tests,
                             in_unshare=internal_inside_unshare,
                             chip_tool=chip_tool, dry_run=dry_run,
                             runtime=runtime,
                             include_tags=include_tags,
                             exclude_tags=exclude_tags)


@main.command(
    'list', help='List available test suites')
@click.pass_context
def cmd_list(context):
    for test in context.obj.tests:
        tags = test.tags_str()
        if tags:
            tags = f" ({tags})"

        print("%s%s" % (test.name, tags))


@main.command(
    'run', help='Execute the tests')
@click.option(
    '--iterations',
    default=1,
    help='Number of iterations to run')
@click.option(
    '--all-clusters-app',
    help='what all clusters app to use')
@click.option(
    '--lock-app',
    help='what lock app to use')
@click.option(
    '--fabric-bridge-app',
    help='what fabric bridge app to use')
@click.option(
    '--ota-provider-app',
    help='what ota provider app to use')
@click.option(
    '--ota-requestor-app',
    help='what ota requestor app to use')
@click.option(
    '--tv-app',
    help='what tv app to use')
@click.option(
    '--bridge-app',
    help='what bridge app to use')
@click.option(
    '--lit-icd-app',
    help='what lit-icd app to use')
@click.option(
    '--microwave-oven-app',
    help='what microwave oven app to use')
@click.option(
    '--rvc-app',
    help='what rvc app to use')
@click.option(
    '--network-manager-app',
    help='what network-manager app to use')
@click.option(
    '--energy-gateway-app',
    help='what energy-gateway app to use')
@click.option(
    '--energy-management-app',
    help='what energy-management app to use')
@click.option(
    '--closure-app',
    help='what closure app to use')
@click.option(
    '--matter-repl-yaml-tester',
    help='what python script to use for running yaml tests using matter-repl as controller')
@click.option(
    '--chip-tool-with-python',
    help='what python script to use for running yaml tests using chip-tool as controller')
@click.option(
    '--pics-file',
    type=click.Path(exists=True),
    default="src/app/tests/suites/certification/ci-pics-values",
    show_default=True,
    help='PICS file to use for test runs.')
@click.option(
    '--keep-going',
    is_flag=True,
    default=False,
    show_default=True,
    help='Keep running the rest of the tests even if a test fails.')
@click.option(
    '--test-timeout-seconds',
    default=None,
    type=int,
    help='If provided, fail if a test runs for longer than this time')
@click.option(
    '--expected-failures',
    type=int,
    default=0,
    show_default=True,
    help='Number of tests that are expected to fail in each iteration.  Overall test will pass if the number of failures matches this.  Nonzero values require --keep-going')
@click.option(
    '--ble-wifi',
    is_flag=True,
    default=False,
    show_default=True,
    help='Use Bluetooth and WiFi mock servers to perform BLE-WiFi commissioning. This option is available on Linux platform only.')
@click.option(
    '--threads',
    type=int,
    default=1,
    show_default=True,
    help='Number of threads used to parallelize tests. Values other than 1 are ignored on non-linux platform.')
@click.pass_context
def cmd_run(context, iterations, all_clusters_app, lock_app, ota_provider_app, ota_requestor_app,
            fabric_bridge_app, tv_app, bridge_app, lit_icd_app, microwave_oven_app, rvc_app, network_manager_app,
            energy_gateway_app, energy_management_app, closure_app, matter_repl_yaml_tester,
            chip_tool_with_python, pics_file, keep_going, test_timeout_seconds, expected_failures, ble_wifi, threads):
    if expected_failures != 0 and not keep_going:
        logging.exception(f"'--expected-failures {expected_failures}' used without '--keep-going'")
        sys.exit(2)

    paths_finder = PathsFinder()

    def build_app(arg_value, kind: str, key: str):
        app_path = arg_value if arg_value else paths_finder.get(key)
        if app_path is not None:
            return Application(kind=kind, path=Path(app_path))
        return None

    all_clusters_app = build_app(all_clusters_app, 'app', 'chip-all-clusters-app')
    lock_app = build_app(lock_app, 'app', 'chip-lock-app')
    fabric_bridge_app = build_app(fabric_bridge_app, 'app', 'fabric-bridge-app')
    ota_provider_app = build_app(ota_provider_app, 'app', 'chip-ota-provider-app')
    ota_requestor_app = build_app(ota_requestor_app, 'app', 'chip-ota-requestor-app')
    tv_app = build_app(tv_app, 'app', 'chip-tv-app')
    bridge_app = build_app(bridge_app, 'app', 'chip-bridge-app')
    lit_icd_app = build_app(lit_icd_app, 'app', 'lit-icd-app')
    microwave_oven_app = build_app(microwave_oven_app, 'app', 'chip-microwave-oven-app')
    rvc_app = build_app(rvc_app, 'app', 'chip-rvc-app')
    network_manager_app = build_app(network_manager_app, 'app', 'matter-network-manager-app')
    energy_gateway_app = build_app(energy_gateway_app, 'app', 'chip-energy-gateway-app')
    energy_management_app = build_app(energy_management_app, 'app', 'chip-energy-management-app')
    closure_app = build_app(closure_app, 'app', 'closure-app')
    matter_repl_yaml_tester = build_app(matter_repl_yaml_tester, 'tool',
                                        'yamltest_with_matter_repl_tester.py').wrap_with(('python3',))

    if chip_tool_with_python is None:
        if context.obj.runtime == TestRunTime.DARWIN_FRAMEWORK_TOOL_PYTHON:
            chip_tool_with_python = build_app(None, 'tool', 'darwinframeworktool.py')
        else:
            chip_tool_with_python = build_app(None, 'tool', 'chiptool.py')

        if chip_tool_with_python is not None:
            chip_tool_with_python = chip_tool_with_python.wrap_with(('python3',))

    if ble_wifi and sys.platform != "linux":
        raise click.BadOptionUsage("ble-wifi", "Option --ble-wifi is available on Linux platform only")

    # Command execution requires an array
    paths = chiptest.ApplicationPaths(
        chip_tool=context.obj.chip_tool,
        all_clusters_app=all_clusters_app,
        lock_app=lock_app,
        fabric_bridge_app=fabric_bridge_app,
        ota_provider_app=ota_provider_app,
        ota_requestor_app=ota_requestor_app,
        tv_app=tv_app,
        bridge_app=bridge_app,
        lit_icd_app=lit_icd_app,
        microwave_oven_app=microwave_oven_app,
        rvc_app=rvc_app,
        network_manager_app=network_manager_app,
        energy_gateway_app=energy_gateway_app,
        energy_management_app=energy_management_app,
        closure_app=closure_app,
        matter_repl_yaml_tester_cmd=matter_repl_yaml_tester,
        chip_tool_with_python_cmd=chip_tool_with_python,
    )

    max_workers = threads if sys.platform == 'linux' else 1

    os.makedirs('logs', exist_ok=True)

    logging.info("Each test will be executed %d times" % iterations)

    for i in range(iterations):
        logging.info("Starting iteration %d" % (i+1))
        observed_failures = 0
        available_ids = Queue()

        for i in range(max_workers):
            available_ids.put(i)

        def run_test_with_id(test, context, paths, pics_file, ble_wifi, test_timeout_seconds):
            index = available_ids.get()
            result = run_test(test, index, context, paths, pics_file, ble_wifi, test_timeout_seconds)
            available_ids.put(index)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_test = {
                executor.submit(run_test_with_id, test, context, paths, pics_file, ble_wifi, test_timeout_seconds): test
                for test in context.obj.tests
            }

            for future in as_completed(future_to_test):
                test = future_to_test[future]
                try:
                    success = future.result()
                    if not success:
                        observed_failures += 1

                    with open(os.path.join("logs", test.name)) as logs:
                        sys.stderr.write(logs.read())
                except Exception as e:
                    logging.exception(f"Exception while running test {test.name}: {e}")
                    observed_failures += 1

        if observed_failures != expected_failures:
            logging.exception(f'Iteration {i}: expected failure count {expected_failures}, but got {observed_failures}')
            sys.exit(2)


def run_test(test, index, context, paths, pics_file, ble_wifi, test_timeout_seconds):
    ble_controller_app = None
    ble_controller_tool = None
    ns = None

    if sys.platform == 'linux':
        ns = chiptest.linux.IsolatedNetworkNamespace(
            index=index,
            # Do not bring up the app interface link automatically when doing BLE-WiFi commissioning.
            setup_app_link_up=not ble_wifi,
            # Change the app link name so the interface will be recognized as WiFi or Ethernet
            # depending on the commissioning method used.
            app_link_name='wlx-app' if ble_wifi else 'eth-app',
            unshared=context.obj.in_unshare)

        if ble_wifi:
            bus = chiptest.linux.DBusTestSystemBus()
            bluetooth = chiptest.linux.BluetoothMock()
            wifi = chiptest.linux.WpaSupplicantMock("MatterAP", "MatterAPPassword", ns)
            ble_controller_app = 0   # Bind app to the first BLE controller
            ble_controller_tool = 1  # Bind tool to the second BLE controller

    obj = {
        "index": index,
        "test": test,
        "context": context.obj,
        "ns": ns,
        "paths": paths,
        "ble_controller_app": ble_controller_app,
        "ble_controller_tool": ble_controller_tool,
        "pics_file": pics_file,
        "test_timeout_seconds": test_timeout_seconds
    }

    payload = pickle.dumps(obj)

    with open(Path('logs') / test.name, "w") as logs:
        if ns is None:
            runner = chiptest.runner.Runner(logs)
        else:
            runner = chiptest.runner.NamespacedRunner(ns, logs)

        test_case = Application(kind='rpc', path=Path('scripts/tests/run_test_case.py')).wrap_with((sys.executable,))

        proc, stdout, stderr = runner.RunSubprocess(test_case, wait=False, stdin=subprocess.PIPE)
        # proc = subprocess.Popen(
        #     cmd,
        #     stdin=subprocess.PIPE,
        #     stdout=logs,
        #     stderr=logs
        # )

        _, _ = proc.communicate(payload)

    if sys.platform == "linux":
        if ble_wifi:
            wifi.terminate()
            bluetooth.terminate()
            bus.terminate()
        ns.terminate()

    return proc.returncode == 0


# On linux, allow an execution shell to be prepared
if sys.platform == 'linux':
    @main.command(
        'shell',
        help=('Execute a bash shell in the environment (useful to test '
              'network namespaces)'))
    @click.pass_context
    def cmd_shell(context):
        chiptest.linux.IsolatedNetworkNamespace(unshared=context.obj.in_unshare)
        os.execvpe("bash", ["bash"], os.environ.copy())


if __name__ == '__main__':
    main(auto_envvar_prefix='CHIP')
