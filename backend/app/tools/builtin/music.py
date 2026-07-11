"""Apple Music agent — controls the Music app via AppleScript.

Session-aware: never relaunches Music if it's already running; playback
commands act on the current session.
"""
from __future__ import annotations

import subprocess

from ..base import tool


def _osascript(script: str, timeout: int = 20) -> str:
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "1002" in err or "not authorized" in err.lower():
            return ("Not allowed to control Music yet — macOS will show a permission "
                    "prompt; ask the user to click OK and retry.")
        return f"Music error: {err}"
    return r.stdout.strip() or "OK"


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


@tool(
    name="music_play",
    description="Play music in Apple Music. With a query it searches the user's library "
                "for a matching song/artist/album and plays it; without a query it "
                "resumes playback. Reuses the current Music session.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string",
                                 "description": "song, artist or album; empty = resume"}},
    },
    agent_tags=["automation", "music"],
)
def music_play(query: str = "") -> str:
    if not query:
        return _osascript('tell application "Music" to play')
    script = f'''
    tell application "Music"
        set results to (search library playlist 1 for "{_q(query)}")
        if (count of results) = 0 then return "NOTFOUND"
        play item 1 of results
        set t to item 1 of results
        return "Playing " & (name of t) & " by " & (artist of t)
    end tell'''
    out = _osascript(script)
    if out == "NOTFOUND":
        return (f"'{query}' is not in the user's Apple Music library. Library search "
                f"only — playing from the full Apple Music catalog needs a MusicKit "
                f"integration (not implemented). Offer to play it on YouTube instead.")
    return out


@tool(
    name="music_control",
    description="Control Apple Music playback: pause, resume, next, previous, "
                "shuffle_on, shuffle_off, repeat_on, repeat_off, or 'status' for "
                "the current track.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["pause", "resume", "next", "previous", "shuffle_on",
                                "shuffle_off", "repeat_on", "repeat_off", "status"]},
        },
        "required": ["action"],
    },
    agent_tags=["automation", "music"],
)
def music_control(action: str) -> str:
    scripts = {
        "pause": 'tell application "Music" to pause',
        "resume": 'tell application "Music" to play',
        "next": 'tell application "Music" to next track',
        "previous": 'tell application "Music" to previous track',
        "shuffle_on": 'tell application "Music" to set shuffle enabled to true',
        "shuffle_off": 'tell application "Music" to set shuffle enabled to false',
        "repeat_on": 'tell application "Music" to set song repeat to all',
        "repeat_off": 'tell application "Music" to set song repeat to off',
        "status": 'tell application "Music"\n'
                  'if player state is playing then\n'
                  'return "Playing: " & (name of current track) & " by " & (artist of current track)\n'
                  'else\nreturn "Not playing (" & (player state as string) & ")"\nend if\nend tell',
    }
    if action not in scripts:
        return f"Unknown action '{action}'"
    return _osascript(scripts[action])


@tool(
    name="music_playlists",
    description="List the user's Apple Music playlists, or play one by name.",
    parameters={
        "type": "object",
        "properties": {
            "play": {"type": "string", "description": "playlist name to play; empty = just list"},
        },
    },
    agent_tags=["automation", "music"],
)
def music_playlists(play: str = "") -> str:
    if play:
        return _osascript(f'tell application "Music" to play playlist "{_q(play)}"')
    return _osascript('tell application "Music" to get name of playlists') or "No playlists."


@tool(
    name="music_create_playlist",
    description="Create a new empty playlist in Apple Music, optionally adding library "
                "songs to it by search query.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "add_songs_matching": {"type": "string",
                                   "description": "optional library search; matching songs are added"},
        },
        "required": ["name"],
    },
    risk="confirm",
    agent_tags=["automation", "music"],
)
def music_create_playlist(name: str, add_songs_matching: str = "") -> str:
    out = _osascript(
        f'tell application "Music" to make new user playlist with properties {{name:"{_q(name)}"}}')
    if out.startswith("Music error"):
        return out
    if add_songs_matching:
        add = _osascript(f'''
        tell application "Music"
            set results to (search library playlist 1 for "{_q(add_songs_matching)}")
            repeat with t in results
                duplicate t to user playlist "{_q(name)}"
            end repeat
            return "added " & (count of results) & " songs"
        end tell''')
        return f"Created playlist '{name}' ({add})."
    return f"Created playlist '{name}'."
