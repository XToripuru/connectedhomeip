#!/usr/bin/env -S python3 -B

#
#    Copyright (c) 2025 Project CHIP Authors
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

import enum
import logging
import os
import sys
import pickle
import time
import typing
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import chiptest
import click
import coloredlogs
from chiptest.accessories import AppsRegister
from chiptest.glob_matcher import GlobMatcher
from chiptest.test_definition import TestRunTime, TestTag
from chipyaml.paths_finder import PathsFinder
from run_test_suite import RunContext


def run_test(obj, test, ns, apps_register, paths, pics_file, ble_controller_app, ble_controller_tool, test_timeout_seconds):
    if ns is None:
        runner = chiptest.runner.Runner()
    else:
        runner = chiptest.runner.NamespacedRunner(ns)

    if obj.include_tags:
        if not (test.tags & obj.include_tags):
            logging.debug("Test %s not included" % test.name)
            return

    if obj.exclude_tags:
        if test.tags & obj.exclude_tags:
            logging.debug("Test %s excluded" % test.name)
            return

    test_start = time.monotonic()
    try:
        if obj.dry_run:
            logging.info("Would run test: %s" % test.name)
        else:
            logging.info('%-20s - Starting test' % (test.name))
        test.Run(
            runner, apps_register, paths, pics_file, test_timeout_seconds, obj.dry_run,
            test_runtime=obj.runtime,
            ble_controller_app=ble_controller_app,
            ble_controller_tool=ble_controller_tool)
        if not obj.dry_run:
            test_end = time.monotonic()
            logging.info('%-30s - Completed in %0.2f seconds' %
                         (test.name, (test_end - test_start)))
    except Exception:
        test_end = time.monotonic()
        logging.exception('%-30s - FAILED in %0.2f seconds' %
                          (test.name, (test_end - test_start)))
        return 1

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    data = sys.stdin.buffer.read()

    obj = pickle.loads(data)

    apps_register = AppsRegister()
    apps_register.init()

    result = run_test(obj["context"], obj["test"], obj["ns"], apps_register, obj["paths"], obj["pics_file"],
                      obj["ble_wifi"], obj["ble_controller_app"], obj["ble_controller_tool"], obj["test_timeout_seconds"])

    apps_register.uninit()

    sys.exit(result)
