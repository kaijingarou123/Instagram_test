"""Render a short looping fact Reel (7-30 s; 7-15 s is the default loop) from real CC wildlife footage.

Usage:  python scripts/make_loop_reel.py content/reels/<slug>.json [...]
Output: output/reels/<slug>.mp4, -cover.jpg, -caption.txt, -meta.json, -frames.jpg (review sheet)
        (the same files make_reel.py writes, so preflight.py, post_queue.py and publish.py handle it as a "reel")

The format ("loop", see content/PIPELINE.md, Reels):
  * one continuous CC clip from assets/video, cropped 16:9 -> 9:16 around `focus`, no stills, no pans
  * beat 0 is the hook and is fully on screen from frame 0 (the first frame is also the cover)
  * 1-2 more beats deliver ONE sendable fact; every beat sits in the same place, inside the Reels safe zone
  * the end loops: the last LOOP_XF seconds dissolve back into the opening frames and the text returns to the
    hook, so the replay is seamless and the hook is read again
  * species label, source and video credit stay on screen; the credit is added to the caption as well
  * audio (spec "audio", default {"bed": true}): "bed" = a pad synthesised here whose period equals the Reel
    length, plus a quiet tick on each beat, so it loops too and carries no licence risk; "natural" = gain for the
    clip's own soundtrack (loop-dissolved like the picture); "music" = {track: <assets/music library slug>} or
    {file, title, licence} for an owner-downloaded Meta Sound Collection track, synced so a beat hits frame 0 and
    the strongest accent hits spec "hero_at", with the text changes snapped onto beats (see music_sync). Optional TTS narration:
    spec "voice" (Windows System.Speech); a voiced Reel gets a caption disclosure line.
  * spec "experiment" (hook / audio / length / theme arm values) is copied into the meta for the insight agent.

Spec fields: slug, clip {media "folder/01.webm", start s, focus [x, y], zoom (1 = fill; < 1 = blur-fill, top y)}, duration (7-15),
beats [{at, text, say?}], species, source, caption, hashtags, sources, alt_text, format_tags,
optional credit_artist (clean author name when the Commons field is messy), voice {name, rate}, audio, experiment.
"""
import html
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import PALETTE as P, ROOT, font, gradient, wrap  # noqa: E402

VID, OUT = ROOT / "assets" / "video", ROOT / "output" / "reels"
W, H, FPS, SR = 1080, 1920, 30, 44100
X0, X1 = 90, 950                 # text column: clear of the right action rail (~x 980+)
TEXT_TOP = 380                   # beats start here (below the top UI and the species label)
INFO_Y = 1395                    # species / source / credit block; Reels caption UI starts ~1520
LOOP_XF = 0.6                    # seconds of video + text dissolve back into the opening
POP = 0.18                       # beat entry animation, seconds
MAX_S = 30                       # E4 length arm goes up to ~30 s; the default loop is 7-15 s
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
HANDLE = "@" + _CFG["ig_username"]


# --------------------------------------------------------------------------- media
def clip_credit(spec):
    rel = Path(spec["clip"]["media"])
    credits = json.loads((VID / rel.parent / "credits.json").read_text(encoding="utf-8"))
    c = next(c for c in credits if c["file"] == rel.name)
    artist = spec.get("credit_artist") or html.unescape(c.get("artist") or "Unknown").split("(")[0].strip()[:48]
    return c, f"Video: {artist}, {c['license']}, Wikimedia Commons"


def read_frames(spec, n_pre, n):
    """Yield n_pre + n RGB frames (H, W, 3) starting LOOP_XF before clip.start."""
    clip = spec["clip"]
    zoom = float(clip.get("zoom", 1.0))
    fx, fy = clip.get("focus", (0.5, 0.5))
    sh = round(H * zoom)                                   # scale so height fills, then crop around focus
    cx = f"'min(max(iw*{fx}-{W}/2,0),iw-{W})'"
    if zoom >= 1:
        vf = (f"fps={FPS},scale=-2:{sh}:flags=lanczos,"
              f"crop={W}:{H}:{cx}:'min(max(ih*{fy}-{H}/2,0),ih-{H})',unsharp=5:5:0.5")
    else:
        # blur-fill: a close-up that would sit under the text is shrunk and placed lower (`top`, default
        # bottom-aligned above the info block) over a blurred, darkened copy of the same footage
        top = int(clip.get("top", H - sh - 60))
        vf = (f"fps={FPS},split[a][b];[a]scale=-2:{H},crop={W}:{H}:{cx}:0,boxblur=40:3,eq=brightness=-0.10[bg];"
              f"[b]scale=-2:{sh}:flags=lanczos,crop={W}:{sh}:{cx}:0,unsharp=5:5:0.5[fg];[bg][fg]overlay=0:{top}")
    start = float(clip["start"]) - n_pre / FPS
    if start < 0:
        raise SystemExit(f"{spec['slug']}: clip.start must be >= {LOOP_XF} s (the loop dissolve needs footage before it)")
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(VID / clip["media"]),
           "-t", f"{(n_pre + n) / FPS + 0.2:.3f}", "-filter_complex" if zoom < 1 else "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    for k in range(n_pre + n):
        buf = proc.stdout.read(size)
        if len(buf) < size:
            proc.kill()
            raise SystemExit(f"{spec['slug']}: clip too short for start {clip['start']} + {spec['duration']} s")
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    proc.stdout.close()
    proc.kill()


# --------------------------------------------------------------------------- text layers
def halo(lay, radius=14, strength=0.85):
    """Dark soft halo behind text so it reads on bright or busy footage."""
    a = lay.getchannel("A").filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("RGBA", lay.size, (6, 10, 8, 0))
    out.putalpha(a.point(lambda v: int(min(255, v * 1.6) * strength)))
    out.alpha_composite(lay)
    return out


def beat_layer(text, hook):
    """Centred text block for one beat, top at TEXT_TOP. The hook is bigger and amber-underlined."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    width = X1 - X0
    size = 92 if hook else 70
    while True:
        f = font("bold", size)
        lines = wrap(d, text, f, width)
        if len(lines) <= (3 if hook else 4) or size <= 50:
            break
        size -= 4
    lead = round(size * 1.12)
    y = TEXT_TOP
    for ln in lines:
        x = X0 + (width - d.textlength(ln, font=f)) / 2
        d.text((x, y), ln, font=f, fill=P["cream"] + (255,), stroke_width=3, stroke_fill=(10, 14, 12, 255))
        y += lead
    if hook:
        cx = (X0 + X1) // 2
        d.rounded_rectangle((cx - 50, y + 22, cx + 50, y + 31), radius=4, fill=P["amber"] + (255,))
    return halo(lay)


def info_layer(spec, credit):
    """Persistent: handle (top), species, source and video credit (bottom of the safe zone)."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.text((X0, 250), HANDLE, font=font("semi", 32), fill=P["cream"] + (230,))
    f = font("semi", 34)
    label = spec["species"]
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((X0, INFO_Y, X0 + tw + 44, INFO_Y + 56), radius=28, fill=P["amber"] + (240,))
    d.text((X0 + 22, INFO_Y + 6), label, font=f, fill=P["ink"] + (255,))
    for y, text, kind, size, alpha in [(INFO_Y + 72, "Source: " + spec["source"], "reg", 28, 235),
                                       (INFO_Y + 110, credit, "light", 25, 215)]:
        while size > 18 and d.textlength(text, font=font(kind, size)) > X1 - X0:   # never run off screen
            size -= 1
        d.text((X0, y), text, font=font(kind, size), fill=P["cream"] + (alpha,))
    return halo(lay, 10, 0.75)


SCRIM_TOP = gradient(W, H, P["ink"], 150, 0, start=0.0).transpose(Image.FLIP_TOP_BOTTOM)
SCRIM_BOT = gradient(W, H, P["ink"], 0, 190, start=0.62)


def text_alpha(beats, i, n):
    """[(layer index, alpha, scale)] for frame i: pop-in on each beat, dissolve back to the hook at the end."""
    t = i / FPS
    k = max(j for j, b in enumerate(beats) if b["at"] <= t)
    tail = n - round(LOOP_XF * FPS)
    if i >= tail:                                               # loop: last beat -> hook
        a = (i - tail + 1) / (n - tail)
        return [(k, 1 - a, 1.0), (0, a, 1.0)] if k else [(0, 1.0, 1.0)]
    since = t - beats[k]["at"]
    if k == 0 or since >= POP:
        return [(k, 1.0, 1.0)]
    e = since / POP
    e = e * e * (3 - 2 * e)
    return [(k - 1, 1 - e, 1.0), (k, e, 0.94 + 0.06 * e)]


def scaled(layer, s):
    if s >= 0.999:
        return layer
    w, h = round(W * s), round(H * s)
    small = layer.resize((w, h), Image.BILINEAR)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(small, ((W - w) // 2, round(TEXT_TOP * (1 - s))))
    return out


def with_alpha(layer, a):
    if a >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return out


# --------------------------------------------------------------------------- audio
def pad_audio(spec, n_samples):
    """Soft A-minor pad whose partials all repeat exactly every Reel length (seamless loop), with a
    gentle breathing swell and a quiet tick on each beat. Pure synthesis: no third-party audio."""
    L = n_samples / SR
    t = np.arange(n_samples) / SR
    out = np.zeros(n_samples)
    for f0, amp in [(110.0, 0.22), (164.81, 0.16), (220.0, 0.14), (261.63, 0.10), (329.63, 0.08), (440.0, 0.04)]:
        f = round(f0 * L) / L                                   # snap to the loop period
        swell = 0.75 + 0.25 * np.sin(2 * np.pi * t / L * 2 + f0)  # 2 swells per loop
        out += amp * swell * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t))
    rng = np.random.default_rng(7)                              # circular low-passed noise = loops too
    spec_n = np.fft.rfft(rng.standard_normal(n_samples))
    freqs = np.fft.rfftfreq(n_samples, 1 / SR)
    spec_n *= np.exp(-(freqs / 500.0) ** 2)
    out += 0.5 * np.fft.irfft(spec_n, n_samples) / (np.abs(np.fft.irfft(spec_n, n_samples)).max() + 1e-9) * 0.18
    for b in spec["beats"]:                                     # tick: short bell on each beat
        s0 = int(b["at"] * SR)
        m = min(int(0.6 * SR), n_samples - s0)
        tt = np.arange(m) / SR
        out[s0:s0 + m] += 0.12 * np.exp(-tt * 9) * (np.sin(2 * np.pi * 1318.5 * tt) + 0.4 * np.sin(2 * np.pi * 1975.5 * tt))
    return out / np.abs(out).max() * 0.32


def tts(text, voice, rate, wav_path):
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SelectVoice('{voice}'); $s.Rate = {int(rate)}; "
          f"$s.SetOutputToWaveFile('{wav_path}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=text, text=True, check=True)
    with wave.open(str(wav_path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        sr = w.getframerate()
    if sr != SR:
        x = np.interp(np.arange(0, len(x) * SR / sr) * sr / SR, np.arange(len(x)), x)
    return x


def narrate(spec, tmp):
    """TTS each beat, then retime the beats to the narration: each beat starts 0.25 s after the previous line
    ends, and the Reel lasts until the last line ends plus the loop dissolve (still capped at 15 s)."""
    v = spec["voice"]
    clips = [tts(b.get("say", b["text"]), v.get("name", "Microsoft Zira Desktop"), v.get("rate", 1), tmp / f"v{j}.wav")
             for j, b in enumerate(spec["beats"])]
    t = 0.0
    for b, x in zip(spec["beats"], clips):
        b["at"] = round(t, 2)
        t += 0.1 + len(x) / SR + 0.25
    spec["duration"] = max(spec["duration"], round(t + LOOP_XF + 0.3, 1))
    if spec["duration"] > MAX_S:
        raise SystemExit(f"{spec['slug']}: narration needs {spec['duration']} s; shorten the lines or raise voice.rate")
    return clips


def voice_track(spec, clips, n_samples):
    out = np.zeros(n_samples)
    for b, x in zip(spec["beats"], clips):
        s0 = int((b["at"] + 0.1) * SR)
        m = min(len(x), n_samples - s0)
        out[s0:s0 + m] += x[:m]
    return out / (np.abs(out).max() + 1e-9) * 0.9


def natural_audio(spec, n_samples):
    """The clip's own soundtrack for the same window, loop-dissolved like the picture, RMS-normalised."""
    clip = spec["clip"]
    pre = int(LOOP_XF * SR)
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{float(clip['start']) - LOOP_XF:.3f}", "-i", str(VID / clip["media"]),
           "-t", f"{(pre + n_samples) / SR + 0.1:.3f}", "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float64) / 32768
    if len(x) < pre + n_samples:
        raise SystemExit(f"{spec['slug']}: clip has no usable soundtrack for the natural-sound arm")
    head, body = x[:pre], x[pre:pre + n_samples].copy()
    ramp = np.linspace(0, 1, pre)
    body[-pre:] = body[-pre:] * (1 - ramp) + head * ramp
    rms = np.sqrt(np.mean(body ** 2)) + 1e-9
    return np.clip(body * (0.1 / rms), -0.9, 0.9)


MUSIC = ROOT / "assets" / "music"
HOP = 512


def load_music(m, slug):
    """Returns (mono samples, provenance dict). m is one of:
    {"track": <slug in assets/music/library.json>}                      public-domain / CC0 (Wikimedia Commons)
    {"file", "title", "licence": "Meta Sound Collection"}                owner download
    {"file", "title", "artist", "licence": "Pixabay Content License", "source_url", "content_id": false}
                                                                        owner download, no Content ID shield only
    {"file", "title", "licence": "AI-generated", "tool", "plan", "terms_url", "commercial_rights": true}
                                                                        owner-made on a plan whose terms grant
                                                                        commercial rights (free tiers usually don't)"""
    if "track" in m:
        lib = {t["slug"]: t for t in json.loads((MUSIC / "library.json").read_text(encoding="utf-8"))}
        t = lib[m["track"]]
        title = t.get("display") or Path(t["title"].removeprefix("File:")).stem   # clean name if the library has one
        info = {"title": title, "artist": t.get("artist", ""), "licence": t["license"], "source_url": t["page"],
                "source_class": t.get("source_class", "classical-pd"), "content_id": False,
                "credit": f"{title} ({t['license']}, Wikimedia Commons)"}
        path = MUSIC / t["file"]
    else:
        lic, path = m["licence"], ROOT / m["file"]
        if lic == "Meta Sound Collection":
            info = {"source_class": "meta-sound-collection", "credit": f"{m['title']} (Meta Sound Collection)"}
        elif lic == "Pixabay Content License":
            if m.get("content_id") is not False or "pixabay.com/music/" not in m.get("source_url", ""):
                raise SystemExit(f"{slug}: Pixabay music needs source_url and \"content_id\": false (no shield icon)")
            info = {"source_class": "pixabay", "credit": f"{m['title']} by {m['artist']} (Pixabay Content License, "
                                                         f"no Content ID, Pixabay)"}
        elif lic == "AI-generated":
            if m.get("commercial_rights") is not True or not m.get("plan") or not m.get("terms_url"):
                raise SystemExit(f"{slug}: AI music needs tool, a paid plan, terms_url and \"commercial_rights\": true")
            info = {"source_class": "ai-generated", "credit": f"{m['title']} (AI-generated music, {m['tool']} "
                                                              f"{m['plan']}, commercial rights)"}
        else:
            raise SystemExit(f"{slug}: music licence {lic!r} is not allowed (see PIPELINE.md 2R)")
        info.update({k: m.get(k, "") for k in ("title", "artist", "source_url", "tool", "plan", "terms_url")},
                    licence=lic, content_id=False)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768, info


def analyse(x):
    """Onset envelope, tempo (s per beat), beat grid (s) and loudness per hop."""
    n = (len(x) - 2048) // HOP
    frames = np.lib.stride_tricks.sliding_window_view(x, 2048)[::HOP][:n] * np.hanning(2048)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    env = np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)
    env = np.convolve(env, np.hanning(5) / 2.5, mode="same")
    env = (env - env.mean()) / (env.std() + 1e-9)
    rms = np.sqrt((frames ** 2).mean(axis=1))[1:]
    fps = SR / HOP
    lags = np.arange(int(0.33 * fps), int(1.0 * fps))           # 60-180 bpm
    ac = np.array([np.dot(env[:-l], env[l:]) for l in lags])
    period = lags[int(np.argmax(ac))]
    phase = max(range(period), key=lambda ph: env[ph::period].sum())
    grid = np.arange(phase, len(env), period) / fps
    return env, rms, period / fps, grid


def music_sync(spec, x, L):
    """Choose where in the track the Reel starts so that a beat lands on frame 0 (the hook) and the strongest accent
    lands on spec["hero_at"] (the animal's key moment), in a passage loud enough to carry; then snap the text beats
    (unless a voice sets their timing) to the nearest music beat within 0.3 s."""
    env, rms, beat, grid = analyse(x)
    fps = SR / HOP
    hero = float(spec.get("hero_at", spec["beats"][1]["at"] if len(spec["beats"]) > 1 else 0))
    loud = np.median(rms)

    def at(t):
        i = int(t * fps)
        return env[max(i - 2, 0):i + 3].max() if 0 <= i < len(env) else -9

    best, best_o = -1e9, None
    for o in grid:
        if o < LOOP_XF or o + L + 0.2 > len(x) / SR:
            continue
        i0, i1 = int(o * fps), int((o + L) * fps)
        if rms[i0:i1].mean() < 0.6 * loud or rms[i0:i1].min() < 0.05 * loud:   # no near-silent gaps
            continue
        score = at(o) + 2.0 * at(o + hero) + 0.5 * sum(at(o + b["at"]) for b in spec["beats"][1:])
        if score > best:
            best, best_o = score, o
    if best_o is None:
        raise SystemExit(f"{spec['slug']}: no loud enough {L:.0f} s passage in the music track")
    snaps = []
    if not spec.get("voice"):
        rel = grid - best_o
        for b in spec["beats"][1:]:
            near = rel[np.argmin(np.abs(rel - b["at"]))]
            if abs(near - b["at"]) <= 0.3 and 0 < near < L - LOOP_XF - 1.5:
                snaps.append(round(near - b["at"], 2))
                b["at"] = round(float(near), 3)
    return best_o, 60 / beat, hero, snaps


def music_track(spec, x, offset, n_samples, voice=None):
    """The chosen passage, loop-dissolved into the bars just before it, RMS-normalised, ducked under narration."""
    pre = int(LOOP_XF * SR)
    i0 = int(offset * SR)
    head, body = x[i0 - pre:i0], x[i0:i0 + n_samples].copy()
    ramp = np.linspace(0, 1, pre)
    body[-pre:] = body[-pre:] * (1 - ramp) + head * ramp
    body *= 0.12 / (np.sqrt(np.mean(body ** 2)) + 1e-9)
    if voice is not None:                                        # duck about 9 dB while the voice speaks
        env = np.convolve(np.abs(voice), np.ones(int(0.15 * SR)) / (0.15 * SR), mode="same")
        body *= 1 - 0.65 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    return np.clip(body, -0.95, 0.95)


# --------------------------------------------------------------------------- render
def render(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    slug, beats = spec["slug"], spec["beats"]
    if not 7 <= spec["duration"] <= MAX_S:
        raise SystemExit(f"{slug}: duration must be 7-{MAX_S} s")
    if beats[0]["at"] != 0:
        raise SystemExit(f"{slug}: the first beat (the hook) must start at 0")
    if spec.get("voice"):
        raise SystemExit(f"{slug}: no narration (owner rule 28 Oct 2026): remove \"voice\"; use on-screen text and "
                         f"a soothing track (fetch_commons_music.py --list soothing)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f".{slug}-tmp"
    tmp.mkdir(exist_ok=True)
    clips = narrate(spec, tmp) if spec.get("voice") else []
    music = None
    if spec.get("audio", {}).get("music"):                      # before anything reads the beat times
        mx, m_info = load_music(spec["audio"]["music"], slug)
        m_off, m_bpm, m_hero, m_snaps = music_sync(spec, mx, spec["duration"])
        music = (mx, m_off)
    n = round(spec["duration"] * FPS)
    nx = round(LOOP_XF * FPS)
    clip_meta, credit = clip_credit(spec)

    # audio first (a wav ffmpeg muxes in)
    ns = round(n / FPS * SR)
    a_spec = spec.get("audio", {"bed": True})
    parts, audio_desc = [], []
    if a_spec.get("bed", True):
        parts.append(pad_audio(spec, ns) * (0.45 if clips else 1.0))
        audio_desc.append("generated loop pad + beat ticks (synthesised by make_loop_reel.py, no third-party audio)")
    if a_spec.get("natural"):
        parts.append(natural_audio(spec, ns) * float(a_spec["natural"]))
        audio_desc.append(f"natural sound from the CC clip ({clip_meta['license']}, credited)")
    vt = voice_track(spec, clips, ns) if clips else None
    if music:
        parts.append(music_track(spec, *music, ns, vt) * (1.6 if clips else 2.4))
        audio_desc.append(f"music: {m_info['credit']}")
    if clips:
        parts.append(vt * 0.75)
        audio_desc.append("TTS narration (Windows System.Speech, synthetic voice)")
    if not parts:
        raise SystemExit(f"{slug}: no audio source selected")
    audio = np.sum(parts, axis=0)
    # same loudness for every Reel (about -16 dBFS RMS), so the audio experiment compares content, not volume
    audio *= 0.158 / (np.sqrt(np.mean(audio ** 2)) + 1e-9)
    audio = np.tanh(audio / 0.9) * 0.9                          # soft limiter instead of hard clipping
    wav = tmp / "audio.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        pcm = (audio * 32767).astype(np.int16)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())

    mp4 = OUT / f"{slug}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(wav), "-t", f"{n / FPS:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-g", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-movflags", "+faststart", str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    layers = [beat_layer(b["text"], j == 0) for j, b in enumerate(beats)]
    info = info_layer(spec, credit)
    pre, first, last, sheet, steps, prev = [], None, None, [], [], None
    for k, fr in enumerate(read_frames(spec, nx, n)):
        if k < nx:
            pre.append(fr)                                     # footage just before start: the loop tail
            continue
        i = k - nx
        if i >= n - nx:                                        # dissolve into the opening footage
            a = (i - (n - nx) + 1) / nx
            fr = (fr.astype(np.float32) * (1 - a) + pre[i - (n - nx)].astype(np.float32) * a).astype(np.uint8)
        frame = Image.fromarray(fr).convert("RGBA")
        frame.alpha_composite(SCRIM_TOP)
        frame.alpha_composite(SCRIM_BOT)
        for idx, a, s in text_alpha(beats, i, n):
            frame.alpha_composite(with_alpha(scaled(layers[idx], s), a))
        frame.alpha_composite(info)
        rgb = frame.convert("RGB")
        proc.stdin.write(rgb.tobytes())
        if prev is not None and i % 10 == 0:
            steps.append(float(np.abs(np.asarray(rgb, np.float32) - prev).mean()))
        prev = np.asarray(rgb, np.float32)
        if i == 0:
            first = rgb
        if i == n - 1:
            last = rgb
        if i % round(n / 8) == 0:
            sheet.append(rgb.resize((270, 480)))
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"{slug}: ffmpeg failed")

    # loop seam: the last frame should be about as close to the first as two neighbouring frames are
    seam = float(np.abs(np.asarray(last, np.float32) - np.asarray(first, np.float32)).mean())
    step = float(np.median(steps)) if steps else 0.0
    first.save(OUT / f"{slug}-cover.jpg", "JPEG", quality=90)
    sheet.append(last.resize((270, 480)))
    contact = Image.new("RGB", (270 * len(sheet), 480), P["ink"])
    for j, im in enumerate(sheet):
        contact.paste(im, (270 * j, 0))
    contact.save(OUT / f"{slug}-frames.jpg", "JPEG", quality=85)

    caption = spec["caption"].strip()
    caption += f"\n\n{credit} ({clip_meta['title'].removeprefix('File:')})."
    if music:
        caption += f"\nMusic: {m_info['credit']}."
    if spec.get("voice"):
        caption += "\nNarration: computer-generated voice (text-to-speech)."
    caption += "\n\n" + " ".join(spec["hashtags"])
    (OUT / f"{slug}-caption.txt").write_text(caption, encoding="utf-8")
    meta = {
        "slug": slug, "format": "reel", "reel_format": "loop", "size": f"{W}x{H}", "fps": FPS,
        "duration_s": round(n / FPS, 2), "beats": [b["text"] for b in beats],
        "audio": "; ".join(audio_desc), "experiment": spec.get("experiment", {}),
        "synthetic_voice": bool(spec.get("voice")),
        "ai_music": bool(music and m_info["source_class"] == "ai-generated"),
        "ai_disclosure": ("caption discloses computer-generated narration; apply Instagram's AI label (publish by hand)"
                          if spec.get("voice") else
                          "AI-generated music: caption names the tool; apply Instagram's AI label if Meta requires it"
                          if music and m_info["source_class"] == "ai-generated" else
                          "none needed (real footage, no AI imagery or voice)"),
        "caption_chars": len(caption), "hashtags": spec["hashtags"], "format_tags": spec.get("format_tags", []),
        "alt_text": spec.get("alt_text", ""), "sources": spec["sources"],
        "photo_credits": [credit], "video_source": {k: clip_meta[k] for k in ("title", "page", "license", "artist")},
        "music": m_info if music else None, "variant_of": spec.get("variant_of"),
        "music_sync": ({"start_s": round(m_off, 2), "bpm": round(m_bpm), "hero_at": m_hero, "beat_snaps_s": m_snaps}
                       if music else None),
        "clip": spec["clip"], "loop_seam_diff": round(seam, 1), "median_frame_step": round(step, 1), "file_mb": round(mp4.stat().st_size / 1e6, 2),
    }
    (OUT / f"{slug}-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    print(f"{slug}: {n / FPS:.1f}s, {len(beats)} beats, {meta['file_mb']} MB, loop seam {seam:.1f} vs frame step {step:.1f} -> {mp4}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        render(p)
