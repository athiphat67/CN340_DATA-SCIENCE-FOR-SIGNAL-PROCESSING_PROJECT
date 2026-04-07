"""
run_test_report.py — รัน pytest ทุกไฟล์ใน tests/ แล้วสร้าง report
Usage: python tests/run_test_report.py
"""
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent  # Src/
TESTS_DIR = SRC_DIR / "tests"
REPORT_FILE = TESTS_DIR / "TEST_REPORT.md"

# รวบรวม test files ทั้งหมด
TEST_DIRS = [
    "test_unit",
    "test_integration",
    "test_llm",
    "test_data_engine",
    # "test_llm_with_api",  # ข้ามเพราะต้องใช้ API key จริง
]


def find_test_files() -> list[Path]:
    files = []
    for d in TEST_DIRS:
        dir_path = TESTS_DIR / d
        if dir_path.exists():
            for f in sorted(dir_path.glob("test_*.py")):
                files.append(f)
    return files


def run_single_test(test_file: Path) -> dict:
    """รัน pytest 1 ไฟล์ แล้ว return ผลลัพธ์"""
    rel = test_file.relative_to(SRC_DIR)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(rel), "-v", "--tb=short", "-o", "addopts="],
        capture_output=True, text=True, cwd=str(SRC_DIR), encoding="utf-8",
    )
    # นับจำนวน passed / failed / error / skipped
    lines = result.stdout.split("\n")
    summary_line = ""
    for line in reversed(lines):
        line_stripped = line.strip()
        if "passed" in line_stripped or "failed" in line_stripped or "error" in line_stripped:
            summary_line = line_stripped
            break

    # ดึงรายชื่อ test
    test_names = []
    for line in lines:
        if "PASSED" in line or "FAILED" in line or "ERROR" in line or "SKIPPED" in line:
            test_names.append(line.strip())

    return {
        "file": str(rel),
        "returncode": result.returncode,
        "summary": summary_line,
        "tests": test_names,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def generate_report(results: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"# Test Report")
    lines.append(f"")
    lines.append(f"Generated: {now}")
    lines.append(f"")

    # ── Summary table ──
    total_passed = 0
    total_failed = 0
    total_error = 0

    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Test File | Status | Summary |")
    lines.append("|---|-----------|--------|---------|")

    for i, r in enumerate(results, 1):
        fname = Path(r["file"]).name
        rc = r["returncode"]
        if rc == 0:
            status = "PASSED"
            total_passed += 1
        elif rc == 1:
            status = "FAILED"
            total_failed += 1
        else:
            status = "ERROR"
            total_error += 1
        summary = r["summary"] or "no output"
        lines.append(f"| {i} | `{fname}` | {status} | {summary} |")

    lines.append("")
    lines.append(f"**Total: {len(results)} files | "
                 f"{total_passed} passed | "
                 f"{total_failed} failed | "
                 f"{total_error} error**")
    lines.append("")

    # ── Detail per file ──
    lines.append("---")
    lines.append("")
    lines.append("## Details")
    lines.append("")

    for i, r in enumerate(results, 1):
        fname = Path(r["file"]).name
        rc = r["returncode"]
        status_emoji = "PASS" if rc == 0 else ("FAIL" if rc == 1 else "ERROR")
        lines.append(f"### {i}. `{fname}` [{status_emoji}]")
        lines.append("")
        lines.append(f"**File:** `{r['file']}`")
        lines.append("")

        if r["tests"]:
            lines.append("**Tests:**")
            lines.append("```")
            for t in r["tests"]:
                lines.append(t)
            lines.append("```")
        else:
            lines.append("**Tests:** (no test output captured)")

        lines.append("")
        if r["summary"]:
            lines.append(f"**Result:** {r['summary']}")
        lines.append("")

        # แสดง stderr ถ้ามี error
        if rc != 0 and r["stderr"]:
            lines.append("**Errors:**")
            lines.append("```")
            # ตัดให้ไม่ยาวเกินไป
            stderr_lines = r["stderr"].strip().split("\n")[-30:]
            for sl in stderr_lines:
                lines.append(sl)
            lines.append("```")
            lines.append("")
        
        # แสดง stdout failure details
        if rc != 0 and r["stdout"]:
            lines.append("**Output:**")
            lines.append("```")
            stdout_lines = r["stdout"].strip().split("\n")[-40:]
            for sl in stdout_lines:
                lines.append(sl)
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("  Test Report Generator")
    print("=" * 60)
    
    test_files = find_test_files()
    print(f"\nFound {len(test_files)} test files:\n")
    for f in test_files:
        print(f"  - {f.relative_to(SRC_DIR)}")

    results = []
    for f in test_files:
        rel = f.relative_to(SRC_DIR)
        print(f"\nRunning: {rel} ...", end=" ", flush=True)
        r = run_single_test(f)
        rc = r["returncode"]
        print(f"{'PASS' if rc == 0 else 'FAIL'} ({r['summary']})")
        results.append(r)

    report = generate_report(results)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{'=' * 60}")
    print(f"  Report saved to: {REPORT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
