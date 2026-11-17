"""Offline tests: digest building and the Slack / e-mail / Markdown renderers (no network, no Apify token).

Run: pip install -r requirements.txt pytest && pytest -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import alert  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "sample_items.json").read_text(encoding="utf-8"))  # real Actor output


def change(t, title, old=None, new=None, pct=None, store="shop.example"):
    return {"rowType": "change", "changeType": t, "store": store, "title": title, "url": f"https://{store}/products/x",
            "currency": "USD", "oldPrice": old, "newPrice": new, "priceChangePct": pct}


class FakeKV:
    def __init__(self, value):
        self.value = value

    def get_record(self, key):
        return {"key": key, "value": self.value} if key == "RUN-SUMMARY" else None


@pytest.fixture
def cfg():
    return alert.load_config(ROOT / "config.yml")


def test_slack_payload_from_real_sample(cfg):
    digest, kept = alert.make_digest(FIXTURE, cfg, None)
    assert digest.total == len(kept) == len(FIXTURE) > 0
    payload = alert.build_slack_payload(digest)
    json.dumps(payload)
    blocks = payload["blocks"]
    assert payload["text"] and blocks[0]["type"] == "header" and len(blocks) <= alert.MAX_SLACK_BLOCKS
    sections = [b for b in blocks if b["type"] == "section"]
    assert len(sections) == len(digest.entries)
    for b, e in zip(sections, digest.entries):
        assert f"<{e.url}|" in b["text"]["text"] and len(b["text"]["text"]) <= 3000


def test_ordering_labels_and_prices(cfg):
    items = [change("new", "New tee", new=30), change("price_increase", "Up", 10, 12, 20.0),
             change("price_drop", "Small drop", 100, 90, -10.0), change("price_drop", "Big drop", 120, 60, -50.0),
             change("restocked", "Back", 25.5, 25.5)]
    digest, kept = alert.make_digest(items, cfg, None)
    assert [e.title for e in digest.entries] == ["Big drop", "Small drop", "Back", "New tee", "Up"]
    big = digest.entries[0].meta
    assert big[0] == "Price drop -50%" and big[1] == "120.00 USD → 60.00 USD"
    assert digest.entries[2].meta[1] == "25.50 USD"
    assert digest.summary == "5 change(s): 2 price drop, 1 back in stock, 1 new product, 1 price increase."


def test_status_rows_become_notes_not_entries(cfg):
    items = [{"rowType": "status", "store": "a.com", "status": "baseline-recorded", "productsRecorded": 308},
             {"rowType": "status", "store": "b.com", "input": "b.com", "status": "blocked", "detail": "HTTP 403."}]
    digest, kept = alert.make_digest(items, cfg, FakeKV({"stoppedReason": "max charge limit reached"}))
    assert digest.total == 0 and kept == [] and digest.entries == []
    text = " ".join(digest.notes)
    assert "a.com (308 products)" in text and "b.com: blocked. HTTP 403." in text and "max charge limit" in text
    assert digest.summary == "No changes since the last run."


def test_baseline_summary(cfg):
    items = [{"rowType": "status", "store": "a.com", "status": "baseline-recorded", "productsRecorded": 3}]
    digest, _ = alert.make_digest(items, cfg, None)
    assert digest.summary.startswith("Baseline recorded for 1 store(s)")


def test_input_forces_changes_mode(cfg):
    run_input = alert.build_input(cfg)
    assert run_input["mode"] == "changes" and run_input["stateKey"] == cfg["input"]["stateKey"]
    with pytest.raises(SystemExit):
        alert.build_input({"input": {"stores": []}, "alert": {}})


def test_email_and_markdown_render(cfg):
    digest, _ = alert.make_digest(FIXTURE, cfg, None)
    subject, text, html_body = alert.render_email(digest)
    md = alert.render_markdown(digest)
    assert subject and digest.entries[0].title in text
    assert digest.entries[0].url in html_body and digest.entries[0].url in md


def test_items_file_dry_run(tmp_path, monkeypatch):
    for k in ("SLACK_WEBHOOK_URL", "SMTP_HOST", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(k, raising=False)
    out = tmp_path / "out"
    rc = alert.main(["--config", str(ROOT / "config.yml"), "--out", str(out), "--dry-run",
                     "--items-file", str(ROOT / "tests" / "fixtures" / "sample_items.json")])
    assert rc == 0 and (out / "digest.md").exists() and (out / "items.csv").exists()


def test_vendor_shown_only_for_resellers():
    own = alert.change_entry({**change("new", "Tee", new=10, store="gymshark.com"), "vendor": "Gymshark | Be a visionary."})
    other = alert.change_entry({**change("new", "Shoe", new=10, store="shop.example"), "vendor": "Allbirds"})
    assert own.meta == ["New product", "10.00 USD", "gymshark.com"]
    assert other.meta[-1] == "Allbirds"
