"""macOS automation via AppleScript / system commands.

Anything that changes state on the machine or could expose personal data is
risk-gated: the UI shows a confirmation dialog before it runs. Messages and
email tools only DRAFT — they open the compose window; the user presses send.
"""
from __future__ import annotations

import subprocess

from ..base import tool


def _osascript(script: str, timeout: int = 30) -> str:
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        return f"AppleScript error: {result.stderr.strip()}"
    return result.stdout.strip() or "OK"


def _q(s: str) -> str:
    """Escape a string for embedding in an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


@tool(
    name="open_app",
    description="Open a macOS application by name, e.g. Safari, Notes, Terminal, Spotify.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "application name"}},
        "required": ["name"],
    },
    agent_tags=["automation"],
)
def open_app(name: str) -> str:
    result = subprocess.run(["open", "-a", name], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return f"Could not open '{name}': {result.stderr.strip()}"
    return f"Opened {name}"


@tool(
    name="quit_app",
    description="Quit a running macOS application by name.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
    risk="confirm",
    agent_tags=["automation"],
)
def quit_app(name: str) -> str:
    return _osascript(f'tell application "{_q(name)}" to quit')


@tool(
    name="open_url",
    description="Open a URL in the default browser.",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
    agent_tags=["automation", "research"],
)
def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    subprocess.run(["open", url], timeout=10)
    return f"Opened {url}"


@tool(
    name="notification",
    description="Show a macOS notification to the user.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}, "message": {"type": "string"}},
        "required": ["title", "message"],
    },
    agent_tags=["automation"],
)
def notification(title: str, message: str) -> str:
    return _osascript(
        f'display notification "{_q(message)}" with title "{_q(title)}"')


@tool(
    name="clipboard_read",
    description="Read the current contents of the clipboard.",
    parameters={"type": "object", "properties": {}},
    risk="confirm",
    agent_tags=["automation"],
)
def clipboard_read() -> str:
    result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
    return result.stdout[:5000] or "(clipboard is empty)"


@tool(
    name="clipboard_write",
    description="Copy text to the clipboard.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    agent_tags=["automation"],
)
def clipboard_write(text: str) -> str:
    subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
    return f"Copied {len(text)} characters to clipboard"


@tool(
    name="create_note",
    description="Create a new note in Apple Notes.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
        "required": ["title", "body"],
    },
    risk="confirm",
    agent_tags=["automation"],
)
def create_note(title: str, body: str) -> str:
    body_html = _q(body).replace("\n", "<br>")
    return _osascript(
        f'tell application "Notes" to make new note at folder "Notes" with properties '
        f'{{name:"{_q(title)}", body:"{body_html}"}}')


@tool(
    name="search_notes",
    description="Search Apple Notes by title/content and return matching note titles.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    risk="confirm",
    agent_tags=["automation", "notes"],
)
def search_notes(query: str) -> str:
    script = f'''
    set out to ""
    tell application "Notes"
        repeat with n in notes
            if (name of n as string) contains "{_q(query)}" or (plaintext of n) contains "{_q(query)}" then
                set out to out & "- " & (name of n) & "\\n"
                if (count of paragraphs of out) > 20 then exit repeat
            end if
        end repeat
    end tell
    return out'''
    result = _osascript(script, timeout=60)
    return result if result not in ("", "OK") else f"No notes matching '{query}'."


@tool(
    name="read_note",
    description="Read the full text of an Apple Note by its exact title.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    },
    risk="confirm",
    agent_tags=["automation", "notes"],
)
def read_note(title: str) -> str:
    out = _osascript(f'tell application "Notes" to get plaintext of note "{_q(title)}"', 30)
    return out[:6000]


@tool(
    name="append_note",
    description="Append text to the end of an existing Apple Note.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
        "required": ["title", "text"],
    },
    risk="confirm",
    agent_tags=["automation", "notes"],
)
def append_note(title: str, text: str) -> str:
    body_html = _q(text).replace("\n", "<br>")
    return _osascript(
        f'tell application "Notes" to set body of note "{_q(title)}" to '
        f'(body of note "{_q(title)}") & "<br>{body_html}"')


@tool(
    name="calendar_create_event",
    description="Create an event in Apple Calendar. Dates use 'YYYY-MM-DD HH:MM' 24h format.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
            "end": {"type": "string", "description": "YYYY-MM-DD HH:MM; default start + 1h"},
            "location": {"type": "string"},
        },
        "required": ["title", "start"],
    },
    risk="confirm",
    agent_tags=["automation", "calendar"],
)
def calendar_create_event(title: str, start: str, end: str = "", location: str = "") -> str:
    import datetime
    try:
        start_dt = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M")
        end_dt = (datetime.datetime.strptime(end, "%Y-%m-%d %H:%M") if end
                  else start_dt + datetime.timedelta(hours=1))
    except ValueError:
        return "Invalid date format — use YYYY-MM-DD HH:MM."
    fmt = "%A, %B %d, %Y %H:%M:%S"  # AppleScript-friendly
    props = f'summary:"{_q(title)}", start date:startD, end date:endD'
    if location:
        props += f', location:"{_q(location)}"'
    script = f'''
    set startD to date "{start_dt.strftime(fmt)}"
    set endD to date "{end_dt.strftime(fmt)}"
    tell application "Calendar"
        tell calendar 1
            make new event with properties {{{props}}}
        end tell
    end tell
    return "created"'''
    out = _osascript(script, timeout=60)
    return (f"Created event '{title}' on {start}." if out == "created" else out)


@tool(
    name="calendar_events",
    description="List Apple Calendar events in a date range (defaults to the next 7 days).",
    parameters={
        "type": "object",
        "properties": {
            "days_ahead": {"type": "integer", "description": "how many days from today (default 7)"},
        },
    },
    risk="confirm",
    agent_tags=["automation", "calendar"],
)
def calendar_events(days_ahead: int = 7) -> str:
    script = f'''
    set output to ""
    set today to current date
    set startOfDay to today - (time of today)
    set endWindow to startOfDay + {max(1, min(days_ahead, 60))} * days
    tell application "Calendar"
        repeat with cal in calendars
            set evs to (every event of cal whose start date >= startOfDay and start date < endWindow)
            repeat with ev in evs
                set output to output & (start date of ev as string) & " — " & (summary of ev) & "\\n"
            end repeat
        end repeat
    end tell
    return output'''
    result = _osascript(script, timeout=90)
    return result if result not in ("", "OK") else "No events in that range."


@tool(
    name="create_reminder",
    description="Create a reminder in Apple Reminders. due is optional, format 'YYYY-MM-DD HH:MM'.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}, "due": {"type": "string"}},
        "required": ["title"],
    },
    risk="confirm",
    agent_tags=["automation"],
)
def create_reminder(title: str, due: str = "") -> str:
    props = f'{{name:"{_q(title)}"}}'
    if due:
        return _osascript(
            f'set dueDate to date "{_q(due)}"\n'
            f'tell application "Reminders" to make new reminder with properties '
            f'{{name:"{_q(title)}", due date:dueDate}}')
    return _osascript(
        f'tell application "Reminders" to make new reminder with properties {props}')


@tool(
    name="calendar_today",
    description="List today's events from Apple Calendar.",
    parameters={"type": "object", "properties": {}},
    risk="confirm",
    agent_tags=["automation"],
)
def calendar_today() -> str:
    script = '''
    set output to ""
    set today to current date
    set startOfDay to today - (time of today)
    set endOfDay to startOfDay + 1 * days
    tell application "Calendar"
        repeat with cal in calendars
            set evs to (every event of cal whose start date >= startOfDay and start date < endOfDay)
            repeat with ev in evs
                set output to output & (start date of ev as string) & " - " & (summary of ev) & "\n"
            end repeat
        end repeat
    end tell
    return output
    '''
    result = _osascript(script, timeout=60)
    return result if result != "OK" else "No events today."


@tool(
    name="draft_imessage",
    description="Open Messages with a drafted text to a recipient. The DRAFT is prepared "
                "but the user must press send themselves — this tool never sends.",
    parameters={
        "type": "object",
        "properties": {
            "recipient": {"type": "string", "description": "phone number or contact handle"},
            "body": {"type": "string"},
        },
        "required": ["recipient", "body"],
    },
    risk="confirm",
    agent_tags=["messaging"],
)
def draft_imessage(recipient: str, body: str) -> str:
    import urllib.parse
    url = f"sms:{urllib.parse.quote(recipient)}&body={urllib.parse.quote(body)}"
    subprocess.run(["open", url], timeout=10)
    return f"Opened Messages with a draft to {recipient}. The user must press send."


@tool(
    name="draft_email",
    description="Open Apple Mail with a drafted email. The DRAFT is prepared but the user "
                "must press send themselves — this tool never sends.",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    risk="confirm",
    agent_tags=["email"],
)
def draft_email(to: str, subject: str, body: str) -> str:
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{_q(subject)}", content:"{_q(body)}", visible:true}}
        tell newMessage to make new to recipient at end of to recipients with properties {{address:"{_q(to)}"}}
        activate
    end tell
    '''
    return _osascript(script)


@tool(
    name="run_applescript",
    description="Run arbitrary AppleScript. Powerful — can control most Mac apps. "
                "Use only when no dedicated tool exists for the task.",
    parameters={
        "type": "object",
        "properties": {"script": {"type": "string"}},
        "required": ["script"],
    },
    risk="dangerous",
    agent_tags=["automation"],
)
def run_applescript(script: str) -> str:
    return _osascript(script, timeout=60)
