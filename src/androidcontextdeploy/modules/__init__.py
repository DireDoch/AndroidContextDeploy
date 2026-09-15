"""Modules: one area of work each, run in the order of MODULES.

A Module is a file with two things:

    NAME = "my_module"                 # key for module.my_module.* strings
    def run(ctx: Context) -> list[Result]: ...

It talks to the phone through ctx.adb, reports progress through ctx.runner,
never touches the UI, and returns at least one Result. Adding one is: write the
file, append it to MODULES, add its strings to locales/*.json, add a test.
See chapter 7 of the manual before writing one -- most needs are a deploy.json
edit instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from androidcontextdeploy.manifest import AppEntry, Manifest
from androidcontextdeploy.models import AppLogger, DeviceInfo, SessionConfig
from androidcontextdeploy.modules import applications, device_settings, final_check


@dataclass
class Context:
    session: SessionConfig
    device: DeviceInfo
    manifest: Manifest
    apps: list[AppEntry]     # the catalog entries ticked by the technician, in order
    adb: object              # AdbService (or a fake in tests)
    runner: object           # WorkflowRunner
    log: AppLogger


MODULES = [device_settings, applications, final_check]
