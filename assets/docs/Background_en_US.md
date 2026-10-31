# Background Running

> This document was translated from the Simplified Chinese version using AI. Last updated: 2026-10-31. If anything differs, the Simplified Chinese version takes precedence.

To keep using your computer while the assistant runs tasks, choose one of the following three approaches:

| Approach | For | Your keyboard and mouse | Setup |
|------|------|-----------|---------|
| Windows background mode (recommended) | Local game on Windows | Clicks, drags, and scrolling do not move the system mouse | Switch in settings |
| Cloud Honkai: Star Rail | Cloud game | Not used | Enable in settings |
| Remote local multi-user desktop (advanced) | Local game on Windows | Does not use your current desktop | Requires modifying system components |

## Windows Background Mode (Recommended)

The game window stays behind your other windows and the assistant operates the game through window messages, so you can keep using your computer while tasks run. Foreground mode remains the default; background mode has to be turned on manually.

### How to Enable

In `Settings → Miscellaneous → Local control mode`, select `Background`, then read and confirm the notice that appears; it takes effect the next time a task starts. Turn Auto Dialogue off and on again to apply it there.

You can also edit the configuration file directly:

```yaml
local_control_mode: background
```

`background_mouse_protection` may remain in an old config file, but it no longer does anything: background input no longer locks or borrows the system mouse.

The cloud game uses its own input method and is not affected by this setting.

### Requirements

- The game window can stay behind other windows but **must not be minimized**: a minimized window cannot be captured and does not process input.
- The lock screen or a secure desktop such as UAC does not block the window messages themselves. If the game locks the cursor to the center of the window during that time, the assistant may be unable to put it back until the system is unlocked.
- If the game runs with administrator privileges, the assistant needs the same privileges (a normally started assistant requests them automatically).
- Background mode always uses window capture; if window capture fails, recognition stops instead of falling back to a desktop screenshot that might include other applications.

### Effects on Your Mouse and Keyboard

This follows BetterGI's background channel: client coordinates go into window messages addressed to the game window. The assistant does not call `SetCursorPos` and does not bring the game forward, so you can keep moving your own mouse.

- **Clicks, hovers, and drags** send `WM_MOUSEMOVE`, `WM_LBUTTONDOWN`, and `WM_LBUTTONUP`. The point is the client coordinate in the message, not where the system cursor is.
- **Scrolling** sends `WM_MOUSEWHEEL`. The screen coordinate is taken from the virtual pointer. The cursor is not moved onto the game, and the game is not brought forward.
- **Keys** still use `WM_KEYDOWN` / `WM_KEYUP` and do not take keyboard focus. When the game is not in front, a `WM_ACTIVATE` is posted first; otherwise Unity drops the input.
- In the **open-world view**, the game may lock the cursor to the center of the window for the short time it believes it is active. If the assistant sees that lock, it puts the cursor back when the action ends. It does not move the cursor onto the button being clicked. Menus usually do not lock the cursor, so the system mouse stays still during clicks.
- A normal attack without coordinates, when the view has captured the cursor, presses and releases at that locked point. It does not reuse a previous UI click and does not move the system cursor.
- Clicks and drags no longer wait while you are using the mouse, and they no longer show "waiting for the mouse to be idle" or "scrolling needs the foreground".

### Window State Changes

- **Switching windows**: bringing the game to the front or switching to another window is normal and does not end the task with an error. The assistant does not pull focus back for a click or a scroll. If the switch happens in the middle of an input, the keys and mouse button held by that input are released first, and the task then recognizes the game screen again; keys, text, clicks, and drags that were already sent are not replayed automatically.
- **Minimized or temporarily invisible**: no input is sent; screenshots and input wait up to 60 seconds and prompt you to restore the game window. Once it is restored, the task continues automatically (the input put on hold during the wait returns as not completed and is not sent later); on timeout the task stops with the reason, for example the log message "游戏窗口已最小化（已等待 60 秒）" (the game window is minimized; waited 60 seconds). Within one period of unavailability the wait happens only once, and time spent paused does not count. The program never restores or activates the game window by itself.
- **Game process exited**: reported immediately as "游戏进程已退出" (the game process has exited) without waiting, and without asking you to restore the window. During game startup, the game is closed and restarted as in foreground mode; in the middle of a task, it ends as a normal error.
- **Game window not found while the process is still running** (for example while the game is starting or recreating its window): the assistant also waits up to 60 seconds, and a timeout is handled as a normal error.
- **Game busy loading**: if the game does not process a mouse message within 0.5 seconds, the input is released and returned as not completed, and the task checks the screen again instead of ending.
- If the window moves or changes size, or the coordinates fall outside the game view during an input, the input is likewise released and returned as not completed.

"Not completed" only means that the input was not fully sent. An operation that was fully sent and only ran into a window switch or pause while finishing still returns success, so the task does not repeat a click or key press that already took effect.

### Pause and Stop

Pausing and stopping first release the keys and mouse held by the backend, then acknowledge the state. After resuming from a pause, interrupted long presses or drags are not replayed; check the current screen before continuing. When you stop a task from the GUI, a stop command is sent first and the GUI waits for the "input released" acknowledgement before ending the process; if no acknowledgement arrives in time, the original forced termination is still used and logged. The command-line `--control <run ID> stop` uses the same command.

### Known Limitations

- The launcher and standalone programs such as Fhoe-Rail and third-party Simulated Universe tools do not gain background capability; run them in the foreground as they require.
- **Exclusive fullscreen**, some anti-cheat, and camera modes that read the real cursor (`GetCursorPos` / Raw Input) instead of the coordinates in the window message may ignore clicks or scrolling. Switch back to foreground mode in that case. BetterGI's background channel also does not support relative movement. This assistant additionally posts `WM_MOUSEWHEEL`; if the game ignores that message, the step needs foreground mode.
- Foreground mode still uses the system mouse and keyboard and does move the real cursor. The cloud game uses its own input and is not affected by local background mode.
- Text input clicks the most recently located input box again within the same activation session and then sends the characters; IME candidates and appending text in arbitrary editors are not supported.
- Currency Wars reward orbs are collected with short sweeps that release the mouse after each segment; if a step is not completed, the current stage is kept and checked again in the next round instead of going straight to purchasing or deploying.
- If you run into recognition or operation problems, switch back to foreground mode first to confirm whether the problem is related to background mode, then report it with the logs.

## Cloud Honkai: Star Rail

With `Cloud Honkai: Star Rail` enabled, tasks such as spending Trailblaze Power, Daily Training, Currency Wars, and Divergent Universe no longer require a fixed window; they support background running and can also run headless. Field farming and Simulated Universe still require the game to stay fullscreen in the foreground.

The cloud game does not depend on a local game window and can also run on macOS, Linux, [Docker](/assets/docs/Docker.md), and [Termux on Android](/assets/docs/Termux.md); see the [Usage Guide](/assets/docs/Tutorial_en_US.md) for how to enable it.

## Remote Local Multi-User Desktop (Advanced)

> On the same computer (no second computer needed), sign in to another Windows user session through local Remote Desktop and let the game and the assistant run there in foreground mode, without using the keyboard and mouse of your current desktop at all. This requires patching the system to allow multiple simultaneous sign-ins, the setup is more involved, and the patch may stop working after system updates. In most cases, try Windows background mode first.

 * Emulators have many drawbacks such as stuttering and high resource usage; running directly on the PC costs less than an emulator
 * We recommend the Remote Desktop service built into Windows
 * Tutorials for enabling multi-user Remote Desktop on Windows (in Chinese):
   * [Detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/) (⭐Recommended⭐)
   * [RDPWrap method](https://blog.sena.moe/win10-multiple-RDP/)
   * [File modification method](https://www.wyr.me/post/701)
 * All files used in the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/): [download link](https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)
   * Alternative links
     * [Baidu Netdisk](https://pan.baidu.com/s/13aoll4n1gmKlPT9WwNYeEw?pwd=jbha) extraction code: jbha
     * [GitHub mirror](https://github.kotori.top/https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)

While the assistant runs in the remote session, keep the Remote Desktop connection open and do not disconnect the session. By default, the remote session stops drawing when the Remote Desktop window is minimized, which may make screenshots fail; if you need to minimize it, create a DWORD value `RemoteDesktop_SuppressWhenMinimized` with data `2` under `HKEY_CURRENT_USER\Software\Microsoft\Terminal Server Client` for your current user, then reopen the Remote Desktop connection.

### For Windows 11 Users

The `SuperRDP` tool mentioned in the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/) may no longer work; we recommend [TermsrvPatcher](https://github.com/fabianosrc/TermsrvPatcher) instead. In mainland China you can also download it from the alternative link: [Lanzou Cloud](https://wwsj.lanzout.com/i4V8u2np8dna).

**Note:** This method only covers step `4. 多用户同时登陆补丁` (the multi-user simultaneous sign-in patch) of the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/); follow the original tutorial for the remaining steps.

**Usage:**

1. Clone the repository with `git clone`, or download the archive directly.
2. After downloading, extract the archive, right-click `TermsrvPatcher.ps1`, and choose "Run"; the script completes everything automatically.

If you prefer to modify the file manually, see the blog post [File modification method](https://www.wyr.me/post/701). Note that some steps in that post may not apply to Windows 11:

- **String to search for in Windows 11 (regex):**
   `39 81 3C 06 00 00 0F (?:[0-9A-F]{2} ){4}00` (in practice, searching for `39 81 3C 06 00 00 0F` is enough; modify it only if the remaining hex bytes match the regex)
- **Replace with:**
   `8B 81 38 06 00 00 39 81 3C 06 00 00 75`
