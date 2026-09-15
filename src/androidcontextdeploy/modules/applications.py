"""Brings each ticked catalog app onto the Work Profile, signs it in and pins it.

Per app: (1) open its page in the managed Play Store, unless Intune already
pushed it; (2) wait until `pm list packages --user` sees it; (3) sign in --
the Company Portal through the Enrollment controller, the others through the
Detection Loop; (4) pin it to the home screen.

Android Enterprise forbids adb from launching a Work Profile app, so step 3
often starts with a Manual Action: the technician taps the icon in the Mirror
and Injection takes over from the sign-in screen.
"""
from __future__ import annotations

import time

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import Result
from androidcontextdeploy.signin import SignInDriver

NAME = "applications"

INSTALL_TIMEOUT = 300       # seconds per app
SIGN_IN_TIMEOUT = 600
OPEN_DELAY = 3.0            # let the app reach its first screen


def run(ctx) -> list[Result]:
    selected = {app.name for app in ctx.apps}
    skipped = [Result(app.name, "N/A", t("result.app.not_selected"))
               for app in ctx.manifest.catalog if app.name not in selected]
    if not ctx.apps:
        return skipped or [Result(t("module.applications.title"), "N/A", t("result.app.none"))]

    driver = SignInDriver(ctx.runner, ctx.manifest.organization)
    serial = ctx.device.serial
    results: list[Result] = []
    total = len(ctx.apps)

    for index, app in enumerate(ctx.apps):
        step = f"[{index + 1}/{total}] {app.name}"
        # Enrollment installs on the primary user: the Work Profile does not exist yet.
        user = 0 if app.enrollment else ctx.device.work_user_id
        ctx.runner.emit_app_status(app.name, "waiting")
        ctx.log.info(t("log.app.start", step=step, package=app.package_id))

        # 1. Store
        ctx.runner.emit_progress(index / total, t("progress.app.store", step=step))
        ctx.runner.emit_app_status(app.name, "opening_store")
        if ctx.adb.is_installed(serial, app.package_id, user):
            ctx.log.ok(t("log.app.already_installed", app=app.name))
        else:
            ok, error = ctx.adb.open_play_store(serial, app.package_id, user)
            # "permission to access user" is Android Enterprise refusing a
            # cross-profile launch: normal, Intune pushes required apps itself.
            ctx.log.info(t("log.app.store_opened" if ok else "log.app.store_blocked",
                           app=app.name, user=user))

        # 2. Installed
        ctx.runner.emit_progress((index + 0.25) / total, t("progress.app.install", step=step))
        ctx.runner.emit_app_status(app.name, "installing")
        if not ctx.adb.wait_for_package(serial, app.package_id, user, timeout=INSTALL_TIMEOUT):
            ctx.log.warn(t("log.app.missing", app=app.name, minutes=INSTALL_TIMEOUT // 60))
            ctx.runner.emit_app_status(app.name, "failed")
            results.append(Result(app.name, "WARNING",
                                  t("result.app.missing", minutes=INSTALL_TIMEOUT // 60),
                                  t("remedy.app.missing", app=app.name)))
            continue
        ctx.runner.emit_app_status(app.name, "installed")

        manual: list[str] = []
        done = [t("result.app.installed", user=user)]

        # 3. Sign in
        if app.sign_in:
            ctx.runner.emit_progress((index + 0.5) / total, t("progress.app.sign_in", step=step))
            opened, _ = ctx.adb.open_app(serial, app.package_id, user)
            if opened:
                ctx.runner.emit_app_status(app.name, "auth_pending")
            else:
                ctx.runner.emit_app_status(app.name, "manual")
                ctx.runner.emit_manual_action(app.name, t("manual.open_app", app=app.name))
            time.sleep(OPEN_DELAY)

            if app.enrollment:
                outcome = driver.run_enrollment(ctx.session, ctx.device, app.name)
                ctx.runner.emit_manual_action(app.name, "")
                if outcome == "cancelled":
                    ctx.runner.emit_app_status(app.name, "failed")
                    results.append(Result(app.name, "ERROR", t("result.enrollment.cancelled"),
                                          t("remedy.enrollment.cancelled")))
                    results += [Result(rest.name, "N/A", t("result.app.not_reached"))
                                for rest in ctx.apps[index + 1:]]
                    return results + skipped
                done.append(t("result.enrollment.done"))
                # The Work Profile was just created; the id read at connection is stale.
                ctx.device.work_user_id = ctx.adb.get_work_user_id(serial)
                if ctx.device.work_user_id:
                    ctx.log.ok(t("log.app.work_profile", user=ctx.device.work_user_id))
                else:
                    ctx.log.warn(t("log.app.no_work_profile"))
            else:
                outcome = driver.run_sign_in(ctx.session, ctx.device, app.name,
                                             timeout=SIGN_IN_TIMEOUT)
                ctx.runner.emit_manual_action(app.name, "")
                if outcome == "timeout":
                    manual.append(t("result.app.sign_in_manual"))
                else:
                    done.append(t("result.app.signed_in"))
            ctx.runner.emit_app_status(app.name, "auth_confirmed")

        # 4. Pin
        if app.pin:
            ctx.runner.emit_progress((index + 0.75) / total, t("progress.app.pin", step=step))
            ctx.runner.emit_app_status(app.name, "pinning")
            ok, detail = ctx.adb.pin_to_home(serial, app.package_id, app.name, user)
            if ok:
                done.append(t("result.app.pinned"))
                ctx.runner.emit_app_status(app.name, "pinned")
            else:
                ctx.log.warn(t("log.app.pin_failed", app=app.name, detail=detail or "-"))
                manual.append(t("result.app.pin_manual"))
                ctx.runner.emit_app_status(app.name, "pin_manual")

        if manual:
            # detail = what was done, remedy = what is left by hand
            results.append(Result(app.name, "MANUAL", " · ".join(done), " · ".join(manual)))
        else:
            results.append(Result(app.name, "OK", " · ".join(done)))
        ctx.log.ok(t("log.app.complete", step=step))

    ctx.runner.emit_progress(1.0, t("progress.done"))
    return results + skipped
