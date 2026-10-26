"""Công cụ chép chat Zalo cho giai đoạn 0: đọc định dạng, che thông tin cá nhân, đúng schema, chấm điểm."""

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "pilot" / "zalo_transcript.py"
spec = importlib.util.spec_from_file_location("zalo_transcript", TOOL)
zt = importlib.util.module_from_spec(spec)
sys.modules["zalo_transcript"] = zt
spec.loader.exec_module(zt)

CHAT = """# hộ: Quán thử
# giờ chốt: 04:00
# người gửi: Chị Lan = owner; Hà = accountant
== 02/10/2026 ==
10:00 Chị Lan: [ảnh a.jpg, b.jpg]
10:01 Chị Lan: chuyển giúp chị vào stk 0071000123456 nhé, sđt 0903123456
10:02 Chị Lan: Doanh thu hôm nay 12500000đ
   còn 2 bàn chưa tính
10:03 Hà: [sticker]
"""


def test_parse_and_build(tmp_path):
    (tmp_path / "anh").mkdir()
    (tmp_path / "anh" / "a.jpg").write_bytes(b"A")
    (tmp_path / "anh" / "b.jpg").write_bytes(b"B")
    t = zt.parse(CHAT)
    assert [m.kind for m in t.messages] == ["image", "text", "text", "sticker"]
    assert t.messages[2].text.endswith("còn 2 bàn chưa tính"), "dòng không giờ nối vào tin trước"
    doc, report = zt.build(t, tmp_path / "anh", tmp_path / "out", "tester")
    zt.validate(doc)
    texts = json.dumps(doc, ensure_ascii=False)
    assert "0071000123456" not in texts and "0903123456" not in texts
    assert "Chị Lan" not in texts and "Hà" not in texts, "tên người gửi được thay bằng mã"
    assert "12500000đ" in texts, "số tiền 8 chữ số không bị che nhầm thành số tài khoản"
    assert report["redacted"] == {"SDT": 1, "STK": 1}
    assert [s["role"] for s in doc["senders"]] == ["owner", "accountant"]
    assert doc["messages"][0]["sent_at"] == "2026-10-02T10:00:00+07:00"
    assert len(doc["messages"][0]["attachments"]) == 2 and (tmp_path / "out" / "images" / "b.jpg").exists()


@pytest.mark.parametrize("bad,msg", [
    ("10:00 A: hi", "thiếu dòng ngày"),
    ("== 02/10/2026 ==\n25:00 A: hi", "giờ không hợp lệ"),
    ("# người gửi: A = boss\n== 02/10/2026 ==\n10:00 A: hi", "vai trò"),
    ("== 02/10/2026 ==\n10:00 A: [ảnh]", "cần tên file"),
    ("== 02/10/2026 ==\nlinh tinh", "không hiểu"),
])
def test_parse_errors(bad, msg):
    with pytest.raises(zt.TranscriptError, match=msg):
        zt.parse(bad)


def test_cli_preview_and_score(tmp_path):
    (tmp_path / "chat.txt").write_text(CHAT.replace("[ảnh a.jpg, b.jpg]", "[ảnh a.jpg]") + "10:05 Chị Lan: tiền gas\n",
                                       encoding="utf-8")
    (tmp_path / "anh").mkdir()
    (tmp_path / "anh" / "a.jpg").write_bytes(b"A")
    assert zt.main([str(tmp_path / "chat.txt"), "--images", str(tmp_path / "anh"), "--out", str(tmp_path / "out")]) == 0
    path = tmp_path / "out" / "danh-dau.csv"
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert {"giao dịch", "liên kết: caption"} <= {r["loai"] for r in rows}
    # Người chép đánh dấu: mọi giao dịch đúng, riêng chú thích 'tiền gas' bị engine gán sai.
    for r in rows:
        r["dung_khong"] = "N" if "tiền gas" in r["noi_dung"] else "Y"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = zt.score(path)
    assert s["tu_dong_sai"] == 1 and s["chua_cham"] == 0
    assert 0 < s["STOR_uoc_tinh"] <= 1
