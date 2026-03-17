#Created by Peter Azmy
#!/usr/bin/env python3
"""
SRT → SCC Converter
Converts SubRip (.srt) subtitle files to Scenarist Closed Captions (.scc) format.
Outputs to a folder called SCC_Conversion. Replaces existing files automatically.

Usage:
    python srt_to_scc.py
    (Run from the folder containing your .srt files)
"""

import os
import re
import sys
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    from tqdm import tqdm
except ImportError:
    print("Installing tqdm (progress bar library)...")
    os.system(f'"{sys.executable}" -m pip install tqdm --break-system-packages -q')
    from tqdm import tqdm

# ── Constants ─────────────────────────────────────────────────────────────────
FPS        = 29.97
OUTPUT_DIR = "SCC_Conversion"

# CEA-608 Control Codes (Corrected for Row 14/15, Column 0)
CTRL_EDM  = "942c"  # Erase Displayed Memory
CTRL_ENM  = "94ae"  # Erase Non-Displayed Memory
CTRL_RCL  = "9420"  # Resume Caption Loading
CTRL_EOC  = "942f"  # End of Caption (Flip)
CTRL_PAC1 = "9440"  # PAC: Row 14, Column 0
CTRL_PAC2 = "9460"  # PAC: Row 15, Column 0

# Comprehensive CEA-608 Special Character Map (29 characters)
SPECIAL_CHAR_MAP = {
    "®": "91b6",  "°": "9127",  "½": "9128",  "¿": "9129",
    "™": "912a",  "¢": "912b",  "£": "912c",  "♪": "912d",
    "à": "912e",  "é": "9131",  "â": "9132",  "ê": "9133",
    "î": "9134",  "ô": "9135",  "û": "9136",  "Á": "9137",
    "É": "9138",  "Ó": "9139",  "Ú": "913a",  "Ü": "913b",
    "ü": "913c",  "ó": "913d",  "ú": "913e",  "ñ": "913f",
    "Ñ": "9220",  "á": "9221",  "í": "9223",  "ö": "9228",
    "è": "912e",
}

# ── Timecode Logic ────────────────────────────────────────────────────────────

def srt_time_to_seconds(time_str):
    time_str = time_str.replace(",", ".")
    h, m, rest = time_str.split(":")
    s, ms = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_scc_tc(seconds):
    """Accurate conversion for True Time SRT inputs using floor math and semicolon."""
    total_frames = int(seconds * FPS)
    ff = total_frames % 30
    total_secs = total_frames // 30
    hh = total_secs // 3600
    mm = (total_secs % 3600) // 60
    ss = total_secs % 60
    # Uses semicolon separator for standard SCC compatibility
    return f"{hh:02d}:{mm:02d}:{ss:02d};{ff:02d}"

# ── Text Encoding ─────────────────────────────────────────────────────────────

def strip_markup(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\\[^}]+\}", "", text)
    text = text.replace("\u200b", "")
    return text.strip()


def encode_char(c):
    code = ord(c)
    if 0x20 <= code <= 0x7E:
        return code
    return {
        "\u2019": 0x27, "\u2018": 0x27,
        "\u201c": 0x22, "\u201d": 0x22,
        "\u2013": 0x2D, "\u2014": 0x2D,
        "\u2026": 0x2E,
        "\u00A0": 0x20,
    }.get(c, 0x20)


def text_to_scc_words(text):
    text = strip_markup(text)
    words = []
    i = 0
    while i < len(text):
        char = text[i]
        if char in SPECIAL_CHAR_MAP:
            words.extend([SPECIAL_CHAR_MAP[char], SPECIAL_CHAR_MAP[char]])
            i += 1
            continue
        
        b1 = encode_char(char)
        if i + 1 < len(text) and text[i + 1] not in SPECIAL_CHAR_MAP:
            b2 = encode_char(text[i + 1])
            i += 2
        else:
            b2 = 0x80 # Null pad byte
            i += 1
        words.append(f"{b1:02x}{b2:02x}")
    return words

# ── Core Processing Logic ─────────────────────────────────────────────────────

def build_scc_content(srt_path):
    raw = Path(srt_path).read_text(encoding="utf-8-sig", errors="replace")
    
    # Accurate regex to handle block structure
    blocks = re.findall(
        r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\s*\n\d+\s*\n|\n\s*\Z|\Z)", 
        raw, re.DOTALL
    )

    # Dictionary timeline grouping to manage same-frame collisions
    timeline = {}

    def add_to_timeline(secs, words):
        tc = seconds_to_scc_tc(secs)
        timeline.setdefault(tc, []).extend(words)

    for _, start_tc, end_tc, text in blocks:
        start = srt_time_to_seconds(start_tc)
        end = srt_time_to_seconds(end_tc)
        lines = [l.strip() for l in text.splitlines() if l.strip()][:2]

        # Payload: Standard 0.5s Preload
        payload = [CTRL_ENM, CTRL_ENM, CTRL_RCL, CTRL_RCL]
        for idx, line in enumerate(lines):
            pac = CTRL_PAC1 if (len(lines) == 2 and idx == 0) else CTRL_PAC2
            payload += [pac, pac] + text_to_scc_words(line)

        add_to_timeline(max(0, start - 0.5), payload)
        add_to_timeline(end, [CTRL_EDM, CTRL_EDM])   # Erase first
        add_to_timeline(start, [CTRL_EOC, CTRL_EOC]) # Flip second

    out_lines = ["Scenarist_SCC V1.0", "", ""]
    for tc in sorted(timeline.keys()):
        out_lines.append(f"{tc}\t{' '.join(timeline[tc])}")
        out_lines.append("")

    return "\r\n".join(out_lines).encode("ascii", errors="replace")

# ── Main Terminal UI ──────────────────────────────────────────────────────────

def main():
    cwd = Path.cwd()
    srt_files = sorted(cwd.glob("*.srt"))

    if not srt_files:
        print("\n  No .srt files found in the current directory.")
        print(f"  (Looked in: {cwd})\n")
        sys.exit(0)

    output_dir = cwd / OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    total = len(srt_files)
    print(f"\n{'━' * 54}")
    print(f"  SRT to SCC Converter")
    print(f"{'━' * 54}")
    print(f"  Source : {cwd}")
    print(f"  Output : {output_dir}")
    print(f"  Files  : {total}")
    print(f"{'━' * 54}\n")

    errors    = []
    new_files = []
    replaced  = []

    bar_fmt = (
        "  {l_bar}{bar}| {n_fmt}/{total_fmt} files "
        "[{elapsed} elapsed, {remaining} left]"
    )

    with tqdm(total=total, unit="file", bar_format=bar_fmt,
              colour="green", ncols=72) as pbar:
        for srt_path in srt_files:
            name = srt_path.name
            pbar.set_description(f"  {name[:36]:<36}")
            try:
                scc_bytes = build_scc_content(srt_path)
                out_path = output_dir / (srt_path.stem + ".scc")
                was_existing = out_path.exists()
                out_path.write_bytes(scc_bytes)

                (replaced if was_existing else new_files).append(name)

            except Exception as exc:
                errors.append((name, str(exc)))

            pbar.update(1)

    succeeded = len(new_files) + len(replaced)
    print(f"\n{'━' * 54}")
    print(f"  Done! — {succeeded}/{total} file(s) converted")
    print(f"{'━' * 54}")

    if new_files:
        print(f"\n  New ({len(new_files)}):")
        for f in new_files:
            print(f"    • {f}")

    if replaced:
        print(f"\n  Replaced ({len(replaced)}):")
        for f in replaced:
            print(f"    • {f}")

    if errors:
        print(f"\n  Errors ({len(errors)}) — skipped:")
        for fname, msg in errors:
            print(f"    • {fname}")
            print(f"        {msg}")
    else:
        print(f"\n  No errors.")

    print(f"\n  Saved to: {output_dir}")
    print(f"{'━' * 54}\n")


if __name__ == "__main__":
    main()