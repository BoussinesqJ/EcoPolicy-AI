"""
EcoPolicy-AI Security Review Script
====================================
Comprehensive pre-push security scan. Run before EVERY git push.

Usage:
    python security_review.py                    # Scan repo root
    python security_review.py --path /other/dir  # Scan specific directory
    python security_review.py --fix              # Auto-fix common issues
"""

import os
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# ============================================================
# SCAN RULES
# ============================================================

# --- 1. PATTERN-BASED SCANS (regex) ---

REGEX_PATTERNS = {
    # Personal identifiers
    "phone_number": {
        "pattern": r'(?<!\d)1[3-9]\d{9}(?!\d)',
        "severity": "CRITICAL",
        "description": "Chinese mobile phone number",
        "exclude_comments": True,
    },
    "id_card": {
        "pattern": r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]',
        "severity": "CRITICAL",
        "description": "Chinese ID card number (18 digits)",
    },
    "email_personal": {
        "pattern": r'[a-zA-Z0-9._%+-]+@(?!gov\.cn|gmail\.com|outlook\.com|qq\.com|163\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "severity": "HIGH",
        "description": "Personal email (non-public domain)",
    },
    "bank_account": {
        "pattern": r'(?:(?: bank| account|卡号|账号|account)\s*[:：]\s*)[\d\s-]{12,23}',
        "severity": "CRITICAL",
        "description": "Bank account number",
    },
    "credit_code": {
        "pattern": r'[0-9A-HJ-NP-RTUW-Y]{2}\d{6}[0-9A-HJ-NP-RTUW-Y]{10}',
        "severity": "CRITICAL",
        "description": "Unified Social Credit Code (18 chars)",
    },
    "tax_id": {
        "pattern": r'(?:税号|纳税识别号|tax\s*id)\s*[:：]\s*\d{15,20}',
        "severity": "CRITICAL",
        "description": "Tax identification number",
    },

    # --- 2. ENTERPRISE-SPECIFIC PATTERNS ---

    "enterprise_jyh": {
        "pattern": r'(?:金玉汇|湖北金玉汇|JYH|S02975)',
        "severity": "CRITICAL",
        "description": "Real enterprise: JinYuhui",
    },
    "enterprise_cmig": {
        "pattern": r'(?:中煤科工|武汉设计研究院|zmwhy|dzk)',
        "severity": "CRITICAL",
        "description": "Real enterprise: China Coal Technology",
    },
    "enterprise_any_full": {
        "pattern": r'(?:有限公司|股份有限公司|有限责任公司|集团有限公司)(?!\s*(?:示例|模板|模拟|虚构|如|或|和|与|etc))',
        "severity": "HIGH",
        "description": "Possible real enterprise name (full legal name)",
        "exclude_examples": True,
    },

    # --- 3. ADDRESS PATTERNS ---

    "specific_address": {
        "pattern": r'(?:路\d+号|街\d+号|栋\d+|楼\d+|室\d+|单元\d+|号楼)',
        "severity": "HIGH",
        "description": "Specific street address with building/unit number",
    },

    # --- 4. FINANCIAL DATA ---

    "specific_amount": {
        "pattern": r'(?:(?:营业收入|净利润|总资产|负债|营收|利润|资产总额|实缴税金)\s*[:：为达到]\s*)\d+(?:\.\d+)?\s*(?:万元|亿元|元)',
        "severity": "MEDIUM",
        "description": "Specific financial figure in enterprise context",
        "exclude_examples": True,
    },

    # --- 5. STOCK/CODE PATTERNS ---

    "stock_code_specific": {
        "pattern": r'S\d{6}|[0-3]\d{5}(?=\s*(?:挂牌|上市|股票))',
        "severity": "CRITICAL",
        "description": "Specific stock/exchange listing code",
    },

    # --- 6. SECRET/CREDENTIAL PATTERNS ---

    "password_pattern": {
        "pattern": r'(?:password|passwd|密码|口令)\s*[:：=]\s*\S+',
        "severity": "CRITICAL",
        "description": "Password or credential",
    },
    "api_key": {
        "pattern": r'(?:api[_-]?key|secret[_-]?key|access[_-]?token|token)\s*[:：=]\s*["\']?[A-Za-z0-9_\-]{20,}',
        "severity": "CRITICAL",
        "description": "API key or secret token",
    },
    "private_key": {
        "pattern": r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
        "severity": "CRITICAL",
        "description": "Private key file content",
    },
}

# --- FILE TYPE RESTRICTIONS ---

BLOCKED_EXTENSIONS = {
    ".db", ".sqlite", ".sqlite3",      # Database files
    ".docx", ".doc", ".xlsx", ".xls",   # Office documents
    ".pdf",                              # PDF files
    ".pptx", ".ppt",                     # PowerPoint
    ".env", ".env.local",               # Environment secrets
    ".key", ".pem", ".crt",             # Certificates
    ".p12", ".pfx",                      # Keystores
    ".pyc", ".pyo",                      # Compiled Python
    ".DS_Store",                         # macOS
    "Thumbs.db",                         # Windows
}

BLOCKED_DIRECTORIES = {
    "__pycache__",
    ".git",
    "node_modules",
    ".env",
    "credentials",
    "secrets",
}

# --- SENSITIVE FILENAMES ---

SENSITIVE_FILES = {
    "credentials.json",
    "service-account.json",
    "aws-credentials",
    ".ssh",
    "id_rsa",
    "id_ed25519",
}

# ============================================================
# SCANNER
# ============================================================

class SecurityScanner:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        self.findings = defaultdict(list)
        self.stats = {
            "files_scanned": 0,
            "files_skipped": 0,
            "findings_total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

    def scan(self):
        """Run all scans."""
        print(f"\n{'='*60}")
        print(f"  EcoPolicy-AI Security Review")
        print(f"  Path: {self.repo_path}")
        print(f"{'='*60}\n")

        # Phase 1: File type check
        self._scan_file_types()

        # Phase 2: Content scans
        self._scan_file_contents()

        # Phase 3: Directory check
        self._scan_directories()

        # Phase 4: Sensitive filenames
        self._scan_filenames()

        # Report
        self._print_report()

        return self.stats["critical"] == 0 and self.stats["high"] == 0

    def _scan_file_types(self):
        """Check for blocked file types."""
        print("[Phase 1] Checking file types...")
        for f in self.repo_path.rglob("*"):
            if f.is_file():
                ext = f.suffix.lower()
                name = f.name.lower()
                if ext in BLOCKED_EXTENSIONS or name in SENSITIVE_FILES:
                    rel = f.relative_to(self.repo_path)
                    self.findings["blocked_file"].append({
                        "file": str(rel),
                        "line": 0,
                        "severity": "HIGH",
                        "message": f"Blocked file type: {ext or name}",
                    })
                    self.stats["high"] += 1
                    self.stats["findings_total"] += 1
        print(f"  -> {self.stats['high']} blocked files found\n")

    def _scan_file_contents(self):
        """Scan all text file contents for patterns."""
        print("[Phase 2] Scanning file contents...")
        for f in self.repo_path.rglob("*"):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            # Only scan text files
            if ext not in {".py", ".yaml", ".yml", ".md", ".txt", ".json",
                           ".toml", ".cfg", ".ini", ".sh", ".bat", ".html",
                           ".css", ".js", ".gitignore"}:
                continue

            # Skip this script itself (contains detection patterns)
            if f.name == "security_review.py":
                continue
                continue

            rel = str(f.relative_to(self.repo_path))
            self.stats["files_scanned"] += 1

            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
            except Exception:
                self.stats["files_skipped"] += 1
                continue

            for rule_name, rule in REGEX_PATTERNS.items():
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                for i, line in enumerate(lines, 1):
                    # Skip comment lines for some rules
                    if rule.get("exclude_comments") and line.strip().startswith("#"):
                        continue
                    # Skip examples directory for enterprise patterns
                    if rule.get("exclude_examples") and "example" in rel.lower():
                        continue

                    matches = pattern.finditer(line)
                    for match in matches:
                        # Check if it's in a comment or docstring context
                        is_in_comment = line.strip().startswith("#") or line.strip().startswith("//")

                        self.findings[rule_name].append({
                            "file": rel,
                            "line": i,
                            "severity": rule["severity"],
                            "message": rule["description"],
                            "context": line.strip()[:120],
                            "match": match.group()[:50],
                        })
                        sev = rule["severity"].lower()
                        self.stats[sev] = self.stats.get(sev, 0) + 1
                        self.stats["findings_total"] += 1

        print(f"  -> {self.stats['files_scanned']} files scanned, {self.stats['files_skipped']} skipped\n")

    def _scan_directories(self):
        """Check for blocked directories."""
        print("[Phase 3] Checking directories...")
        for d in self.repo_path.rglob("*"):
            if d.is_dir() and d.name in BLOCKED_DIRECTORIES and d.name != ".git":
                rel = d.relative_to(self.repo_path)
                self.findings["blocked_dir"].append({
                    "file": str(rel),
                    "line": 0,
                    "severity": "HIGH",
                    "message": f"Blocked directory: {d.name}",
                })
                self.stats["high"] += 1
                self.stats["findings_total"] += 1
        print(f"  -> Directory check complete\n")

    def _scan_filenames(self):
        """Check for sensitive filenames."""
        print("[Phase 4] Checking sensitive filenames...")
        for f in self.repo_path.rglob("*"):
            if f.is_file() and f.name.lower() in {s.lower() for s in SENSITIVE_FILES}:
                rel = f.relative_to(self.repo_path)
                self.findings["sensitive_file"].append({
                    "file": str(rel),
                    "line": 0,
                    "severity": "CRITICAL",
                    "message": f"Sensitive file: {f.name}",
                })
                self.stats["critical"] += 1
                self.stats["findings_total"] += 1
        print(f"  -> Filename check complete\n")

    def _print_report(self):
        """Print the final security report."""
        print(f"{'='*60}")
        print(f"  SECURITY REVIEW REPORT")
        print(f"{'='*60}\n")

        total = self.stats["findings_total"]
        if total == 0:
            print("  [PASS] No security issues found.\n")
            print(f"  Files scanned: {self.stats['files_scanned']}")
            print(f"  -> Safe to push.\n")
            return

        print(f"  [RESULT] {total} issue(s) found!\n")
        print(f"  CRITICAL : {self.stats['critical']}")
        print(f"  HIGH     : {self.stats['high']}")
        print(f"  MEDIUM   : {self.stats.get('medium', 0)}")
        print(f"  LOW      : {self.stats.get('low', 0)}")
        print(f"\n  Files scanned: {self.stats['files_scanned']}")
        print()

        # Group by severity
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            items = []
            for rule_name, findings in self.findings.items():
                for f in findings:
                    if f["severity"] == severity:
                        items.append((rule_name, f))

            if not items:
                continue

            print(f"  --- {severity} ---")
            for rule_name, f in sorted(items, key=lambda x: x[1]["file"]):
                print(f"  [{f['severity']}] {f['message']}")
                print(f"    File: {f['file']}:{f['line']}")
                if f.get("context"):
                    print(f"    Context: {f['context'][:100]}")
                if f.get("match"):
                    print(f"    Match: {f['match']}")
                print()

        # Verdict
        if self.stats["critical"] > 0 or self.stats["high"] > 0:
            print(f"  [BLOCK] Push blocked. Fix CRITICAL and HIGH issues first.\n")
        else:
            print(f"  [WARN] MEDIUM/LOW issues found. Review before pushing.\n")

    def auto_fix(self):
        """Attempt to auto-fix common issues."""
        print("\n[Auto-fix] Scanning for fixable issues...")
        fixed = 0

        # Fix 1: Remove .db files
        for f in self.repo_path.rglob("*.db"):
            if f.is_file():
                print(f"  Removing: {f.relative_to(self.repo_path)}")
                f.unlink()
                fixed += 1

        # Fix 2: Remove __pycache__
        for d in self.repo_path.rglob("__pycache__"):
            if d.is_dir():
                import shutil
                print(f"  Removing: {d.relative_to(self.repo_path)}")
                shutil.rmtree(d)
                fixed += 1

        print(f"  -> Fixed {fixed} issues\n")
        return fixed


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="EcoPolicy-AI Security Review")
    parser.add_argument("--path", default=".", help="Path to scan (default: repo root)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix common issues")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path not found: {repo_path}")
        sys.exit(1)

    scanner = SecurityScanner(repo_path)

    if args.fix:
        scanner.auto_fix()

    safe = scanner.scan()

    if args.json:
        import json
        report = {
            "safe_to_push": safe,
            "stats": scanner.stats,
            "findings": {k: v for k, v in scanner.findings.items()},
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))

    sys.exit(0 if safe else 1)


if __name__ == "__main__":
    main()
