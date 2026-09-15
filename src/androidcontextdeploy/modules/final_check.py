"""Reads the phone one last time before handover: is the Work Profile there,
are the ticked apps still in it, and what is left to do by hand."""
from __future__ import annotations

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import Result

NAME = "final_check"


def run(ctx) -> list[Result]:
    serial = ctx.device.serial
    results: list[Result] = []

    ctx.runner.emit_progress(0.2, t("progress.final.profile"))
    user = ctx.adb.get_work_user_id(serial)
    ctx.device.work_user_id = user
    if any(app.enrollment for app in ctx.manifest.catalog):
        if user:
            results.append(Result(t("result.final.profile"), "OK",
                                  t("result.final.profile_found", user=user)))
        else:
            results.append(Result(t("result.final.profile"), "ERROR",
                                  t("result.final.profile_missing"), t("remedy.final.profile")))

    ctx.runner.emit_progress(0.6, t("progress.final.apps"))
    missing = [app.name for app in ctx.apps
               if not ctx.adb.is_installed(serial, app.package_id, 0 if app.enrollment else user)]
    if ctx.apps:
        present = len(ctx.apps) - len(missing)
        if missing:
            results.append(Result(t("result.final.apps"), "WARNING",
                                  t("result.final.apps_missing", present=present,
                                    total=len(ctx.apps), missing=", ".join(missing)),
                                  t("remedy.final.apps")))
        else:
            results.append(Result(t("result.final.apps"), "OK",
                                  t("result.final.apps_present", present=present, total=len(ctx.apps))))

    # Always left to the technician. Lockdown turns OK when its button is used.
    results.append(Result(t("result.lockdown.name"), "MANUAL", t("result.lockdown.todo")))
    if getattr(ctx.adb, "recorder", None) is not None:
        results.append(Result(t("result.final.diag"), "MANUAL", t("result.final.diag_review")))

    ctx.runner.emit_progress(1.0, t("progress.done"))
    return results
