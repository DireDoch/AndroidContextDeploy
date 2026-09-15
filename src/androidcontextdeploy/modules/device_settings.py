"""Applies every entry of deploy.json `device_settings` with `settings put`,
then reads each one back. The Result is what the phone reports, not what was
sent: some keys are silently ignored by some manufacturers."""
from __future__ import annotations

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import Result

NAME = "device_settings"


def run(ctx) -> list[Result]:
    settings = ctx.manifest.device_settings
    if not settings:
        return [Result(t("module.device_settings.title"), "N/A", t("result.settings.none"))]

    serial = ctx.device.serial
    results: list[Result] = []
    for index, setting in enumerate(settings):
        ctx.runner.emit_progress(index / len(settings), t("progress.setting", name=setting.name))
        ok, error = ctx.adb.put_setting(serial, setting.namespace, setting.key, setting.value)
        actual = ctx.adb.get_setting(serial, setting.namespace, setting.key)
        where = f"{setting.namespace}/{setting.key}"
        if actual == setting.value:
            ctx.log.ok(t("log.setting.ok", name=setting.name))
            results.append(Result(setting.name, "OK", f"{where} = {actual}"))
        else:
            detail = t("result.setting.mismatch", where=where, actual=actual or "-",
                       expected=setting.value)
            if not ok and error:
                detail += f" ({error})"
            ctx.log.warn(f"{setting.name}: {detail}")
            results.append(Result(setting.name, "WARNING", detail,
                                  t("remedy.setting", index=index)))
    ctx.runner.emit_progress(1.0, t("progress.done"))
    return results
