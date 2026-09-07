"""
Convert the raw Amazon Q chat-history JSON into a readable Markdown transcript.

Usage:
    python evidence/extract_transcript.py

Reads:  evidence/amazon-q-chat-history-raw.json
Writes: evidence/amazon-q-full-transcript.md
"""

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "amazon-q-chat-history-raw.json")
OUT = os.path.join(HERE, "amazon-q-full-transcript.md")


def clean(text: str) -> str:
    """Unescape HTML entities Amazon Q stores in message bodies."""
    return html.unescape(text or "").replace("\r\n", "\n")


def main() -> None:
    # utf-8-sig tolerates a leading BOM if one is ever present.
    with open(RAW, encoding="utf-8-sig") as fh:
        data = json.load(fh)

    tabs = next(c for c in data["collections"] if c["name"] == "tabs")
    lines = [
        "# Amazon Q Developer — Full Session Transcript",
        "",
        "Readable export of the raw chat history "
        "(`amazon-q-chat-history-raw.json`). Amazon Q extension v2.7.0, "
        "Language Server v1.78.0, model: Auto.",
        "",
        "---",
        "",
    ]

    for tab in tabs["data"]:
        for convo in tab.get("conversations", []):
            for msg in convo.get("messages", []):
                body = clean(msg.get("body", "")).strip()
                mtype = msg.get("type")

                # Skip the internal tool-result relay messages with no body.
                if not body:
                    continue

                if mtype == "prompt":
                    lines.append("## Prompt (me)")
                    lines.append("")
                    lines.append("```")
                    lines.append(body)
                    lines.append("```")
                    lines.append("")
                elif mtype == "answer":
                    lines.append("## Response (Amazon Q)")
                    lines.append("")
                    lines.append(body)
                    lines.append("")
                    lines.append("---")
                    lines.append("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
