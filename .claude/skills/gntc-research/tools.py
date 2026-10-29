"""Helpers for the gntc-research skill. They reuse the project's own modules, so prompts and rules have one source.

Run with the project venv from the project root:
    .venv\\Scripts\\python.exe .claude\\skills\\gntc-research\\tools.py <command> ...
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import evidence  # noqa: E402
import monitor  # noqa: E402
import registry  # noqa: E402
import research_agent  # noqa: E402


def cmd_prompt(args):
    """The writing prompt the dashboard gives its model for this mode."""
    if args.mode == 'monitor':
        print(monitor.CHANGE_PROMPT)
    else:
        profile = Path(args.profile).read_text(encoding='utf-8-sig') if args.profile else ''
        print(research_agent.build_report_prompt(profile, args.mode))


def cmd_registry(args):
    """Official registry record: Markdown table to stdout, raw record saved as JSON for later comparison."""
    record = registry.fetch_company(args.tax_id)
    if record is None:
        print(f'查無統一編號 {args.tax_id} 的公司登記資料。')
        return
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(registry.to_markdown(record))


def cmd_search(args):
    """Companies whose registered name contains the keyword, to find the tax ID and rule out same-name companies."""
    for row in registry.search_by_name(args.keyword, active_only=not args.all):
        print(f'{row["tax_id"]}\t{row["name"]}\t{row["status"]}\t{row["responsible"]}\t{row["address"]}')


def cmd_compare(args):
    """Registry changes between two saved records."""
    load = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))  # noqa: E731
    changes = registry.compare(load(args.previous), load(args.current))
    print('\n'.join(f'- {c}' for c in changes) or '公司登記資料無變更。')


def cmd_mark(args):
    """Mark figures without a citation as 〔待驗證〕 in place; prints the count."""
    path = Path(args.report)
    # utf-8-sig: PowerShell writes a BOM, which would hide a leading table row from the marker.
    report, count = evidence.mark_unverified(path.read_text(encoding='utf-8-sig'), tuple(args.skip or ()))
    path.write_text(report, encoding='utf-8')
    print(f'〔待驗證〕標記共 {count} 處。')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser('prompt')
    p.add_argument('mode', choices=('market', 'company', 'monitor'))
    p.add_argument('--profile', help='file with our own company profile (adds the entry / differentiation section)')
    p.set_defaults(func=cmd_prompt)
    p = sub.add_parser('registry')
    p.add_argument('tax_id')
    p.add_argument('--save')
    p.set_defaults(func=cmd_registry)
    p = sub.add_parser('search')
    p.add_argument('keyword')
    p.add_argument('--all', action='store_true', help='include dissolved / revoked companies')
    p.set_defaults(func=cmd_search)
    p = sub.add_parser('compare')
    p.add_argument('previous')
    p.add_argument('current')
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser('mark')
    p.add_argument('report')
    p.add_argument('--skip', action='append', help='a ## section title whose figures come from the registry')
    p.set_defaults(func=cmd_mark)
    args = parser.parse_args()
    try:
        args.func(args)
    except (registry.RegistryError, ValueError) as exc:
        sys.exit(str(exc))


if __name__ == '__main__':
    main()
