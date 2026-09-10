# Preview capture (stock-format preview.png)

The preview is the theme's public face and a hard authenticity gate: it must be
a real capture of the applied theme on a real desktop - wallpaper + themed bar
+ a themed terminal - never fabricated UI. Stock previews are **1800x1012**
desktop screenshots.

Read the window-safety protocol in the main [SKILL.md](../SKILL.md) before
following this recipe - it is mandatory, and every step below assumes it.

## Why this is delicate

Preview capture tempts agents to move/close "the preview window" with Hyprland
dispatchers. On current Omarchy (quattro), several window dispatchers act on
**the focused window**, not the window you meant. During two earlier theme
builds in this collection, focus-dependent `window.kill()`/`window.move` calls
aimed at a preview terminal closed the user's live browser instead. The
protocol below prevents that class of damage; "restore the browser afterward"
is not a safety mechanism.

## Window-safety protocol (mandatory)

1. **Identify the exact target window before acting.** List clients with
   `hyprctl clients -j` and select the window whose address, class/app-id, AND
   title match the terminal you spawned. Give the spawned terminal a
   distinctive app-id at creation (`foot --app-id=theme-preview-<slug>`) and
   record its address/PID at spawn time.
2. **Verify before every operation.** Re-read `hyprctl clients -j` and confirm
   the window you are about to act on still exists, still matches the recorded
   address/class/title, and - for any API that acts on the focused window -
   carries the `focused` flag on that exact address.
3. **Prefer explicitly targeted mechanisms over focus-dependent ones:**
   output-targeted capture (`grim -o <output>`), workspace-indexed switches,
   self-terminating preview terminals (bounded `sleep`, or a signal to the
   exact recorded PID), and window rules registered **before** spawn.
4. **Never** call a focus-dependent dispatcher against "whatever is focused"
   without the verification in step 2, and never use a destructive dispatcher
   when a targeted alternative exists.
5. **Stop if the target is ambiguous** - multiple candidates, no match, or a
   mismatched title/class/address. Fall back to compositing instead.
6. If a capture has already gone wrong, verify which clients remain
   (`hyprctl clients -j`) before making any further dispatcher call.

## Recipe (happy path)

1. **Prepare an empty workspace.** With the target monitor focused
   (`hl.dsp.focus{direction="left"}` or similar), switch to an unused
   workspace: `hyprctl repl 'return hl.dsp.focus{workspace=N}'`. Focus the
   empty workspace BEFORE spawning anything - a newly spawned window lands on
   the focused workspace, and moving it later is exactly the focus-dependent
   operation to avoid.
2. **Spawn a self-terminating themed terminal.** Run it in the background so
   it survives independently, with a distinctive app-id, a bounded lifetime,
   and its PID recorded:

   ```bash
   foot --app-id=theme-preview-<slug> -w 1400x800 sh -c \
     'omarchy dev theme-preview <colors.toml> --no-osc; sleep 300' &
   echo $! > /tmp/theme-preview.pid
   ```

   The bounded `sleep` means the window cleans itself up even if later steps
   fail - no `window.kill()` needed on the happy path.
3. **Verify the spawn.** `hyprctl clients -j` - find the client whose
   `class`/`app-id` is `theme-preview-<slug>`, note its `address` and that it
   sits on the expected workspace. If it is not uniquely identifiable, stop and
   go composite.
4. **Optionally float it via a pre-registered rule.** Rules apply to NEW
   windows only, so register before spawning:

   ```bash
   hyprctl repl 'local r = hl.window_rule{class="theme-preview-<slug>", size={1400,800}, position={100,100}, floating=true} return "ok"'
   ```

   If the window still comes up tiled, do not fight geometry with
   focus-dependent float/move/resize calls - capture it full-bleed and
   composite instead.
5. **Capture the monitor**, not the window:

   ```bash
   grim -o <monitor> wallpaper.png
   ```

6. **Clean up by PID.** `kill $(cat /tmp/theme-preview.pid)` - or simply let
   the bounded `sleep` expire. Only use `window.close()`/`window.kill()` if
   you have re-verified the exact window address per the protocol.
7. **Post-process**: resize to exactly 1800x1012 (LANCZOS), quantize to
   <= 256 colors (`im.quantize(colors=256, method=Image.MEDIANCUT, dither=NONE)`),
   save optimized - target ~300-800 KB.

## Busy desktop / unreliable geometry -> composite

If the user's desktop is busy, exact geometry control is unreliable, or any
target is ambiguous: capture the wallpaper+bar on the empty workspace of one
monitor, capture the themed terminal wherever it renders (tiled full-bleed is
fine), and composite terminal-over-wallpaper. Both inputs must still be
genuine `grim` captures of the applied theme. Full recipe:
[preview-compositing.md](preview-compositing.md).

## Placement rule

The preview panel must not occlude the artwork's focal content - its
wordmark/logo. Locate protected elements programmatically (see the compositing
recipe) rather than by eyeball or vision-model estimates.

## Verification

- Exactly 1800x1012, complete valid PNG, <= 2 MB (repo validator gate).
- One final look at the image: wordmark fully visible, panel text readable,
  reads as a real desktop.
- Pixel-sample any complaint about compositing before reworking - "text
  bleeding through the panel" is usually a misread of dim artwork near the
  panel edge.
