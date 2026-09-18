from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, body: str, timeout_ms: int = 2500) -> None:
    return


def _notify_windows(title: str, body: str) -> None:
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
        "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$texts = $template.GetElementsByTagName('text'); "
        f"$texts.Item(0).AppendChild($template.CreateTextNode({_ps_quote(title)})) | Out-Null; "
        f"$texts.Item(1).AppendChild($template.CreateTextNode({_ps_quote(body)})) | Out-Null; "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('stt-hotkey').Show($toast)"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        timeout=8,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
