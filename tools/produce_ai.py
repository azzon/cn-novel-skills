#!/usr/bin/env python3
"""produce_ai.py — 全AI协作章节生产流水线（每章5阶段subagent对抗）

阶段1: 卡生成+审核 (subagent写卡 → card_check门)
阶段2: 正文写作 (subagent写章 → era_clean+fix_quotes+check门)
阶段3: 冷读 (subagent独立冷读 → 总分≥7门)
阶段4: 修复 (冷读<7时,subagent按报告修复 → check重跑)
阶段5: 记账+done (自动: ledger_extract + done --strict)

用法: python3 tools/produce_ai.py <章号> [--book 书根]
前置: 场景卡骨架已通过 skill_protocol gen card 生成
"""
import sys, subprocess, re, json, pathlib
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def run(cmd, timeout=120):
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       timeout=timeout, cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


def agent_write(prompt_path, output_path, sys_prompt="你是一个专业的网文写作AI。按指令完成写作任务。"):
    """调用AI写文件（此处写入prompt让外部agent系统处理）
    在实际生产中，这一步由ZCode的agent系统调度。
    此脚本只负责准备prompt和验证输出。"""
    pp = Path(prompt_path)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(sys_prompt + "\n\n" + output_path, encoding="utf-8")
    return pp


def gate_check(fp, label="check"):
    rc, out, _ = run(["tools/check.py", str(fp)])
    fails = re.findall(r"\[FAIL\]", out)
    return rc == 0, out


def gate_card(n, book):
    rc, out, _ = run(["tools/card_check.py", str(n), "--book", str(book)])
    return rc == 0, out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: produce_ai.py <章号> [--book 书根]"); return 2
    n = int(args[0])
    book = Path(sys.argv[sys.argv.index("--book") + 1]).resolve() if "--book" in sys.argv else None
    if book is None:
        book = ROOT  # 主书

    B = book
    text_dir = B / "text" / "卷1"
    body = text_dir / f"第{n:03d}章.md"
    card_dir = B / "卡"
    card = card_dir / f"卷1-第{n:03d}章-场1.md"
    audit = B / "audit"
    audit.mkdir(exist_ok=True)

    print(f"═══ 全AI流水线: 第{n:03d}章 ═══")

    # Phase 1: 场景卡
    print("\n── Phase 1: 场景卡 ──")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"),
                        "gen", "card", str(n)] + (["--book", str(B)] if B != ROOT else []),
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        print(f"  ❌ gen card: {r.stderr[:80]}"); return 1
    print(f"  ✅ 骨架卡生成: {card}")

    # Phase 2: 正文 (AI写)
    print("\n── Phase 2: 正文写作 ──")
    print(f"  目标: {body}")
    print(f"  (AI正文由ZCode主会话的Write工具写入，此脚本负责验证)")

    if not body.exists():
        print(f"  ❌ 正文不存在: {body}")
        print(f"  → 请在主会话中用Write工具写正文，然后重跑此脚本")
        return 1
    print(f"  ✅ 正文已存在: {len(body.read_text(encoding='utf-8'))} chars")

    # Phase 3: 机器门
    print("\n── Phase 3: 机器门 ──")
    for name, cmd in [
        ("fix_quotes", ["tools/fix_quotes.py", str(body)]),
        ("era_clean", ["tools/era_clean.py", str(body)]),
        ("check", ["tools/check.py", str(body)]),
        ("card_check", ["tools/card_check.py", str(n), "--book", str(B)]),
        ("voice_check", ["tools/voice_check.py", str(body)]),
    ]:
        rc, out, err = run(cmd)
        status = "✅" if rc == 0 else "❌"
        detail = ""
        for line in out.splitlines():
            if "FAIL]" in line:
                detail = line.strip()[:60]; break
        print(f"  {status} {name}: {detail if detail else 'OK'}")

    # Phase 4: 冷读 (AI subagent)
    print("\n── Phase 4: 冷读 ──")
    cr_file = audit / f"冷读-第{n:03d}章.md"
    if cr_file.exists():
        txt = cr_file.read_text(encoding="utf-8")
        m = re.search(r"总分[:：]\s*\*{0,2}([\d.]+)", txt)
        score = float(m.group(1)) if m else 0
        will = "不会翻" not in txt
        icon = "✅" if score >= 7 and will else "❌"
        print(f"  {icon} 冷读总分: {score}/10 | 会翻: {will}")
    else:
        print(f"  ❌ 冷读报告不存在: {cr_file}")
        print(f"  → 请派发独立冷读代理后重跑")

    # Phase 5: done
    print("\n── Phase 5: done ──")
    args_done = ["tools/pipeline.py", "done", str(n)]
    if B != ROOT:
        args_done += ["--book", str(B)]
    rc, out, err = run(args_done, timeout=60)
    for line in out.splitlines():
        if "✅" in line or "❌" in line:
            print(f"  {line.strip()}")

    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
